#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight —— 只剩名字，实质已并入 `status`（2026-10-28 晚）。

保留这个文件只有一个理由：`run.py preflight` 在文档、台账与人的习惯里出现过，
突然删掉会让那条命令变成「No such action」而不是「它搬到哪了」。

**这里不许写判据。** 原实现回答四件事（数据截止／采集／结构／版本控制）并给
「能不能开跑」的结论——那些全部搬进了 `pkb/actions/status.py`，因为三个自动化
本来就跑 `status`：一条只在该用的时候才想得起来的命令，等于没有。

判断依据（采集日志里最晚的日期）`status` 本来就已经读出来了，再读一遍纯属多余；
两份各读一遍还会在跨零点时给出不同答案——**同一个量只留一处**。
"""
import argparse

from . import status


def run(argv=None):
    ap = argparse.ArgumentParser(
        prog='preflight', description='已并入 status：开跑前先看「数据截止」那一行')
    ap.add_argument('--task', default='', help='已废弃，保留只为不报错')
    ap.parse_args(list(argv or []))
    print('（preflight 已并入 status，两者输出相同；下面就是 status 的结果）')
    return status.run([])
