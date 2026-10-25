#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享报告器：15 项文档检查都往同一份报告里写。

为什么单独一个文件：拆包后每个子模块都要 ok/err/warn。若它们 import 包本身
（`from . import ok`）就成了循环导入——包要先加载子模块，子模块又要包里的名字。
这里只放状态与三个薄函数，谁也不依赖，谁都能导入。

`errors`/`warns`/`oks` 是 `rep` 里同名 list 的**别名**：清空统一用 `.clear()`，
绝不重建对象，否则别名会指向旧 list，各检查写进去的东西就丢了。
"""
from pkb.core import Reporter

rep = Reporter()
errors, warns, oks = rep.errors, rep.warns, rep.oks


def ok(msg):
    rep.ok(msg)


def err(item, msg):
    rep.err(item, msg)


def warn(item, msg):
    rep.warn(item, msg)
