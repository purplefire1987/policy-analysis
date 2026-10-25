#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三页状态快照：采到哪天 / 跑没跑 / 修没修 + 下一步。

为什么独立成脚本：这段逻辑原本长在 run.py 里（action_status），
三页的格式一变就要改入口——与「叶子脚本自由生长、入口只做调度」的设计相悖。
2026-10-25 外移。入口 `run.py status` 只是转发调用本脚本。

只读三页：采集日志（采到哪天）、运行状态（跑没跑）、任务台账（修没修）。
恒 exit 0：它是给人看的摘要，不是校验器。
"""

import re
import sys

from lib import COLLECT_LOG, STATUS, LEDGER


def main():
    print('\n' + '=' * 62)
    print('当前状态')
    print('=' * 62)

    # 1. 采到哪天 —— 采集日志里最近一条「第 N 轮」
    last_day, last_round = '（未读到）', '（未读到）'
    if COLLECT_LOG.exists():
        rows = [l for l in COLLECT_LOG.read_text(encoding='utf-8').split('\n')
                if l.strip().startswith('|') and '第' in l and '轮' in l]
        for l in rows:
            cells = [c.strip() for c in l.strip().strip('|').split('|')]
            if len(cells) >= 2 and re.match(r'\d{4}-\d{2}-\d{2}', cells[0]):
                # 「手工补录（不占轮次）」不是采集轮次，不能当 D——
                # 否则会把已补过的日期当成采集进度（AGENTS 里的取 D 规则）
                if '手工补录' in cells[1] or '不占轮次' in cells[1]:
                    continue
                last_day, last_round = cells[0], cells[1]
                break
    print(f'采到哪天：{last_day}   最近轮次：{last_round}')

    # 2. 跑没跑 —— 运行状态的三行灯
    lights = []
    if STATUS.exists():
        for l in STATUS.read_text(encoding='utf-8').split('\n'):
            if l.strip().startswith('|') and any(k in l for k in ('采集', '体检', '周观点')):
                cells = [c.strip() for c in l.strip().strip('|').split('|')]
                if len(cells) >= 3 and re.search(r'🔴|🟡|🟢', l):
                    light = next((c for c in cells if c in ('🔴', '🟡', '🟢')), '?')
                    lights.append(f'{cells[0]}{light}')
    print('跑没跑　：' + ('  '.join(lights) if lights else '（未读到状态行）'))

    # 3. 修没修 —— 任务台账未闭环项
    open_n, overdue = 0, 0
    if LEDGER.exists():
        txt = LEDGER.read_text(encoding='utf-8')
        for l in txt.split('\n'):
            if l.strip().startswith('|') and re.search(r'T-\d{8}-\d{2}', l):
                if re.search(r'🆕|🟡|⏳', l):
                    open_n += 1
                if re.search(r'🆕|🟡', l):
                    overdue += 1
    print(f'修没修　：未闭环 {open_n} 项（其中待办/在办 {overdue} 项）')

    print('\n下一步：')
    print('  先跑  python3 tools/run.py check   （看有没有硬错误）')
    print('  再跑  python3 tools/run.py fix     （能自动修的一次改完）')
    print('  然后  python3 tools/run.py plan    （领本轮的活）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
