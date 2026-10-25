#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkb.actions —— 动作层：调度、聚合退出码、决定输出详略。

规则：
* 业务判断留在 checks；这里只负责「跑哪几项、怎么打印、返回什么码」。
* **一模块一动作**：文件名即动作名，`run(argv) -> int` 供 `run.py` 的 ACTIONS 调用；
  ACTIONS 与目录必须一一对应（`tests/test_smoke.py` 钉住），所以加动作只改两处。
* **下划线开头＝内部件**（`_proc` 命令行抓取、`_snapshot` 快照刷新），不是动作，
  不进 ACTIONS、不出现在 `run.py list` 里。
"""
