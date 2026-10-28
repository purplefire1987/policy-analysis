#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**库内容与文档的交叉核对**：黑名单、已删页面、结构数字、脚本数量、专家引用。

这一组的共同点：判据来自 `pkb/domain`（口径）或磁盘实际（卡数、文件名），
而不是文档自己说了什么。所以每一条都要么指向一处口径，要么指向一次 `glob`。
"""
import re

from pkb.core import (VAULT, CARD_DIR, CHAIN_DIR, TEMPLATE_DIR, WEEK_TEMPLATE,
                      SIGNAL_TEMPLATE, card_files, read as lib_read)
from pkb.domain import DOC_MUST_MENTION, FIELD_MAP
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
    """AGENTS 里「唯一允许写数字」的那句（结构常量）括号里的那串。"""
    m = re.search(r'结构常量[^\n（]{0,6}（([^）]+)）', t)
    return m.group(1) if m else ''


def actual_facts():
    """结构常量的实物：一个事实一个来源，一律现数，没有一个是手填的。

    `words` 借 `checks/structure` 的解析——同一张表解析两次就是两份会漂的代码。
    """
    from pkb.checks import structure as _structure      # 局部导入：避免包初始化期互引
    return {
        'cards': len(card_files(CARD_DIR)),
        'chains': len(list(CHAIN_DIR.glob('*.md'))),
        'words': len(_structure.load_theme_words()[1]),
        'sections': len(re.findall(r'^##\s+', lib_read(WEEK_TEMPLATE, ''), re.M)),
        'fields': len(re.findall(r'^- \*\*', lib_read(SIGNAL_TEMPLATE, ''), re.M)),
    }


# 一个事实一行：(键, 认它的写法, 单位)。写法要窄——**宁可漏认，不可错认**。
# 「节」故意不在这里：`政策链三节`、`六节历史归档` 说的都是别的东西（前者是链的正文三节，
# 后者是 W39–41 的历史事实），一条规则不该让这两种正确写法看起来像报错。
# 节数只在 AGENTS「结构常量」那一句里查——那里括号内的「八节」不会有歧义。
FACTS = (
    ('cards', (r'(\d+)\s*张(?:产业卡|政策卡片|卡)',), '张产业卡'),
    ('chains', (r'(\d+)\s*条(?:索引链|链)',), '条索引链'),
    ('words', (r'(\d+)\s*个受控词',), '个受控词'),
    ('fields', (r'([\d一二三四五六七八九十]+)\s*个?字段',), '个信号字段'),
)

# 参与比对的文件。**台账与报告不在此列**：它们的数字是「当时」的快照，
# 改了等于篡改记录（体检报告里那些「138 张卡／60 个词」就该原样留着）。
SPEC_DOCS = ('AGENTS', 'index', '政策速览', '专家定义', '专家包README', 'SKILL')


def scan_counts(text):
    """文本里所有「结构常量」写法：[(行号, 原文, 键, 值)]。纯函数，便于直接喂字符串测。"""
    hits = []
    for lineno, line in enumerate(text.split('\n'), 1):
        for key, pats, _label in FACTS:
            for pat in pats:
                for m in re.finditer(pat, line):
                    val = _num(m.group(1))
                    if val is not None:
                        hits.append((lineno, m.group(0), key, val))
    return hits


def check_structure_numbers(docs):
    """结构常量与实物：**每一份规则类文档里的每一处**都要对得上。

    为什么不再只查 AGENTS 那一句（2026-10-26 改）：那句话是唯一「被允许写死数字」的，
    这没错；但同一批数字散在 AGENTS、index、政策速览 与专家定义四份文档里，
    而旧实现只比对 AGENTS 那一句。于是**结构一改，其余各处的数字静默过期**——
    它们恰恰是采集 agent 每次都会读的。现在改成一张「事实 → 实物」表扫全部规则类文档：
    改结构时跑一次 `check --only docs`，报出来的每一行都是待改清单。
    （具体几处不写在注释里，看输出——写死一个「9 处」，改完文档它就过期了。）
    """
    facts = actual_facts()
    seen, bad = 0, False
    for name in SPEC_DOCS:
        t = docs.get(name, '')
        if not t:
            continue
        for lineno, text, key, val in scan_counts(t):
            seen += 1
            if val != facts[key]:
                bad = True
                unit = next(u for k, _p, u in FACTS if k == key)
                err(name, f'第 {lineno} 行写「{text}」，实际 {facts[key]} {unit}'
                          f'——结构改了就同步改这里，别让它自己过期')
    if not seen:
        err('AGENTS', '一份文档里也没读出结构数字——判据失效，不是文档没问题')
    elif not bad:
        ok('结构数字：' + str(seen) + ' 处写法全部等于实物（'
           + '／'.join(f'{u} {facts[k]}' for k, _p, u in FACTS) + '）')

    # 「八节」单独查：只认 AGENTS「结构常量（…）」括号里的那一个，其余写法含义不同。
    seg = _constants(docs.get('AGENTS', ''))
    if not seg:
        err('AGENTS', '找不到「结构常量（…）」那段，节数无法校验——不静默放过')
        return
    m = re.search(r'([\d一二三四五六七八九十]+)\s*节', seg)
    if not m:
        err('AGENTS', '「结构常量」括号里没读出节数——判据失效，不是文档没问题')
    elif _num(m.group(1)) != facts['sections']:
        err('AGENTS', f'结构常量写「{m.group(0)}」，实际周观点 {facts["sections"]} 节')


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


def _section(text, head):
    """取 `head` 开头那一节（到下一个同级或更高级标题为止）。取不到返回空串。"""
    lines = text.split('\n')
    start = next((i for i, l in enumerate(lines) if l.startswith(head)), None)
    if start is None:
        return ''
    level = len(head) - len(head.lstrip('#'))
    out = []
    for l in lines[start + 1:]:
        if re.match(r'^#{1,%d}\s' % level, l):
            break
        out.append(l)
    return '\n'.join(out)


def check_template_list(docs):
    """index 第五节的模板清单 vs `templates/` 实物，**双向**。

    为什么判：清单是手写在 index 里的，实物是目录里的文件，两边谁都看不见谁。
    加一个模板忘了挂 index，读者就找不到它；index 写着已删的模板，读者会去建一个空文件。
    """
    t = docs.get('index', '')
    if not t:
        warn('index', '文件不存在，跳过模板清单比对')
        return
    listed = set(re.findall(r'\[\[([^\[\]|]+模板)\]\]', _section(t, '## 五、模板')))
    on_disk = {p.stem for p in TEMPLATE_DIR.glob('*.md')}
    missing, extra = sorted(on_disk - listed), sorted(listed - on_disk)
    for n in missing:
        err('index', f'模板 {n}.md 在 templates/ 里存在，但第五节没列——读者找不到它')
    for n in extra:
        err('index', f'第五节列了 [[{n}]]，但 templates/ 里没有这个文件')
    if not missing and not extra:
        ok(f'模板清单：index 第五节与 templates/ 一致（{len(on_disk)} 个）')


def check_vocab_list(docs):
    """受控词名单三处对齐：index 第二节的表、磁盘上的卡、`FIELD_MAP` 的键。

    为什么只批名单不批数字：`check_structure_numbers` 早就核「33 个受控词」这个**数**，
    于是「数对而名字错」一路绿——把「养老」写成「老龄」、或者删掉一个词又加一个词，
    三处全对不上，谁都不报。名单才是要核的东西，数字只是它的长度。
    """
    t = docs.get('index', '')
    if not t:
        warn('index', '文件不存在，跳过受控词名单比对')
        return
    listed = set()
    for line in _section(t, '## 二、政策链与受控词').split('\n'):
        m = re.search(r'\]\]\s*\|\s*([^|]+?)\s*\|', line)
        if m:
            listed |= {w.strip() for w in m.group(1).split('、') if w.strip()}
    disk = {p.stem.split('政策卡片-', 1)[-1] for p in card_files(CARD_DIR)}
    code = set(FIELD_MAP)
    bad = False
    for label, other in (('磁盘上的卡', disk), ('domain/chains.py 的 FIELD_MAP', code)):
        only_doc = sorted(listed - other)
        only_other = sorted(other - listed)
        for w in only_doc:
            err('index', f'受控词表有「{w}」，但{label}里没有——新增的词没落地，或删卡后没清表')
            bad = True
        for w in only_other:
            err('index', f'{label}有「{w}」，但第二节受控词表没列——受控词表是唯一源，漏一行就查不到')
            bad = True
    if not bad:
        ok(f'受控词名单：index／磁盘／FIELD_MAP 三处一致（{len(listed)} 个词）')


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
