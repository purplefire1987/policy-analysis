#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子进程调用的统一包装（actions 层内部用）。

为什么还留着子进程：还没迁完的动作（快照、派活、导出、来源清理）仍是脚本形态。
迁完之后这个模块只剩「跑外部命令」这一个用途。
"""
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
