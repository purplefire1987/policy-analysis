#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkb —— 政策知识库工具箱。

分层与依赖方向（单向，低层不许 import 高层）：

    run.py → pkb.actions → pkb.checks → pkb.domain → pkb.core

| 层 | 职责 | 禁止 |
|---|---|---|
| `core` | 路径、读写、frontmatter、Markdown、输出与摘要契约 | 出现「政策」两个字的业务判断 |
| `domain` | 名单与枚举：链、字段、归档周、黑名单 | 读盘、打印 |
| `checks` | 判定并返回 `Result`，明细放 `Result.lines` | 直接 print、直接 sys.exit |
| `actions` | 调度、聚合退出码、决定输出详略 | 业务判断 |

用法（脚本在 tools/ 下运行时，tools/ 自动在 sys.path 里）：

    from pkb.core import CARD_DIR, read, parse_fm, Verdict, Result
"""
