#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口径单源扫描：口径字面量只能出现在 `pkb/domain/`。

判据很窄，只认一件事：**代码里的字符串常量，值与 domain 的某个取值完全相同**。
自己抄一份黑名单域名、或把领域枚举写成裸字符串，这才是「把口径搬出了 domain」。
值只是句子的一部分（提示文案、帮助文本里的示例周号）不算——那是措辞不是口径。

词典从 domain 现读，所以 domain 加一项，扫描自动覆盖那一项，本函数不必改。
这也意味着：**这里不能出现口径字面量**，否则它自己会被自己扫出来。
"""
import ast

from pkb import domain as _domain
from pkb.core import TOOLS, read, py_files

from ._state import err, warn, ok


def guarded_literals():
    """口径层的字符串常量 → 归口常量名（`'jiemian.com'` → `BLACK`）。

    判据不另写一份名单——**名单本身就是第二份副本**，正是要防的东西。
    这里反过来做：把 `pkb.domain` 的导出值读出来当扫描词典。

    排除 `REQUIRED_FIELDS`：字段名是「读数据的键」（`fm.get('领域')`），
    不是复述口径；把字段名也当地雷，会逼所有检查改写 `fm.get(KEY['领域'])`，
    徒增一层无意义间接。`is_bad` 是函数、`CARD_SIZE_WARN` 是数字，天然不在词典里。
    """
    out = {}
    for name in _domain.__all__:
        if name == 'REQUIRED_FIELDS':
            continue
        val = getattr(_domain, name)
        if isinstance(val, str):
            vals = [val]
        elif isinstance(val, dict):
            vals = list(val)                      # 黑名单是「键即域名」，值只是原因说明
        elif isinstance(val, (set, frozenset, tuple, list)):
            vals = [x for x in val if isinstance(x, str)]
        else:
            continue
        for s in vals:
            if len(s) >= 2:                       # 单字枚举（高/中/低）没有判别力
                out.setdefault(s, name)
    return out


def code_strings(path):
    """文件里**代码用到的**字符串常量：[(行号, 值)]。docstring 与注释不算。

    为什么用 AST 而不逐行找引号：注释和 docstring 里举例子会被正则当成违规，
    等于逼人不敢在注释里说清规则；f-string 里的整句（`f'应为 2026-W42'`）是提示
    文案，也不是复述口径。AST 只认真正作为值参与运算的常量——判断标准与
    「把口径抄进代码」这件事对齐。
    """
    try:
        tree = ast.parse(read(path, ''))
    except SyntaxError as e:
        warn(path.name, f'无法解析，跳过口径扫描：{e}')
        return []
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstring_ids]


def check_domain_literals():
    """扫 tools/*.py ＋ tools/pkb/**/*.py，跳过 domain 自己。"""
    guard = guarded_literals()
    hits = []
    files = [p for p in py_files(TOOLS)
             if not p.relative_to(TOOLS).as_posix().startswith('pkb/domain/')]
    for p in files:
        rel = p.relative_to(TOOLS).as_posix()
        for lineno, val in code_strings(p):
            if val in guard:
                hits.append(f'{rel}:{lineno} 硬编码 `{val}`——应 import {guard[val]}（domain/）')
    if hits:
        for h in sorted(hits)[:12]:
            err('口径', h)
        if len(hits) > 12:
            err('口径', f'…另有 {len(hits) - 12} 处口径字面量')
        err('口径', '口径只能住在 pkb/domain/——改口径时要能一处改完')
    else:
        ok(f'口径单源：{len(guard)} 个取值只在 domain/ 出现（{len(files)} 个文件已扫）')
