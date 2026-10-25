#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查注册表：跑哪些检查、顺序、认领哪些参数。

为什么从「自动发现 check_*.py」改成注册表：
    自动发现靠文件名，等于把「哪些文件是检查」这件事交给目录内容；
    模块化之后检查在 `pkb/checks/` 包里，文件名不再承担元信息，注册表才是单一来源。
    顺序也在这里定：输出按注册顺序编号，体检提示词与历史报告都对着这个顺序看。

新增一项检查 = 在这里加一行 + 在 pkb/checks/ 下写一个 `run(argv) -> Result` 模块。
不用改 run.py，也不用改任何提示词。
"""
from dataclasses import dataclass
from types import ModuleType

from . import analysis, docs, health, judgments, prompts, signals, structure, views, weeks


@dataclass(frozen=True)
class Spec:
    """一项检查的元信息。

    name 沿用旧的脚本文件名：体检提示词写的是「取输出里 check_signals.py 那一行」，
    历史体检报告里也是这个名字——改名等于让所有历史记录对不上号。
    """
    name: str
    module: ModuleType
    needs_all: bool = False        # 不带参数就没结论，需要自动补 --all
    flags: tuple = ()              # 认领的参数（其余不传给它，传了 argparse 会报未知参数）
    fixable: bool = False          # 提供 run_fix()：能被 `run.py fix` 自动修


# 顺序 = 输出编号顺序。按名称字母序排列，与模块化之前 glob 的结果一致。
REGISTRY = (
    Spec('check_analysis.py', analysis),
    Spec('check_docs.py', docs),
    Spec('check_health.py', health),
    Spec('check_judgments.py', judgments),
    Spec('check_prompts.py', prompts),
    Spec('check_signals.py', signals, flags=('--since', '--week')),
    Spec('check_structure.py', structure, fixable=True),
    Spec('check_views.py', views),
    Spec('check_week_coverage.py', weeks, needs_all=True, flags=('--week', '--all')),
)


def all_flags():
    """全部检查合计认领的参数（用于「参数无人认领」告警）。"""
    out = set()
    for s in REGISTRY:
        out |= set(s.flags)
    return out


def names():
    return [s.name for s in REGISTRY]
