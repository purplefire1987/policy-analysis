#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**库内容与文档的交叉核对**：黑名单、已删页面、结构数字、脚本数量、专家引用。

这一组的共同点：判据来自 `pkb/domain`（口径）或磁盘实际（卡数、文件名），
而不是文档自己说了什么。所以每一条都要么指向一处口径，要么指向一次 `glob`。
"""
import re

from pkb.core import (VAULT, CARD_DIR, CHAIN_DIR, WEEK_TEMPLATE,
                      SIGNAL_TEMPLATE, read as lib_read)
from pkb.domain import DOC_MUST_MENTION
# 黑名单唯一定义处：pkb/domain/blacklist.py

from ._state import err, warn, ok, errors

# 2026-10-24 三合一后被删除的页面：任何文档再以 wikilink 引用都是漏改。
DELETED_PAGES = ['政策跟踪运营方案', '政策链总览', '主题词表']


def check_blacklist(docs):
    need = list(DOC_MUST_MENTION)
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        miss = [w for w in need if w not in t]
        if miss:
            err(name, f'黑名单缺「{"、".join(miss)}」——读这份文件的 agent 会去采它')
    if not any('黑名单' in e[1] for e in errors):
        ok(f'黑名单：AGENTS／专家定义 均含{"、".join(need)}')


def check_deleted_refs(docs):
    pat_link = re.compile(r'\[\[(' + '|'.join(DELETED_PAGES) + r')')
    pat_path = re.compile(r'wiki/总览/(' + '|'.join(DELETED_PAGES) + r')\.md')
    hit = False
    for name, t in docs.items():
        if not t:
            continue
        for m in pat_link.finditer(t):
            err(name, f'仍以 wikilink 引用已删除页面 [[{m.group(1)}]]')
            hit = True
        for m in pat_path.finditer(t):
            err(name, f'仍引用已删除文件 wiki/总览/{m.group(1)}.md')
            hit = True
    if not hit:
        ok('已删页面：三处均未再引用（仅在说明中提及名称，不算引用）')


CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
          '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _num(s):
    """「八」与「8」都认——规则里写中文更像人写的，判据不能因此瞎。"""
    return CN_NUM.get(s, int(s) if s.isdigit() else None)


def _constants(t):
    """AGENTS 里「唯一允许写数字」的那句（结构常量）——它是全库唯一可写死数字的地方。"""
    m = re.search(r'结构常量[^\n（]{0,6}（([^）]+)）', t)
    return m.group(1) if m else ''


def check_structure_numbers(docs):
    """结构常量必须等于实物：卡数、链数、周观点节数、信号字段数。

    2026-10-26 审计发现这句写着「7 节」而周观点早已是八节——**它偏偏是全库
    唯一被允许写死数字的一句话**，写错没有人发现，因为没人拿它跟模板比。
    所以判据取实物：卡片目录 glob、链目录 glob、模板的 `##` 数、`REQUIRED_FIELDS` 长度。
    """
    t = docs.get('AGENTS', '')
    seg = _constants(t)
    if not seg:
        err('AGENTS', '找不到「结构常量（…）」那段，本项无法校验——不静默放过')
        return
    n_fields = len(re.findall(r'^- \*\*', lib_read(SIGNAL_TEMPLATE, ''), re.M))
    actual = [
        (r'(\d+)\s*张产业卡', len(list(CARD_DIR.glob('*.md'))), '张产业卡'),
        (r'(\d+)\s*条索引链', len(list(CHAIN_DIR.glob('*.md'))), '条索引链'),
        (r'([\d一二三四五六七八九十]+)\s*节', 
         len(re.findall(r'^##\s+', lib_read(WEEK_TEMPLATE, ''), re.M)), '周观点节数'),
        (r'([\d一二三四五六七八九十]+)\s*字段', n_fields, '信号字段'),
    ]
    bad = False
    for pat, real, label in actual:
        m = re.search(pat, seg)
        if not m:
            continue
        got = _num(m.group(1))
        if got is not None and got != real:
            bad = True
            err('AGENTS', f'结构常量写「{m.group(0)}」，实际 {label} {real}')
    if not bad:
        ok('结构常量与实物一致（' + '／'.join(f'{lbl} {n}' for _p, n, lbl in actual) + '）')
    if not any(re.search(p, seg) for p, _n, _l in actual):
        err('AGENTS', '结构常量那段一条数字也没读出来——判据失效，不是文档没问题')


def check_no_hardcoded_count(docs):
    """「N 个脚本」这类表述在增删脚本后必然过时，必须拦。

    但假设句不算——「增删一个脚本要改三处提示词」说的是「如果」，
    不是「现在有几个」。不排除就会把规则说明本身判成违规，跟节拍那条是同一类误报。
    """
    pat = re.compile(r'([一二三四五六七八九十]|\d+)\s*个\s*脚本')
    ASSUME = ('增删', '新增', '删除', '假如', '如果', '假设', '以后', '将来', '一旦', '例如', '比如')
    hit = False
    for name, t in docs.items():
        if not t:
            continue
        for m in pat.finditer(t):
            line_start = t.rfind('\n', 0, m.start()) + 1
            line_end = t.find('\n', m.end())
            line = t[line_start:line_end if line_end > 0 else len(t)]
            if any(k in line for k in ASSUME):
                continue          # 假设性表述：说的是「如果」，不是「现在有几个」
            err(name, f'写死了脚本数量「{m.group(0)}」——增删脚本后必然过时')
            hit = True
    if not hit:
        ok('脚本数量：三处均未写死（假设句已排除）')


def check_expert_refs(docs):
    t = docs.get('专家定义', '')
    if not t:
        warn('专家定义', '文件不存在，跳过引用检查')
        return
    names = {p.stem for p in VAULT.rglob('*.md') if '.obsidian' not in p.parts}
    bad = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', t):
        target = m.group(1).split('|')[0].split('#')[0].strip()
        if not target or '{' in target or '-X' in target or target.endswith('XXX'):
            continue                      # 模板占位符，不是真链接
        if target not in names:
            bad.append(f'[[{target}]]')
    for m in re.finditer(r'`(wiki/[^`]+\.md)`', t):
        if not (VAULT / m.group(1)).exists():
            bad.append(m.group(1))
    if bad:
        for b in sorted(set(bad)):
            err('专家定义', f'引用的页面/路径不存在：{b}')
    else:
        ok('专家定义：所有页面与路径引用有效')
