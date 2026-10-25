#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子进程调用的统一包装（actions 层内部用）。

为什么还留着子进程：还没迁完的动作（快照、派活、导出、来源清理）仍是脚本形态。
迁完之后这个模块只剩「跑外部命令」这一个用途。
"""
import contextlib
import io
import subprocess
import sys

PY = sys.executable or 'python3'


def sh(cmd, cwd=None, timeout=600):
    """跑一条命令，返回 (退出码, 输出文本)。永不抛异常。"""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except Exception as e:                                  # 脚本崩了也算它没过
        return 1, f'[pkb] 执行失败：{e}'


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
