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
    OVERVIEW_DIR, TEMPLATE_DIR,
    INDEX, AGENTS, README, LOG,
    STATUS, LEDGER, COLLECT_LOG, CHECK_REPORT, WEEK_TEMPLATE,
    EXPERT_DIR, EXPERT_MD, SKIP_DIRS,
)
from .fs import (                                     # noqa: F401
    md_files, read, write, digest, all_names, py_files,
)
from .fm import (                                     # noqa: F401
    FM_RE, parse_fm, set_fm_field,
)
from .md import (                                     # noqa: F401
    SECTION_HEAD, extract_sections, md_section_lines, table_rows,
    similar, iso_week, parse_date, span,
)
from .report import (                                 # noqa: F401
    ok, err, warn, info, section,
    SUMMARY_MARK, summary, Verdict, Result, Reporter,
)

__all__ = [
    # 路径
    'VAULT', 'WORKSPACE', 'TOOLS',
    'CARD_DIR', 'CHAIN_DIR', 'SIGNAL_DIR', 'WEEKLY_DIR', 'ANALYSIS_DIR',
    'OVERVIEW_DIR', 'TEMPLATE_DIR',
    'INDEX', 'AGENTS', 'README', 'LOG',
    'STATUS', 'LEDGER', 'COLLECT_LOG', 'CHECK_REPORT', 'WEEK_TEMPLATE',
    'EXPERT_DIR', 'EXPERT_MD', 'SKIP_DIRS',
    # 读写
    'md_files', 'read', 'write', 'digest', 'all_names', 'py_files',
    # frontmatter
    'FM_RE', 'parse_fm', 'set_fm_field',
    # markdown 与日期
    'SECTION_HEAD', 'extract_sections', 'md_section_lines', 'table_rows',
    'similar', 'iso_week', 'parse_date', 'span',
    # 输出与判定
    'ok', 'err', 'warn', 'info', 'section',
    'SUMMARY_MARK', 'summary', 'Verdict', 'Result', 'Reporter',
]
