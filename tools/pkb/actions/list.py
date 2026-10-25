#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：list —— 列出工具结构与各项用途。

存在的理由：脚本有几个、分别干什么，不该由人去记。需要时跑这条命令，
它读的是包内真实模块（新增/删除自动反映），不会像文档那样过时。

动作清单也从包里**发现**，不手写一份名字元组：手写的那份是 `run.py` 的 ACTIONS
的副本，加一个动作忘了改，清单就会安静地少一行（2026-10-25 `export` 改名 `link`
正是这类改动）。文件名即动作名，下划线开头是内部件——这条约定由 `test_smoke`
钉住，所以「发现」出来的清单不会比 ACTIONS 多也不会少。
"""
import importlib
import pkgutil


def head(title):
    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)


def first_line(mod):
    """模块 docstring 的第一行——每个模块都必须有一句「这是什么」。"""
    doc = (mod.__doc__ or '').strip()
    return doc.split('\n')[0].strip() if doc else '（无说明）'


def action_modules():
    """`pkb/actions/` 里的动作模块名：下划线开头的是内部件（`_proc`、`_snapshot`）。"""
    from pkb import actions
    return sorted(m.name for m in pkgutil.iter_modules(actions.__path__)
                  if not m.name.startswith('_'))


def run(argv=None):
    from pkb.checks import REGISTRY

    names = action_modules()
    head('工具目录清单')
    print('\n入口')
    print(f'  run.py                    统一入口（{len(names)} 个动作，跑 `run.py --help` 看全部）')

    print('\n检查项（pkb/checks/，按注册顺序执行；名字即体检输出里的检查项名）')
    for i, spec in enumerate(REGISTRY, 1):
        tag = '（含自动修复）' if spec.fixable else ''
        print(f'  {i}. {spec.name:<26}{first_line(spec.module)[:44]}{tag}')

    print('\n动作（pkb/actions/）')
    for name in names:
        mod = importlib.import_module(f'pkb.actions.{name}')
        print(f'  {name:<12}{first_line(mod)[:50]}')

    print('\n共用层')
    for name in ('pkb.core', 'pkb.domain'):
        mod = importlib.import_module(name)
        print(f'  {name:<12}{first_line(mod)[:50]}')

    print('\n（清单由包内模块生成；新增检查 = 写一个 run(argv)->Result + 在 '
          'pkb/checks/__init__.py 注册一行；新增动作 = 写一个 run(argv)->int + 在 '
          'run.py 的 ACTIONS 加一行）')
    return 0
