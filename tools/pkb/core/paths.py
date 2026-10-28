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

# 目录名本身不是口径：它说的是「数据在哪」，不是「规则是什么」。
# 所以「政策卡片」「政策信号」这类字出现在 core 属正常——路径只能在这里定义一次，
# 换了库名就得改这里。真正的违规是名单/周号/域名（「金融强国」「2026-W40」「界面新闻」）
# 出现在 core 或 checks/actions，那由 check_docs 的口径单源扫描判，词典从 pkb/domain 现读。
CARD_DIR = VAULT / 'wiki' / '政策卡片'
CHAIN_DIR = VAULT / 'wiki' / '政策链'
SIGNAL_DIR = VAULT / 'wiki' / '政策信号'
WEEKLY_DIR = VAULT / 'wiki' / '周观点'
ANALYSIS_DIR = VAULT / 'wiki' / '分析'
OVERVIEW_DIR = VAULT / 'wiki' / '总览'
TEMPLATE_DIR = VAULT / 'templates'

# 一手存档区：只增不改（`run.py fetch` 唯一写入点，勘误另存新文件）。
# **只有「文件本身」能进这里**（2026-10-26 定）：官方报道与解读不进 raw/，
# 按内容归政策卡片或政策信号。判据住 domain（`domain/sources.py` 的 level）。
RAW_DIR = VAULT / 'raw'
ARTICLE_DIR = RAW_DIR / 'articles'
# 人的落笔处（2026-10-28）：对人写的内容开一个口——机器只读不写。
# 为什么放在 raw 下而不是 wiki 下：它不是「库的结论」，是**输入**。
# 周观点取消判断与定稿后，人的异议要有地方写，写在产出里就会被下次生成覆盖。
NOTES_DIR = RAW_DIR / 'notes'
# 抓取过程的临时落点：原页与附件缓存，供抽取失败时人工复核；不是库内容
CACHE_DIR = WORKSPACE / '.cache' / 'fetch'
# 临时目录（2026-10-28）：`tempfile` 的默认探测会把 cwd 当最后候选，
# 而探测失败时已在 cwd 留下随机名空文件。落点钉在这里，见 core/tmp.py。
TMP_DIR = WORKSPACE / '.cache' / 'tmp'

INDEX = VAULT / 'index.md'                      # 唯一入口：链名单＋受控词＋快照
AGENTS = VAULT / 'AGENTS.md'                    # 唯一规则来源
README = VAULT / 'README.md'
LOG = VAULT / 'log.md'

STATUS = OVERVIEW_DIR / '运行状态.md'            # 管「跑没跑」
LEDGER = OVERVIEW_DIR / '任务台账.md'            # 管「修没修」
COLLECT_LOG = OVERVIEW_DIR / '采集日志.md'       # 管「采到哪天」
CHECK_REPORT = OVERVIEW_DIR / '体检报告.md'
# 告警页（2026-10-28）：由 actions/alert 覆盖式重写，只列「要人知道的」。
# 为什么单独一页而不是只看体检输出：体检是流水（跑完就滚走了），
# 而「今天体检发现采集没跑」这件事需要留在页面上等人看见。
ALERT = OVERVIEW_DIR / '告警.md'
# 出库落点（2026-10-28）：交给别人的成品，**不放进 wiki/**——那是库内容，
# 混进导出件会让「库里有几个页面」这类读数失准，也会被断链扫描当成页面。
EXPORT_DIR = VAULT / '归档' / '导出'
WEEK_TEMPLATE = TEMPLATE_DIR / '周观点模板.md'
SIGNAL_TEMPLATE = TEMPLATE_DIR / '政策信号汇总模板.md'

# 提示词存档在库外（工作区），由 check_prompts 守「现行唯一」与引用有效性。
# 放在这里而不是库内路径区：它不在 VAULT 里，混排会让人以为是库内文档。
PROMPT_DIR = WORKSPACE / 'automation-prompts'
PROMPT_ARCHIVE = PROMPT_DIR / '旧版'          # 旧版只归档，不进「现行」判定

# 专家包在库外，但被 check_docs 校验，路径也只在此定义一次
EXPERT_DIR = Path.home() / '.workbuddy/plugins/marketplaces/my-experts/plugins/gov-policy-analyst'
EXPERT_MD = EXPERT_DIR / 'agents' / 'gov-policy-analyst.md'
EXPERT_SKILL = EXPERT_DIR / 'skills' / 'policy-kb-tools'
# 专家包里的 scripts **不是副本**，是指向 TOOLS 的符号链接（见 pkb/core/expert.py）
EXPERT_SCRIPTS = EXPERT_SKILL / 'scripts'
# 平台**实际加载**的是缓存里的那份（`plugins/cache/<名>/<版本>/`），不是 marketplaces 源。
# 2026-10-24 起这份缓存一直没跟上源，五天里专家定义缺「归档索引」——见 core/expert.py::cache_drift
EXPERT_CACHE = Path.home() / '.workbuddy/plugins/cache/my-experts/gov-policy-analyst'

# 扫描时要排除的目录
SKIP_DIRS = ('.obsidian', '.trash', '.git', '__pycache__')
