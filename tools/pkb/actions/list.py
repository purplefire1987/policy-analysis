#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：list —— 列出工具结构与各项用途。

存在的理由：脚本有几个、分别干什么，不该由人去记。需要时跑这条命令，
它读的是包内真实模块（新增/删除自动反映），不会像文档那样过时。
"""
import importlib


def head(title):
    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)


def first_line(mod):
    """模块 docstring 的第一行——每个模块都必须有一句「这是什么」。"""
    doc = (mod.__doc__ or '').strip()
    return doc.split('\n')[0].strip() if doc else '（无说明）'


def run(argv=None):
    from pkb.checks import REGISTRY

    head('工具目录清单')
    print('\n入口')
    print('  run.py                    统一入口（8 个动作，跑 `run.py --help` 看全部）')

    print('\n检查项（pkb/checks/，按注册顺序执行；名字即体检输出里的检查项名）')
    for i, spec in enumerate(REGISTRY, 1):
        tag = '（含自动修复）' if spec.fixable else ''
        print(f'  {i}. {spec.name:<26}{first_line(spec.module)[:44]}{tag}')

    print('\n动作（pkb/actions/）')
    for name in ('status', 'check', 'fix', 'plan', 'week', 'sources', 'export', 'list'):
        mod = importlib.import_module(f'pkb.actions.{name}')
        print(f'  {name:<12}{first_line(mod)[:50]}')

    print('\n共用层')
    for name in ('pkb.core', 'pkb.domain'):
        mod = importlib.import_module(name)
        print(f'  {name:<12}{first_line(mod)[:50]}')

    print('\n（清单由包内模块生成；新增检查 = 写一个 run(argv)->Result + 在 '
          'pkb/checks/__init__.py 注册一行）')
    return 0
