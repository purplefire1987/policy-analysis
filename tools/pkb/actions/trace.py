#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条政策的全链：政策 → 卡 → 链 → 信号 → 一手存档 → 别的卡提到它。

为什么再加一个检索动作
------------------
`query` 能回答「这个词出现在哪些行」，回答不了「这条政策在库里挂在哪」。
后一个问题要跨三种文件：卡（内容）、链（目录）、信号与存档（旁证）。
它们的关系全躺在 frontmatter 与「关联卡片」节里，此前只能人工三处翻。

**「别的卡提到它」是反查出来的，不是人写的链接**：库里一处卡间 `[[政策卡片-X]]`
都没有（卡内 39 处链接全部指向政策链），说明这层关系从来没打算用链接表达。
所以按**文号**在别的卡正文里找——文号唯一，出现即指认；题名不行，
正文里常被简称成「《指导意见》」「该文件」。同卡内的小节提到不算，
那层关系在卡内就近可读。手写链接的方案没有采纳，理由写在 `mentioned_by` 里。

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
from functools import lru_cache

from pkb.core import (ARTICLE_DIR, CARD_DIR, CHAIN_DIR, SIGNAL_DIR,
                      md_section_lines, read, scan_dated, summary)

DOC_NO = re.compile(r'〔\d{4}〕\s*\d+\s*号')
PAREN = re.compile(r'[（(].*?[）)]')
PUNCT = re.compile(r'[《》〈〉「」“”"\'\-—－、，,。．\.：:；;（）()〔〕【】\s]')


@lru_cache(maxsize=None)
def _text(path):
    """按文件缓存正文。一张卡里几十个小节，不缓存就是同一个文件读几十遍——
    跨卡反查是 157 × 157 的两层循环，第一次跑直接把进程拖死过。"""
    return read(path, '')


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
    """一手存档：**按文号或题名认**，不按日期认。

    为什么日期不能当判据：存档文件名是 `日期_机关_文号_标题`，同一天可能有十几份文件。
    早先写成「文号命中 **或** 政策日期相同」，取证结果是把同一天一份无关的中小企业
    通知算成了这条政策的原文——**认错一份存档比查不到更坏**，因为它会让人以为
    物证已经落了盘。同日的其余存档单列成「同期另有」，只说存在，不替你认。
    """
    ks, out, same_day = keys(sec['title']), [], []
    for p in sorted(ARTICLE_DIR.glob('*.md')):
        head = _text(p)[:600]
        if like(ks, head):
            out.append(p.name)
        elif f'政策日期: {sec["date"]}' in head:
            same_day.append(p.name)
    return out, same_day


def _body(sec):
    lines = _text(CARD_DIR / sec['file']).split('\n')
    return '\n'.join(lines[sec['start'] - 1:sec['end']])


def mentioned_by(sec):
    """别的卡里提到这条政策的地方：**按文号反查，不靠人写链接**。

    为什么是这条路而不是在卡片正文里手写 `[[政策卡片-X]]`：
      ① 库里现在一处这样的链接都没有（39 处卡内链接全部指向政策链），
         说明「卡与卡的关系」从来没打算用链接表达，加它是新增一份关系账；
      ② 关系其实已经写在正文里了——「与旧政策的关系」那一栏点名了它承继、
         修订、替代了谁；缺的不是记录，是**能按它反查**；
      ③ 手写链接没人核：链页、信号「关联政策」已经各自记了一遍关系，
         再加一份，第三次漂移照样没人发现。

    按文号而不按题名：正文里题名常被简称（「《指导意见》」「该文件」），
    按题名会漏一半、错一半；文号唯一，出现即指认。
    """
    text = sec['title'] + '\n' + _body(sec)
    nos = {norm(m.group(0)) for m in DOC_NO.finditer(text)}
    if not nos:
        return []
    out = []
    for other in scan_dated(CARD_DIR):
        if other['file'] == sec['file']:
            continue                      # 同一张卡内不算「卡之间」，那层关系在卡内就近可读
        card = re.sub(r'^政策卡片-|\.md$', '', other['file'])
        if like(nos, _body(other)):
            out.append({**other, 'card': card})
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
    arcs, same_day = archives_of(sec)
    out.append(f'  一手存档：{len(arcs)} 份' if arcs else '  一手存档：0 份（原文未落盘）')
    out += [f'    raw/articles/{a}' for a in arcs[:5]]
    if not arcs and same_day:
        out.append(f'    同日另有 {len(same_day)} 份存档，对不上这条（不替你认）：'
                   f'{same_day[0][:44]}')
    refs = mentioned_by(sec)
    if refs:
        out.append(f'  别的卡提到它：{len(refs)} 处（按文号反查，不是人写的链接）')
        out += [f'    {r["card"]} · {r["date"]} {r["title"][:36]}'
                f'　{r["file"]}:{r["start"]}' for r in refs[:4]]
    elif not DOC_NO.search(sec['title'] + _body(sec)):
        out.append('  别的卡提到它：查不了（这条政策正文里没有文号）')
    else:
        out.append('  别的卡提到它：0 处（文号在别的卡里没有出现）')
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
    if args.card:
        from pkb.core.fm import parse_fm
        fm, _b = parse_fm(_text(CARD_DIR / f'政策卡片-{args.card}.md'))
        kws = fm.get('关键词')
        if isinstance(kws, list) and kws:
            out.append(f'这张卡的关键词：{"、".join(str(k) for k in kws)}\n')
    for sec in hit[:3]:
        _show(sec, out)
    if len(hit) > 3:
        out.append(f'（还有 {len(hit) - 3} 条同类政策，换更精确的词再查）')
    print('\n'.join(out))
    summary(f'trace「{keyword or args.card}」：{len(hit)} 条政策，'
            f'信号 {sum(len(signals_of(s["title"])) for s in hit[:3])} 条')
    return 0
