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
    ANALYSIS_TYPES, ANALYSIS_WORD_LIMIT, ANALYSIS_SPINE,
)
from .chains import FIELD_MAP                           # noqa: F401
from .legacy import LEGACY_WEEKS, JUDGE_SINCE           # noqa: F401

__all__ = [
    'BLACK', 'BAD_SUBJECT', 'DOC_MUST_MENTION', 'is_bad',
    'DOMAINS', 'STAT_DOMAINS', 'IMPACTS', 'STATUSES', 'REQUIRED_FIELDS', 'CARD_SIZE_WARN',
    'ANALYSIS_TYPES', 'ANALYSIS_WORD_LIMIT', 'ANALYSIS_SPINE',
    'FIELD_MAP',
    'LEGACY_WEEKS', 'JUDGE_SINCE',
]
