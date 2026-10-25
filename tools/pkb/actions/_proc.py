#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作输出的捕获（actions 层内部件）。

名字叫 `_proc` 是历史遗留——2026-10-25 重构前这里是「用子进程调旧脚本」的包装，
动作迁进同一个进程后只有 `capture` 还在用（`fix` 靠它读各动作自己打的数字）。
不再起子进程，所以没有 shell 拼接与转义问题。
"""
import contextlib
import io


def capture(fn, argv=()):
    """跑一个会 print 的动作，把它的输出抓成文本。返回 (退出码, 文本)。

    为什么需要：fix 要按输出里的数字报「修了几处」，而那些数字是各动作自己打的。
    让它们改成返回结构化结果当然更干净，但改的是 5 个动作的输出路径；
    在这里捕获一次，代价小得多，也不影响它们被单独调用时的行为。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(list(argv))
    return code, buf.getvalue()
