#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调 git：只跑命令、只回文本，不判断。

为什么单独一层：`check_vcs`（判「改动有没有历史」）与 `history`（查「这条改动是哪次」）
是同一件事的两端——一边看工作区脏不脏，一边翻历史找原因。两边各写一份 subprocess
拼装，就是又一次副本（本项目 4 次事故全出在这上面）。

不抛异常：git 不存在、目录不是仓库、命令参数错，都只是「退出码非 0 + 一段说明」，
是否算问题由调用方按自己的口径判——core 不含口径。
"""
import shutil
import subprocess

from .paths import VAULT


def available():
    """本机有没有 git 可执行文件。"""
    return shutil.which('git') is not None


def run_git(*args, cwd=None):
    """跑 `git <args>`，返回 (退出码, 合并输出文本)。

    cwd 默认是资料库根：所有调用都是冲着库去的，让调用方少写一次参数。
    stderr 合进 stdout——调用方要的是「出了什么事」，不关心它从哪个流来。
    """
    if not available():
        return 127, '本机没有 git 可执行文件'
    try:
        p = subprocess.run(['git', *args], cwd=str(cwd or VAULT),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return 126, f'调用 git 失败：{e}'
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def is_repo(cwd=None):
    """这里是不是一个 git 工作树。"""
    code, _ = run_git('rev-parse', '--is-inside-work-tree', cwd=cwd)
    return code == 0
