#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条政策的全链：政策 → 卡 → 链 → 信号 → 一手存档。

为什么再加一个检索动作
------------------
`query` 能回答「这个词出现在哪些行」，回答不了「这条政策在库里挂在哪」。
后一个问题要跨三种文件：卡（内容）、链（目录）、信号与存档（旁证）。
它们的关系全躺在 frontmatter 与「关联卡片」节里，此前只能人工三处翻。

**只连关系，不写结论**：命中的原话照旧不摘、不评。它给的是「去哪几处读」，
不是「这件事怎么看」——后者归周观点与分析。

用法（统一走入口）
----
    run.py trace 促进房车消费             # 按标题片段找政策，牵出全链
    run.py trace 国办函〔2026〕82号       # 按文号找
    run.py trace --card 文旅体育          # 只看某张卡里的政策

恒 exit 0：这是取素材的，不是校验器。查不到会明说，并给最相近的三个标题。
"""
import argparse
import difflib
import re

from pkb.core import (ARTICLE_DIR, CARD_DIR, CHAIN_DIR, SIGNAL_DIR,
                      md_section_lines, read, scan_dated, summary)

DOC_NO = re.compile(r'〔\d{4}〕\s*\d+\s*号')
PAREN = re.compile(r'[（(].*?[）)]')
PUNCT = re.compile(r'[《》〈〉「」“”"\'\-—－、，,。．\.：:；;（）()〔〕【】\s]')


def norm(s):
    """去标点与空白。只用于「像不像」，不用于判定——判定归 check。"""
    return PUNCT.sub('', s or '')


def keys(title):
    """一条政策标题的全部可认形态：文号、去括号后的题名。

    为什么要两个：库里两种写法都有人用——信号页习惯写文号（「国办函〔2026〕82 号」），
    卡片小节写全称。只按全称比，就会漏掉那些只提文号的信号。
    """
    out = [norm(m.group(0)) for m in DOC_NO.finditer(title)]
    core = norm(PAREN.sub('', title))
    if core:
        out.append(core)
    return [k for k in out if len(k) >= 6] or [norm(title)]


def like(ks, text):
    t = norm(text)
    return any(k in t for k in ks)


def policies(keyword, card=None):
    """卡片里标题像这个关键词的小节。"""
    out = []
    for sec in scan_dated(CARD_DIR):
        name = re.sub(r'^政策卡片-|\.md$', '', sec['file'])
        if card and name != card:
            continue
        if keyword and not like(keys(keyword), sec['title']):
            continue
        sec['card'] = name
        out.append(sec)
    return out


def chains_of(card):
    """哪些链的「关联卡片」节点到了这张卡。链是目录，一张卡可属多条链。"""
    out = []
    for p in sorted(CHAIN_DIR.glob('政策链-*.md')):
        body = '\n'.join(md_section_lines(read(p, ''), '关联卡片'))
        if f'政策卡片-{card}' in body:
            out.append(p.stem.replace('政策链-', ''))
    return out


def signals_of(title):
    """关联政策里点到这条政策的信号条目（整节里出现文号或题名即算）。"""
    ks, out = keys(title), []
    for sec in scan_dated(SIGNAL_DIR):
        lines = read(SIGNAL_DIR / sec['file'], '').split('\n')
        if like(ks, '\n'.join(lines[sec['start'] - 1:sec['end']])):
            out.append(sec)
    return out


def archives_of(sec):
    """一手存档：文号相同、或政策日期相同的那些文件。只报文件名，不报内容。"""
    ks, out = keys(sec['title']), []
    for p in sorted(ARTICLE_DIR.glob('*.md')):
        head = read(p, '')[:600]
        if like(ks, head) or f'政策日期: {sec["date"]}' in head:
            out.append(p.name)
    return out


def _show(sec, out):
    out.append(f'【政策】{sec["date"]} · {sec["title"]}')
    out.append(f'    {sec["file"]}:{sec["start"]}-{sec["end"]}'
               f'　（卡：{sec["card"]}）')
    chains = chains_of(sec['card'])
    out.append('  链：' + ('　／　'.join(chains) if chains else '（这张卡还没被任何链点到）'))
    sigs = signals_of(sec['title'])
    out.append(f'  信号：{len(sigs)} 条' if sigs else '  信号：0 条（这条政策还没有相关表态）')
    for s in sigs[:5]:
        out.append(f'    {s["date"]} · {s["title"]}　{s["file"]}:{s["start"]}-{s["end"]}')
    arcs = archives_of(sec)
    out.append(f'  一手存档：{len(arcs)} 份' if arcs else '  一手存档：0 份（原文未落盘）')
    out += [f'    raw/articles/{a}' for a in arcs[:5]]
    out.append('')


def run(argv=None):
    ap = argparse.ArgumentParser(prog='run.py trace', description='一条政策的全链：卡／链／信号／存档')
    ap.add_argument('keyword_pos', nargs='?', metavar='政策名', help='标题片段或文号')
    ap.add_argument('--card', help='只在这张卡里找（卡名以 index 为准）')
    args = ap.parse_args(list(argv or []))
    keyword = (args.keyword_pos or '').strip()

    if not keyword and not args.card:
        ap.print_help()
        summary('未给政策名或卡名，无结论')
        return 0

    hit = policies(keyword, args.card)
    out = []
    if not hit:
        out.append(f'✗ 没找到「{keyword or args.card}」对应的政策小节。')
        pool = [s['title'] for s in scan_dated(CARD_DIR) if not args.card
                or re.sub(r'^政策卡片-|\.md$', '', s['file']) == args.card]
        near = difflib.get_close_matches(keyword, pool, n=3, cutoff=0.3) if keyword else []
        out += [f'  最相近：{t}' for t in near] or ['  换一个词试试，或用 --card 先看这张卡里有什么。']
        print('\n'.join(out))
        summary(f'trace「{keyword or args.card}」：0 条政策')
        return 0

    out.append(f'══ 政策全链：「{keyword or args.card}」命中 {len(hit)} 条 ══\n')
    for sec in hit[:3]:
        _show(sec, out)
    if len(hit) > 3:
        out.append(f'（还有 {len(hit) - 3} 条同类政策，换更精确的词再查）')
    print('\n'.join(out))
    summary(f'trace「{keyword or args.card}」：{len(hit)} 条政策，'
            f'信号 {sum(len(signals_of(s["title"])) for s in hit[:3])} 条')
    return 0
