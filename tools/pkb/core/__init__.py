#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkb.core —— 无业务判断的通用件（路径、读写、frontmatter、Markdown、输出）。

依赖规则：core 不含口径（名单／枚举／判据），也不许 import 上层（domain/checks/actions）。
目录名与结构名不算口径——`wiki/政策卡片` 是数据在哪，`### 日期 · 标题` 是长什么样；
按字面词禁「政策」会连路径常量都写不出来，而路径本来就该只在这里定义一次。
一旦口径进了共用层，改口径就要动代码，那是把规则藏进了实现。
"""
from .paths import (                                  # noqa: F401
    VAULT, WORKSPACE, TOOLS,
    CARD_DIR, CHAIN_DIR, SIGNAL_DIR, WEEKLY_DIR, ANALYSIS_DIR,
    OVERVIEW_DIR, TEMPLATE_DIR, RAW_DIR, ARTICLE_DIR, CACHE_DIR,
    INDEX, AGENTS, README, LOG,
    STATUS, LEDGER, JUDGE_LEDGER, COLLECT_LOG, CHECK_REPORT, WEEK_TEMPLATE,
    PROMPT_DIR, PROMPT_ARCHIVE,
    EXPERT_DIR, EXPERT_MD, EXPERT_SKILL, EXPERT_SCRIPTS, SKIP_DIRS,
)
from .fs import (                                     # noqa: F401
    md_files, read, write, digest, all_names, py_files, action_names,
)
from . import expert                                  # noqa: F401
from . import web, doc                                # noqa: F401
from .fm import (                                     # noqa: F401
    FM_RE, parse_fm, set_fm_field,
)
from .md import (                                     # noqa: F401
    SECTION_HEAD, extract_sections, md_section_lines, table_rows,
    similar, iso_week, parse_date, span,
)
from .report import (                                 # noqa: F401
    ok, err, warn, info, section, banner,
    SUMMARY_MARK, summary, Verdict, Result, Reporter,
)

__all__ = [
    # 路径
    'VAULT', 'WORKSPACE', 'TOOLS',
    'CARD_DIR', 'CHAIN_DIR', 'SIGNAL_DIR', 'WEEKLY_DIR', 'ANALYSIS_DIR',
    'OVERVIEW_DIR', 'TEMPLATE_DIR', 'RAW_DIR', 'ARTICLE_DIR', 'CACHE_DIR',
    'INDEX', 'AGENTS', 'README', 'LOG',
    'STATUS', 'LEDGER', 'JUDGE_LEDGER', 'COLLECT_LOG', 'CHECK_REPORT', 'WEEK_TEMPLATE',
    'PROMPT_DIR', 'PROMPT_ARCHIVE',
    'EXPERT_DIR', 'EXPERT_MD', 'EXPERT_SKILL', 'EXPERT_SCRIPTS', 'SKIP_DIRS',
    # 专家包入口形态判定（链接／副本／链错／缺失）
    'expert',
    # 抓页与附件转文本（无口径，只有机制）
    'web', 'doc',
    # 读写
    'md_files', 'read', 'write', 'digest', 'all_names', 'py_files', 'action_names',
    # frontmatter
    'FM_RE', 'parse_fm', 'set_fm_field',
    # markdown 与日期
    'SECTION_HEAD', 'extract_sections', 'md_section_lines', 'table_rows',
    'similar', 'iso_week', 'parse_date', 'span',
    # 输出与判定
    'ok', 'err', 'warn', 'info', 'section', 'banner',
    'SUMMARY_MARK', 'summary', 'Verdict', 'Result', 'Reporter',
]
