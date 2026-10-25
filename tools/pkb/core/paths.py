#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径与常量：全库唯一定义处。

为什么单独一个模块：2026-10-24 之前，`VAULT` 那条绝对路径在 8 个脚本里各写了一遍，
改一次仓库位置要动 8 处，而其中任何一处漏改都不会报错——这正是本库反复出现的
「副本漂移」。现在只有这里能拼路径，其余模块 `from .paths import`。
"""
import os
from pathlib import Path

# 允许环境变量覆盖：专家包内带的是同一份脚本，换台机器（或换库位置）时
# 只要设 POLICY_KB_VAULT / POLICY_KB_WORKSPACE，不必改代码。
# 默认值仍是本机的绝对路径——绝大多数调用方什么都不用设。
VAULT = Path(os.environ.get('POLICY_KB_VAULT', '/Users/Mr_Zhou/Documents/知识库/资料库'))
WORKSPACE = Path(os.environ.get('POLICY_KB_WORKSPACE',
                                '/Users/Mr_Zhou/WorkBuddy/2026-09-23-07-58-53'))   # 工具、备份、报告落点
# 本文件在 tools/pkb/core/paths.py → 上溯两级才是 tools/
TOOLS = Path(__file__).resolve().parents[2]

CARD_DIR = VAULT / 'wiki' / '政策卡片'
CHAIN_DIR = VAULT / 'wiki' / '政策链'
SIGNAL_DIR = VAULT / 'wiki' / '政策信号'
WEEKLY_DIR = VAULT / 'wiki' / '周观点'
ANALYSIS_DIR = VAULT / 'wiki' / '分析'
OVERVIEW_DIR = VAULT / 'wiki' / '总览'
TEMPLATE_DIR = VAULT / 'templates'

INDEX = VAULT / 'index.md'                      # 唯一入口：链名单＋受控词＋快照
AGENTS = VAULT / 'AGENTS.md'                    # 唯一规则来源
README = VAULT / 'README.md'
LOG = VAULT / 'log.md'

STATUS = OVERVIEW_DIR / '运行状态.md'            # 管「跑没跑」
LEDGER = OVERVIEW_DIR / '任务台账.md'            # 管「修没修」
COLLECT_LOG = OVERVIEW_DIR / '采集日志.md'       # 管「采到哪天」
CHECK_REPORT = OVERVIEW_DIR / '体检报告.md'
WEEK_TEMPLATE = TEMPLATE_DIR / '周观点模板.md'

# 专家包在库外，但被 check_docs 校验，路径也只在此定义一次
EXPERT_DIR = Path.home() / '.workbuddy/plugins/marketplaces/my-experts/plugins/gov-policy-analyst'
EXPERT_MD = EXPERT_DIR / 'agents' / 'gov-policy-analyst.md'

# 扫描时要排除的目录
SKIP_DIRS = ('.obsidian', '.trash', '.git', '__pycache__')
