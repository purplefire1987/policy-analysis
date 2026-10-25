#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**库内容与文档的交叉核对**：黑名单、已删页面、结构数字、脚本数量、专家引用。

这一组的共同点：判据来自 `pkb/domain`（口径）或磁盘实际（卡数、文件名），
而不是文档自己说了什么。所以每一条都要么指向一处口径，要么指向一次 `glob`。
"""
import re

from pkb.core import VAULT, CARD_DIR, CHAIN_DIR
from pkb.domain import DOC_MUST_MENTION   # 黑名单唯一定义处：pkb/domain/blacklist.py

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


def check_structure_numbers(docs):
    n_cards = len(list(CARD_DIR.glob('*.md')))
    n_chains = len(list(CHAIN_DIR.glob('*.md')))
    t = docs.get('AGENTS', '')
    m = re.search(r'(\d+)\s*张产业卡', t)
    if m and int(m.group(1)) != n_cards:
        err('AGENTS', f'「{m.group(1)} 张产业卡」，实际 {n_cards} 张')
    m = re.search(r'(\d+)\s*条索引链', t)
    if m and int(m.group(1)) != n_chains:
        err('AGENTS', f'「{m.group(1)} 条索引链」，实际 {n_chains} 条')
    if not any(e[0] == 'AGENTS' and '张产业卡' in e[1] or '条索引链' in e[1] for e in errors):
        ok(f'结构数字：AGENTS 的 {n_cards} 张卡 / {n_chains} 条链与实际一致')


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
