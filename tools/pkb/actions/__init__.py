#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkb.actions —— 动作层：调度、聚合退出码、决定输出详略。

规则：
* 业务判断留在 checks；这里只负责「跑哪几项、怎么打印、返回什么码」。
* 一个动作一个模块，函数名统一 `run(argv) -> int`（check／status 等），
  供 run.py 按表调用。
"""
