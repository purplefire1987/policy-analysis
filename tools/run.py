#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策知识库 —— 统一入口。

设计目的：让「采集 / 存储 / 链接 / 分析 / 产出 / 自检」六个环节共用一条命令，
不再各自拼脚本路径。**本文件只做调度，不含任何判断**——判定在 pkb/checks、
口径在 pkb/domain、通用件在 pkb/core、动作实现在 pkb/actions。

用法
----
    python3 tools/run.py status     当前状态（采到哪天 / 跑没跑 / 修没修 + 下一步）   恒 exit 0
    python3 tools/run.py check      全量自检                                          有问题 exit 1
    python3 tools/run.py fix        一次性修复（所有能自动修的，一次改完）             恒 exit 0
    python3 tools/run.py plan       派活清单（本轮该做什么，按执行顺序）               恒 exit 0
    python3 tools/run.py week 2026-W42  周观点素材预取（索引＋行号，--full 连正文）     恒 exit 0
    python3 tools/run.py fetch      抓一手源：政策原文落进 raw/articles（默认今天+昨天） 欠账列明细 exit 0
    python3 tools/run.py link       把专家包入口接回本体（符号链接，杜绝副本漂移）   有漂移 exit 1
    python3 tools/run.py sources    来源合规扫描（--apply 才写盘）                     有问题 exit 1
    python3 tools/run.py list       列出包内检查项、动作与用途（不用记模块名）

参数透传（提示词里因此不必再写具体模块路径）
----------------------------------------
    python3 tools/run.py check --since 2026-10-20    只把 --since 交给认得它的检查
    python3 tools/run.py check 2026-W43              周号交给认得 --week 的检查
    python3 tools/run.py check --week 2026-W43       同上
    python3 tools/run.py check --only docs           只跑名字含 docs 的检查，并打全量明细
    python3 tools/run.py check --full                全部跑并打全量（诊断用，费 token）

约定
----
* **新增检查**：在 `pkb/checks/` 写一个 `run(argv) -> Result` 的模块，再在
  `pkb/checks/__init__.py` 的 `REGISTRY` 加一行。不用改本文件，也不用改提示词。
* **新增动作**：在 `pkb/actions/` 写 `run(argv) -> int`，在下面 `ACTIONS` 加一行。
* 路径只在 `pkb/core/paths.py` 定义一次；口径只在 `pkb/domain/` 定义一次。
* `status` / `plan` 是给人看的，永远不阻断（恒 exit 0），不要用它们的退出码判成败。
* 规则只有一处：库内 `AGENTS.md`。本文件不复述规则，只负责调度。
"""
import sys

from pkb.actions import (check, fetch, fix, ledger, link, plan, query, recent,
                         sources, status, trace, week)
from pkb.actions import list as listing

USAGE = __doc__

ACTIONS = {
    'status':  (status.run,  '当前状态：采到哪天 / 跑没跑 / 修没修'),
    'check':   (check.run,   '全量自检，有问题 exit 1（可带 --since / 周号 / --only / --full）'),
    'fix':     (fix.run,     '一次性修复所有能自动修的'),
    'plan':    (plan.run,    '派活清单'),
    'week':    (week.run,    '周观点素材预取：某周政策与信号索引＋行号'),
    'query':   (query.run,   '查库：按词／链／时间窗检索，给文件与行号（只检索不判断；--notes 连笔记）'),
    'trace':   (trace.run,   '一条政策的全链：卡／链／信号／一手存档，只连关系不下结论'),
    'recent':  (recent.run,  '近 N 天新增了什么（政策小节／信号条目／人的笔记）'),
    'fetch':   (fetch.run,   '抓一手源：卡片里的政策原文落进 raw/articles（默认今天+昨天）'),
    'ledger':  (ledger.run,  '台账清理：到期归档／停滞退回（默认只看，--apply 写盘）'),
    'link':    (link.run,    '专家包入口接回本体（符号链接，--check 只核对）'),
    'sources': (sources.run, '来源合规扫描（--apply 写盘）'),
    'list':    (listing.run, '列出包内检查项、动作与用途'),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(USAGE)
        print('可用动作：')
        for k, (_, d) in ACTIONS.items():
            print(f'  {k:<9} {d}')
        return 0
    act, rest = argv[0], argv[1:]
    if act not in ACTIONS:
        print(f'未知动作：{act}')
        print('可用动作：' + ' / '.join(ACTIONS))
        return 2
    return ACTIONS[act][0](rest)


if __name__ == '__main__':
    sys.exit(main())
