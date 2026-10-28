#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkb.domain —— 口径层：名单、枚举、对应关系。

规则：**只有数据与纯函数**。不许读盘、不许打印、不许 import 上层。
`check_*` 里出现字面量 '2026-W40'、'金融强国'、'jiemian.com' 都算违规——
它们必须住在这里，否则改口径要翻遍所有脚本。
"""
from .blacklist import (                               # noqa: F401
    BLACK, BAD_SUBJECT, DOC_MUST_MENTION, is_bad,
)
from .fields import (                                   # noqa: F401
    DOMAINS, STAT_DOMAINS, IMPACTS, STATUSES, REQUIRED_FIELDS, CARD_SIZE_WARN,
    VCS_STALE_DAYS,
    ANALYSIS_TYPES, ANALYSIS_WORD_LIMIT, ANALYSIS_SPINE,
    STANCES, STANCE_MIN, ARCHIVE_DATE_TOLERANCE,
)
# `ledger.py` 的 LEDGER_TYPES／LEDGER_OWNERS **故意不从包里再导出**（2026-10-26）：
#   口径扫描（checks/docs/literals）以「代码里的字符串常量值与 domain 某个取值完全相同」
#   为判据，而这两张表的取值是通用词——「采集／体检／周观点／分析」同时是运行状态的任务名
#   与目录名，「断档」同时是信号概念，「结构」同时是卡片字段。一旦进扫描词典，11 处
#   **正确**写法立刻被判违规（paths.py 的目录名、status.py 的灯标签）。
#   一条会误伤正确写法的规则比不扫更糟——它教人以后绕开规则。
#   需要这两个表的只有 `checks/docs/ledger.py`，它直接 import `pkb.domain.ledger`。
from .chains import FIELD_MAP                           # noqa: F401
from .automations import AUTOMATIONS, PROMPT_ANCHORS    # noqa: F401
from .legacy import LEGACY_WEEKS, IMPACT_SINCE                # noqa: F401
from .lifecycle import (ARCHIVE_DAYS, STALE_DAYS, VERIFY_DAYS, OBSERVE,  # noqa: F401
                        RETIRED_RE, retired)
from . import sources                                   # noqa: F401
from .sources import LEVELS                             # noqa: F401

__all__ = [
    'BLACK', 'BAD_SUBJECT', 'DOC_MUST_MENTION', 'is_bad',
    'DOMAINS', 'STAT_DOMAINS', 'IMPACTS', 'STATUSES', 'REQUIRED_FIELDS', 'CARD_SIZE_WARN',
    'VCS_STALE_DAYS',
    'ANALYSIS_TYPES', 'ANALYSIS_WORD_LIMIT', 'ANALYSIS_SPINE',
    'STANCES', 'STANCE_MIN', 'ARCHIVE_DATE_TOLERANCE',
    'FIELD_MAP',
    'AUTOMATIONS', 'PROMPT_ANCHORS',
    'LEGACY_WEEKS', 'IMPACT_SINCE',
    'ARCHIVE_DAYS', 'STALE_DAYS', 'VERIFY_DAYS', 'OBSERVE',
    # 已终止政策的口径（归档只认这一种）：检查与归档动作共用
    'RETIRED_RE', 'retired',
    'sources', 'LEVELS',
]
