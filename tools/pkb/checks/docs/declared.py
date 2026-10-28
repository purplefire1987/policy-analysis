#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**文档声明的东西**是否与系统实际一致：节拍、周观点节名、分析报告节名。

这一组的共同点：被核对的是「文档里写的那句话」，而不是库里的数据。
所以判据必须是**逐字比对**（节名照抄模板），不能靠语义相似。
"""
import re

from pkb.core import TEMPLATE_DIR, WEEK_TEMPLATE, read

from ._state import err, warn, ok, errors
from .consistency import _section

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
    # README 从必写改成「写了就核」（2026-10-29）：库 README 的节拍表已收成指针，
    # 指向 AGENTS 第一节。没有节拍不是错；写了错的才是。
    for name in ('README', '专家定义', '运行状态', '专家包README'):
        t = docs.get(name, '')
        if not t:
            warn(name, '文件不存在，跳过节拍比对')
            continue
        d = interval_days(t)
        if not d:
            if name != 'README':
                warn(name, f'未写体检节拍，无法比对（AGENTS 为每 {n} 天）')
            continue
        if d != {n}:
            bad.append((name, sorted(d)))
    if bad:
        for name, d in bad:
            err(name, f'体检节拍写 {d} 天，AGENTS 是 {n} 天')
    else:
        ok(f'节拍一致：每 {n} 天（AGENTS／专家定义／运行状态）')


def _times(text, head, idx, need=None):
    """某一节表格里第 idx 列的时刻集合。`need` 用来筛行（例如只取「自动化」那几行）。"""
    out = set()
    for line in _section(text, head).split('\n'):
        s = line.strip()
        if not s.startswith('|') or (need and need not in s):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) > idx:
            out |= set(re.findall(r'\d{2}:\d{2}', cells[idx]))
    return out


def check_times(docs):
    """四个任务的**时刻**：AGENTS 第一节 vs [[运行状态]] 的节拍列。

    为什么单判一条：`check_interval` 只认「每 N 天」，时刻从来没人核——README 与
    运行状态各写一份全表，改一次采集时点要记得改三处。时刻 2026-10-29 收进 AGENTS
    第一节（唯一源），运行状态保留一列供「跑没跑」对照，于是这一列必须被判据看着。
    """
    ag = _times(docs.get('AGENTS', ''), '## 一、产出物与频率', 1, need='自动化')
    st = _times(docs.get('运行状态', ''), '## 一、当前状态', 2)
    if not ag:
        err('AGENTS', '第一节没读出任何「HH:MM」——判据失效，不是文档没问题')
    elif not st:
        warn('运行状态', '当前状态表没读出时刻，无法比对')
    elif ag != st:
        for t in sorted(ag - st):
            err('运行状态', f'AGENTS 写着 {t}，节拍列里没有——改了时点没同步这一页')
        for t in sorted(st - ag):
            err('运行状态', f'节拍列写着 {t}，AGENTS 第一节没有——两处时刻分家了')
    else:
        ok(f'时刻一致：{len(ag)} 个时点（AGENTS 第一节／运行状态节拍列）')


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
