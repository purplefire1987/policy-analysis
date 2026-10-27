#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""近 N 天新增了什么：政策小节、信号条目、人的笔记，一行一条。

为什么需要它
------------
`status` 说采到哪天，`plan` 说该补什么，`query` 说某个词在哪——**没有一个回答
「这一周实际落了什么」**。周观点找素材、日常巡库、判断采集有没有空转，问的都是这一句。
此前只能看 mtime 猜：文件改了不等于内容新增，一次 frontmatter 修正就会让整张卡
显示成「今天动过」。

用法
----
    run.py recent                 # 近 7 天
    run.py recent --days 30
    run.py recent --kind 笔记      # 只看人写的东西

恒 exit 0：这是总览，不是校验。0 条就说 0 条——空窗本身是信息。
"""
import argparse
import datetime

from pkb.core import CARD_DIR, NOTES_DIR, SIGNAL_DIR, scan_dated, scan_notes, summary

KINDS = ('政策', '信号', '笔记')
DEFAULT_DAYS = 7


def gather():
    """三个来源统一成一种形状。笔记没写日期的单独留出来，不猜日期。"""
    out = []
    for sec in scan_dated(CARD_DIR):
        out.append(dict(sec, kind='政策'))
    for sec in scan_dated(SIGNAL_DIR):
        out.append(dict(sec, kind='信号'))
    for sec in scan_notes(NOTES_DIR):
        out.append(dict(sec, kind='笔记'))
    return out


def window(items, since, kinds):
    """按日期窗与类型过滤。无日期的条目丢掉并在摘要里说一句。"""
    picked, undated = [], 0
    for it in items:
        if kinds and it['kind'] not in kinds:
            continue
        if not it['date']:
            undated += 1
            continue
        if it['date'] >= since:
            picked.append(it)
    picked.sort(key=lambda x: (x['date'], x['kind'], x['title']), reverse=True)
    return picked, undated


def _where(it):
    return f'{it["file"]}:{it["start"]}-{it["end"]}'


def run(argv=None):
    ap = argparse.ArgumentParser(prog='run.py recent', description='近 N 天新增了什么')
    ap.add_argument('--days', type=int, default=DEFAULT_DAYS, help=f'回看天数（默认 {DEFAULT_DAYS}）')
    ap.add_argument('--kind', action='append', choices=KINDS,
                    help='只看某一类，可重复给；不给就是三类都要')
    ap.add_argument('--limit', type=int, default=60, help='最多列几条（默认 60）')
    args = ap.parse_args(list(argv or []))

    today = datetime.date.today()
    since = (today - datetime.timedelta(days=max(args.days, 1) - 1)).isoformat()
    picked, undated = window(gather(), since, args.kind)

    cnt = {k: sum(1 for it in picked if it['kind'] == k) for k in KINDS}
    print(f'最近 {args.days} 天（{since} ~ {today}）：'
          + ' · '.join(f'{k} {n}' for k, n in cnt.items() if n or not args.kind))
    if not picked:
        print('  （0 条。空窗本身是信息：可能是没采到，也可能是这几天确实没有新文件。）')
    for it in picked[:args.limit]:
        print(f'{it["date"]}  【{it["kind"]}】{it["title"]}')
        print(f'          {_where(it)}')
    if len(picked) > args.limit:
        print(f'  …还有 {len(picked) - args.limit} 条，加 --limit 或缩 --days')
    if undated:
        print(f'  ! 另有 {undated} 条没有日期（笔记的 `日期` 字段空着），未计入——'
              '不替它猜一个日期')

    summary(f'近 {args.days} 天：' + '／'.join(f'{k} {cnt[k]}' for k in KINDS if cnt[k] or not args.kind))
    return 0
