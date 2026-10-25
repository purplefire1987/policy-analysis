#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周观点素材预取：只列出指定 ISO 周窗口内的政策小节与信号条目，带行号范围。

为什么需要它
------------
周观点要「窗口内全部政策 + 窗口内全部信号」。若靠模型自己遍历，
读入量 = 33 张卡（约 32 万字符）+ 15 个信号页（约 7.8 万字符）≈ 40 万字符，
而实际用到的往往不到 5%。这正是本库最大的 token 漏斗，且随库增长而变坏。

本脚本把「找」和「读」拆开：先给出索引与**精确行号**，
再按行号读那一段（Read 带 offset/limit），
于是一个 30 万字符的库，一次预取只要一两千字符。

用法
----
    python3 week_sources.py 2026-W42            # 索引（带行号范围）
    python3 week_sources.py --week 2026-W42     # 同上
    python3 week_sources.py 2026-W42 --full     # 连正文一起打印（小周可用）
    python3 week_sources.py 2026-W42 --json     # 给程序用

恒 exit 0：这是取素材的，不是校验器。窗口内为空会明说，不静默。
"""
import argparse
import datetime
import json
import re

from pkb.core import CARD_DIR, SIGNAL_DIR, WEEKLY_DIR, summary

H3 = re.compile(r'^### (\d{4}-\d{2}-\d{2}) · (.+?)\s*$')


def week_range(week):
    """'2026-W42' → (周一, 周日)。周号非法返回 None。"""
    m = re.fullmatch(r'(\d{4})-W(\d{2})', week.strip())
    if not m:
        return None
    try:
        mon = datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None
    return mon, mon + datetime.timedelta(days=6)


def scan(dirpath, prefix):
    """扫一个目录下全部 md，按 `### 日期 · 标题` 切小节，返回
    [{'file','start','end','date','title'}]（行号 1 基）。"""
    out = []
    for p in sorted(dirpath.glob('*.md')):
        lines = p.read_text(encoding='utf-8', errors='ignore').split('\n')
        cur = None
        for i, l in enumerate(lines, 1):
            m = H3.match(l)
            if m:
                if cur:
                    cur['end'] = i - 1
                    out.append(cur)
                cur = {'file': p.name, 'start': i, 'end': len(lines),
                       'date': m.group(1), 'title': m.group(2)}
        if cur:
            cur['end'] = len(lines)
            out.append(cur)
    return out


def body_of(dirpath, sec, limit=None):
    lines = (dirpath / sec['file']).read_text(encoding='utf-8', errors='ignore').split('\n')
    chunk = '\n'.join(lines[sec['start'] - 1:sec['end']])
    if limit and len(chunk) > limit:
        chunk = chunk[:limit] + f'\n……（截断，共 {len(chunk)} 字符）'
    return chunk


def _print_index(week, lo, sun, cards, sigs, existing):
    """索引与行号：政策小节与信号条目各列一遍，这是写周观点的主材。"""
    print(f'{week}（{lo} ~ {sun}）  周观点已存在：{"是" if existing.exists() else "否"}')
    print(f'\n政策小节 {len(cards)} 个（速览表逐条列入，不得取舍）：')
    for s in cards:
        print(f'  {s["date"]} · {s["title"]}')
        print(f'      → {s["file"]}:{s["start"]}-{s["end"]}'
              + (f'（{s["end"] - s["start"] + 1} 行）'))
    print(f'\n信号条目 {len(sigs)} 个（第二节全部列入，不得只挑重要的）：')
    for s in sigs:
        print(f'  {s["date"]} · {s["title"]}')
        print(f'      → {s["file"]}:{s["start"]}-{s["end"]}')


def _print_full(cards, sigs, limit):
    """--full：连小节正文一起打，省掉逐个文件跳转。"""
    print('\n' + '=' * 58 + '\n政策正文\n' + '=' * 58)
    for s in cards:
        print(f'\n--- {s["date"]} · {s["title"]}（{s["file"]}）')
        print(body_of(CARD_DIR, s, limit))
    print('\n' + '=' * 58 + '\n信号正文\n' + '=' * 58)
    for s in sigs:
        print(f'\n--- {s["date"]} · {s["title"]}（{s["file"]}）')
        print(body_of(SIGNAL_DIR, s, limit))


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('week_pos', nargs='?', metavar='week', help='如 2026-W42')
    ap.add_argument('--week', dest='week', help='同上')
    ap.add_argument('--full', action='store_true', help='连小节正文一起打印')
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    ap.add_argument('--limit', type=int, default=1200, help='--full 时每段最多字符（默认 1200）')
    args = ap.parse_args(list(argv or []))
    week = args.week or args.week_pos
    if not week:
        ap.print_help()
        summary('未给周号，无结论')
        return 0
    rng = week_range(week)
    if not rng:
        print(f'✗ 周号格式不对：{week}（应形如 2026-W42）')
        summary(f'{week}：周号非法')
        return 0
    mon, sun = rng
    lo, hi = mon.isoformat(), sun.isoformat()

    cards = [s for s in scan(CARD_DIR, '政策卡片-') if lo <= s['date'] <= hi]
    sigs = [s for s in scan(SIGNAL_DIR, '政策信号-') if lo <= s['date'] <= hi]
    cards.sort(key=lambda s: s['date'])
    sigs.sort(key=lambda s: s['date'])

    existing = WEEKLY_DIR / f'周观点-{week}.md'
    if args.json:
        print(json.dumps({'week': week, 'from': lo, 'to': hi,
                          'policies': cards, 'signals': sigs,
                          'weekly_exists': existing.exists()},
                         ensure_ascii=False, indent=1))
        return 0

    _print_index(week, lo, sun, cards, sigs, existing)
    if args.full:
        _print_full(cards, sigs, args.limit)

    if not cards and not sigs:
        print('\n⚠ 窗口内既无政策也无信号。先查采集是否漏采（[[采集日志]]），'
              '不得直接写「本周无新增」。')
    summary(f'{week}（{lo}~{sun}）：政策 {len(cards)} 条、信号 {len(sigs)} 条'
            + ('，已有周观点文件' if existing.exists() else '，周观点未生成'))
    if not args.full:
        print('\n（只给了索引与行号。按行号读那一段即可，不必整卡读——'
              '一整张卡可能有 3 万字符，一个 30 行小节只有 1 千。）')
    return 0
