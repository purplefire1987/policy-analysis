#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三页状态快照：采到哪天 / 跑没跑 / 修没修 + 下一步。

为什么独立成脚本：这段逻辑原本长在 run.py 里（action_status），
三页的格式一变就要改入口——与「叶子脚本自由生长、入口只做调度」的设计相悖。
2026-10-25 外移。入口 `run.py status` 只是转发调用本脚本。

只读三页：采集日志（采到哪天）、运行状态（跑没跑）、任务台账（修没修）。
恒 exit 0：它是给人看的摘要，不是校验器。

**2026-10-28 晚：接住原来的 `preflight`**
----------------------------------------
原先单独有个 `run.py preflight` 回答「我读到的是不是最新数据」。但一条只在该用
时想得起来的命令，等于没有——三个自动化跑的是 `status`，不是 `preflight`。
现在把那一句结论并进这里：**判断依据（采到哪天）本来就已经读出来了，再问一次
纯属多余**。「数据不是当天」时直接写明报告里必须标注截止日。
"""

import datetime
import re

from pkb.core import COLLECT_LOG, STATUS, LEDGER

DASH = '（未读到）'


def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def collect_upto():
    """采集日志里最近一条「第 N 轮」→ (日期, 轮次)。

    「手工补录（不占轮次）」不是采集轮次，不能当 D——否则会把已补过的日期
    当成采集进度（AGENTS 里的取 D 规则）。
    """
    if not COLLECT_LOG.exists():
        return DASH, DASH
    for line in COLLECT_LOG.read_text(encoding='utf-8').split('\n'):
        s = line.strip()
        if not (s.startswith('|') and '第' in s and '轮' in s):
            continue
        cells = _cells(line)
        if len(cells) < 2 or not re.match(r'\d{4}-\d{2}-\d{2}', cells[0]):
            continue
        if '手工补录' in cells[1] or '不占轮次' in cells[1]:
            continue
        return cells[0], cells[1]
    return DASH, DASH


def freshness(day, today=None):
    """→ (一句话结论, 补充说明)。判据是「读到的数据是不是今天的」。"""
    today = today or datetime.date.today().isoformat()
    if day == today:
        return '数据截止：当天 —— 可以开跑，产出不必标注截止日', ''
    if re.match(r'\d{4}-\d{2}-\d{2}', day):
        return (f'数据截止：{day}（不是当天）—— 报告里**必须**写明「数据截止 {day}」，',
                '　　　　　读者看不出数据旧，就会当成今天的新情况读。')
    return '数据截止：采集日志里读不到日期 —— 先确认采集有没有在写日志', ''


def lights():
    """运行状态里采集／体检／周观点三行灯 → ['采集🟢', ...]。"""
    out = []
    if not STATUS.exists():
        return out
    for line in STATUS.read_text(encoding='utf-8').split('\n'):
        s = line.strip()
        if not (s.startswith('|') and any(k in s for k in ('采集', '体检', '周观点'))):
            continue
        cells = _cells(line)
        if len(cells) >= 3 and re.search(r'🔴|🟡|🟢', s):
            out.append(f'{cells[0]}{next(c for c in cells if c in ("🔴", "🟡", "🟢"))}')
    return out


def open_items():
    """任务台账未闭环项 → (未闭环数, 待办／在办数)。"""
    if not LEDGER.exists():
        return 0, 0
    total = doing = 0
    for line in LEDGER.read_text(encoding='utf-8').split('\n'):
        s = line.strip()
        if not (s.startswith('|') and re.search(r'T-\d{8}-\d{2}', s)):
            continue
        if re.search(r'🆕|🟡|⏳', s):
            total += 1
        if re.search(r'🆕|🟡', s):
            doing += 1
    return total, doing


def run(argv=None):
    print('\n' + '=' * 62)
    print('当前状态')
    print('=' * 62)

    day, rnd = collect_upto()
    print(f'采到哪天：{day}   最近轮次：{rnd}')

    head, tail = freshness(day)
    print(head)
    if tail:
        print(tail)

    marks = lights()
    print('跑没跑　：' + ('  '.join(marks) if marks else '（未读到状态行）'))

    total, doing = open_items()
    print(f'修没修　：未闭环 {total} 项（其中待办/在办 {doing} 项）')

    print('\n下一步：')
    print('  先跑  python3 tools/run.py check   （看有没有硬错误）')
    print('  再跑  python3 tools/run.py fix     （能自动修的一次改完）')
    print('  然后  python3 tools/run.py plan    （领本轮的活）')
    return 0

