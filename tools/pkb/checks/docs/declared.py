#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**文档声明的东西**是否与系统实际一致：节拍、周观点节名、分析报告节名。

这一组的共同点：被核对的是「文档里写的那句话」，而不是库里的数据。
所以判据必须是**逐字比对**（节名照抄模板），不能靠语义相似。
"""
import re

from pkb.core import TEMPLATE_DIR, WEEK_TEMPLATE, read

from ._state import err, warn, ok, errors

ANALYSIS_TEMPLATE = TEMPLATE_DIR / '政策分析报告模板.md'


def interval_days(text):
    """提取文档声明的体检节拍。

    跳过假设性语句——专家定义里有「如体检从每 2 天挪到每 3 天」这类操作示例，
    那是可能发生的变更，不是当前节拍，直接取数会误判成自相矛盾。
    """
    days = set()
    for line in text.split('\n'):
        if any(k in line for k in ('挪到', '改为', '例如', '假如', '如体检', '若')):
            continue
        days.update(int(x) for x in re.findall(r'每\s*(\d+)\s*天', line))
    return days


def check_interval(docs):
    base = interval_days(docs['AGENTS'])
    if len(base) > 1:
        err('AGENTS', f'文件内部节拍互相矛盾：{sorted(base)} 天')
        return
    if not base:
        warn('AGENTS', '未找到「每 N 天」表述，无法校验节拍')
        return
    n = base.pop()
    bad = []
    for name in ('README', '专家定义', '运行状态', '专家包README'):
        t = docs.get(name, '')
        if not t:
            warn(name, '文件不存在，跳过节拍比对')
            continue
        d = interval_days(t)
        if not d:
            warn(name, f'未写体检节拍，无法比对（AGENTS 为每 {n} 天）')
        elif d != {n}:
            bad.append((name, sorted(d)))
    if bad:
        for name, d in bad:
            err(name, f'体检节拍写 {d} 天，AGENTS 是 {n} 天')
    else:
        ok(f'节拍一致：每 {n} 天（AGENTS／两份 README／专家定义／运行状态）')


def check_week_sections(docs):
    """周观点节名：模板的 `##` 标题须逐字出现在 AGENTS 与专家定义里。

    节数**不在代码里写死**——模板即清单，加一节只同步两份文档，不必回来改数字
    （2026-10-26 增「八、本周可证伪判断」正是这个用法）。下界 7 只防模板被误删节。
    """
    tpl = read(WEEK_TEMPLATE, '')
    heads = [h.strip() for h in re.findall(r'^##\s+(.+)$', tpl, re.M)]
    if len(heads) < 7:
        err('周观点模板', f'节数 {len(heads)}，少于 7（疑有节被误删）')
        return
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        missing = [h for h in heads if h not in t]
        if missing:
            err(name, f'周观点节名与模板不一致，缺：{"、".join(missing)}')
    if not any(e[0] in ('AGENTS', '专家定义') for e in errors):
        ok(f'周观点节名：AGENTS／专家定义 与模板一致（{len(heads)} 节）')


def check_analysis_sections(docs):
    """分析报告八节名称：AGENTS 与专家定义须与模板逐字一致。

    与周观点同一动机：2026-10-25 模板从七节改为八节后，
    专家定义仍写旧七节，属典型副本漂移。此处把分析报告模板也纳入逐字比对。
    """
    if not ANALYSIS_TEMPLATE.exists():
        warn('分析报告模板', '文件不存在，跳过八节比对')
        return
    tpl = read(ANALYSIS_TEMPLATE, '')
    heads = [h.strip() for h in re.findall(r'^##\s+(.+)$', tpl, re.M)
             if h.strip() != '相关页面']
    if len(heads) != 8:
        err('分析报告模板', f'节数 {len(heads)}，应为 8（不含「相关页面」）')
        return
    before = len(errors)
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        missing = [h for h in heads if h not in t]
        if missing:
            err(name, f'分析报告八节名称与模板不一致，缺：{"、".join(missing)}')
    if len(errors) == before:
        ok('分析报告八节名称：AGENTS／专家定义 与模板一致')
