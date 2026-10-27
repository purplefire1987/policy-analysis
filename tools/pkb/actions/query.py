#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查库：给一个词、一条链、一段时间，回答「库里哪里有、在哪一行」。

为什么需要它
------------
这套工具原来十个动作**全在维护库**（存、检、修、派活），没有一个是「取」。
结果：规则、检查、台账都很厚，而回答一个政策问题仍要靠人肉 grep 四十万字符。
「存得住、检得出」不等于「查得到」——第三种能力要单独建。

它只做检索，不做判断：命中的原话照抄，不下结论、不合并同类项。
判断归周观点与分析报告，那两处有各自的判据。

用法（统一走入口）
----
    run.py query 出口管制                     # 全文：命中小节＋命中行号
    run.py query 出口管制 --since 2026-09-01  # 限时间窗
    run.py query --chain 金融强国             # 该链下全部政策小节
    run.py query --chain 金融强国 --since 2026-10-01
    run.py query 稀土 --full                  # 连小节正文一起打
    run.py query 房车 --notes                 # 连人的笔记（raw/notes）一起查

恒 exit 0：这是取素材的，不是校验器。查不到会明说「0 处」，不静默。
"""
import argparse
import re

from pkb.core import (CARD_DIR, CHAIN_DIR, NOTES_DIR, SIGNAL_DIR,
                      md_section_lines, read, scan_dated, scan_notes, summary)

DEFAULT_LIMIT = 40


def collect(include_notes=False):
    """政策小节、信号条目（可选笔记）各扫一遍，统一成一种形状（带文件、行号、卡名）。

    `kind` 分开是因为三者含义不同：政策是已落定的文件，信号是表态，笔记是**人写的
    东西**。读者一眼要能分清，所以输出里标【政策】/【信号】/【笔记】，不混排成一张表。
    笔记默认不进来：它是人的私稿，混进政策检索会让「这条政策库里有没有」变得可疑。
    """
    out = []
    for sec in scan_dated(CARD_DIR):
        sec.update(kind='政策', dir=CARD_DIR)
        sec['card'] = re.sub(r'^政策卡片-|\.md$', '', sec['file'])
        out.append(sec)
    for sec in scan_dated(SIGNAL_DIR):
        sec.update(kind='信号', dir=SIGNAL_DIR)
        sec['card'] = re.sub(r'^政策信号-|\.md$', '', sec['file'])
        out.append(sec)
    if include_notes:
        for sec in scan_notes(NOTES_DIR):
            sec.update(kind='笔记', dir=NOTES_DIR, card='')
            out.append(sec)
    return out


def chain_cards(name):
    """一条链的「关联卡片」节里点到的卡名。链是目录，卡片才是内容——按链查等于按卡查。"""
    p = CHAIN_DIR / f'政策链-{name}.md'
    if not p.exists():
        return None
    body = '\n'.join(md_section_lines(read(p, ''), '关联卡片'))
    return {m for m in re.findall(r'\[\[政策卡片-([^]#|]+)', body)}


def body_text(sec):
    """小节正文（含标题行）。查询要的是原话，不做摘要——摘要就是判断。"""
    p = sec['dir'] / sec['file']
    lines = read(p, '').split('\n')
    return lines, lines[sec['start'] - 1:sec['end']]


def hits(sec, kw):
    """返回命中处的行号（1 基，相对文件）。标题行本身不算命中——那是已知的。"""
    lines, chunk = body_text(sec)
    base = sec['start']
    return [base + i + 1 for i, line in enumerate(chunk[1:]) if kw.lower() in line.lower()]


def select(secs, args, cards):
    """按链、时间窗、关键词三层过滤。任一层没给就不筛，不猜默认值。"""
    picked = []
    for sec in secs:
        if cards is not None and sec['kind'] == '政策' and sec['card'] not in cards:
            continue
        if cards is not None and sec['kind'] != '政策':
            continue
        if args.since and sec['date'] < args.since:
            continue
        if args.until and sec['date'] > args.until:
            continue
        got = hits(sec, args.keyword) if args.keyword else []
        if args.keyword and not got:
            continue
        picked.append((sec, got))
    picked.sort(key=lambda x: (x[0]['date'], x[0]['title']), reverse=True)
    return picked


def show(picked, args):
    """一行一条：日期·标题，后面跟「文件:起-止」与命中行号。"""
    print(f'{"关键词「" + args.keyword + "」：" if args.keyword else ""}'
          f'命中 {len(picked)} 个小节'
          + (f'（只列最近 {args.limit} 个）' if len(picked) > args.limit else ''))
    if not picked:
        print('  （0 处。查不到就是查不到——换词、放宽时间窗，或这条政策库里确实没有）')
        return
    for sec, got in picked[:args.limit]:
        print(f'\n【{sec["kind"]}】{sec["date"] or "（无日期）"} · {sec["title"]}')
        print(f'    {sec["file"]}:{sec["start"]}-{sec["end"]}'
              + (f'　命中行 {", ".join(map(str, got))}' if got else ''))
        if args.full:
            _lines, chunk = body_text(sec)
            keep = ([line for i, line in enumerate(chunk) if (sec['start'] + i) in got]
                    if got else chunk)
            print('    ' + '\n    '.join(keep)[:args.limit_chars])


def run(argv=None):
    ap = argparse.ArgumentParser(prog='run.py query', description='查库：词／链／时间窗')
    ap.add_argument('keyword_pos', nargs='?', metavar='关键词', help='全文检索的词')
    ap.add_argument('--chain', help='只查一条链下的政策（如 金融强国）')
    ap.add_argument('--since', help='起始日期 YYYY-MM-DD（含）')
    ap.add_argument('--until', help='截止日期 YYYY-MM-DD（含）')
    ap.add_argument('--full', action='store_true', help='连小节正文一起打')
    ap.add_argument('--notes', action='store_true', help='连 raw/notes 里人的笔记一起查')
    ap.add_argument('--limit', type=int, default=DEFAULT_LIMIT, help=f'最多列几条（默认 {DEFAULT_LIMIT}）')
    ap.add_argument('--limit-chars', type=int, default=800, dest='limit_chars',
                    help='--full 时每条最多字符（默认 800）')
    args = ap.parse_args(list(argv or []))
    args.keyword = (args.keyword_pos or '').strip()

    if not (args.keyword or args.chain or args.since or args.until) and not args.notes:
        ap.print_help()
        summary('未给检索条件，无结论')
        return 0

    cards = None
    if args.chain:
        cards = chain_cards(args.chain)
        if cards is None:
            print(f'✗ 没有这条链：政策链-{args.chain}.md（链名以 index.md 为准）')
            summary(f'链不存在：{args.chain}')
            return 0
        if not cards:
            print(f'⚠ 政策链-{args.chain}.md 的「关联卡片」节没点到任何卡——链是空的')
    selected = select(collect(args.notes), args, cards)
    show(selected, args)

    scope = '／'.join(x for x in (
        f'链 {args.chain}' if args.chain else '',
        f'{args.since or "…"}~{args.until or "…"}' if (args.since or args.until) else '',
        f'词「{args.keyword}」' if args.keyword else '',
        '含笔记' if args.notes else '') if x) or '全库'
    summary(f'查询 {scope}：命中 {len(selected)} 个小节'
            + (f'（只列 {args.limit} 个）' if len(selected) > args.limit else ''))
    return 0
