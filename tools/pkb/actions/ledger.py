#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：ledger —— 台账清理。四态之间那一步没人推，本动作来推。

台账「只增不删」是对的：**「上周有、这周没了」必须能区分是修好了还是压根没写**。
但只增不清会烂——2026-10-26 清理时看到 12 条 ✅ 与四条堆在未闭环项里，
有的 🟡 写了「在办」却四天没动过一行。状态与事实脱节，账本就失去读的价值。

**默认只看，`--apply` 才写盘**。三件事里只有前两件自动做：

1. **归档**：✅ 且「最近更新」距今 ≥ 90 天 → 整行搬进「六、关闭记录」，
   未闭环项表下留一行汇总（不删历史，只换位置——第六节就是为这件事设的）。
2. **退回**：🟡 且「最近更新」距今 > 3 天 → 改回 🆕，备注追加退回原因。
   AGENTS 早给了这个权力（「连续三天没动等于没记」），此前没有一次执行过。
3. **只报不改**：⏳ 待验超期、备注里「观察窗口 YYYY-MM」已到——
   验没验、判没判只有人能定，脚本替人下结论就是编造。

为什么不并进 `fix`：fix 修的是「机械可判的错」，这里是**搬历史**。
写错会把归档搬串行；单列一个动作 + 默认 dry-run + 幂等（第二次跑 0 条），才敢让体检每期跑。

退出码：恒 0（整理不是故障）；读不到台账或 `--apply` 写盘失败才 1。
"""
import argparse
import datetime
import re

from pkb.core import LEDGER, read, write, banner
from pkb.checks.docs.ledger import triage       # 判定与执行共用一份，actions→checks 是下行

from pkb.domain import ARCHIVE_DAYS

TITLES = {'archive': '该归档', 'stale': '该退回 🆕',
          'overdue': '待验过期', 'observe': '观察窗口已到'}


def _bounds(lines, key):
    """`## ` 节的 [start, end) 行号（不含标题行）；找不到返回 None。"""
    start = next((i for i, l in enumerate(lines) if l.startswith('## ') and key in l), None)
    if start is None:
        return None
    end = next((i for i, l in enumerate(lines[start + 1:], start + 1) if l.startswith('## ')),
               len(lines))
    return start + 1, end


def _archive(lines, rows, limit):
    """整行搬进「六、关闭记录」。先插高行号、再删低行号——倒着改不会互相挪位。"""
    b6 = _bounds(lines, '关闭记录')
    if not b6:
        return 0
    tbl = [i for i in range(*b6) if lines[i].lstrip().startswith('|')]
    if not tbl:
        return 0
    new = [f'| {c[0]} | {c[1]} | {c[6]} | {c[2]} | {c[7]} |' for _i, c, _w in rows]
    ph = next((i for i in tbl if '—' in lines[i]), None)
    if ph is not None:
        lines[ph:ph + 1] = new
    else:
        lines[tbl[-1] + 1:tbl[-1] + 1] = new
    return len(new)


def _notice(lines, ids, limit):
    """未闭环项表下留一行「已归档」汇总；已有则合并重写，不叠第二行。"""
    b2 = _bounds(lines, '未闭环项')
    if not b2:
        return
    for i in range(*b2):
        if lines[i].startswith('> **已归档**'):
            old = set(re.findall(r'T-\d{8}-\d{2}', lines[i]))
            lines[i] = _notice_line(sorted(old | set(ids)), limit)
            return
    tbl = [i for i in range(*b2) if lines[i].lstrip().startswith('|')]
    if tbl:
        lines[tbl[-1] + 1:tbl[-1] + 1] = ['', _notice_line(sorted(ids), limit)]


def _notice_line(ids, limit):
    return (f'> **已归档**（满 {limit} 天，整行移入「六、关闭记录」）：'
            + '、'.join(ids))


def _print(plan, limit):
    total = sum(len(v) for v in plan.values())
    for n, (key, title) in enumerate(TITLES.items(), 1):
        head = f'【{n}·{title}' + (f'（≥{limit} 天）】' if key == 'archive' else '】')
        print(f'\n{head}{len(plan[key])} 条')
        for _i, c, why in plan[key]:
            print(f'  {c[0]}｜{why}｜{c[5]}')
    return total


def run(argv=None):
    ap = argparse.ArgumentParser(description='台账清理：到期归档 / 停滞退回（默认只看）')
    ap.add_argument('--apply', action='store_true', help='写盘（不加只打印差量）')
    ap.add_argument('--days', type=int, default=ARCHIVE_DAYS, help='✅ 满多少天归档')
    args = ap.parse_args(list(argv or []))

    text = read(LEDGER, '')
    if not text:
        print(f'✗ 读不到任务台账：{LEDGER}')
        return 1
    banner(f'台账清理 · {datetime.date.today()}'
           + ('' if args.apply else '（只看，不写盘）'))
    plan = triage(text)
    total = _print(plan, args.days)

    if not args.apply:
        print(f'\n共 {total} 条待处理。确认无误后加 `--apply` 写盘。'
              if total else '\n台账干净：没有到期该归档的、也没有写了在办却不动的。')
        return 0

    lines = text.split('\n')
    moved = _archive(lines, plan['archive'], args.days)
    ids = [c[0] for _i, c, _w in plan['archive']]
    drop = {i for i, _c, _w in plan['archive']}
    for i in sorted(drop, reverse=True):
        del lines[i]
    if ids:
        _notice(lines, ids, args.days)
    back = 0
    for i, c, why in plan['stale']:
        c = list(c)
        c[5] = '🆕 待办'
        c[7] = f'{c[7]}（{datetime.date.today()} 退回 🆕：{why}）'
        lines[i] = '| ' + ' | '.join(c) + ' |'
        back += 1
    write(LEDGER, '\n'.join(lines))
    print(f'\n已写盘：归档 {moved} 条、退回 {back} 条。'
          f' 待验过期与观察窗口两项只报不改（要不要验只能人判）。')
    return 0
