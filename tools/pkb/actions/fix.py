#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：fix —— 一次性修复所有能自动修的。

顺序有讲究：
1. 结构修复（数值/断链）——会改 frontmatter 的数值；
2. 快照刷新——必须排在结构修复之后，否则 index 里的统计是修之前的；
3. 来源清理——只删黑名单链接，平时是 no-op；
4. 专家包入口归位——scripts 必须是指向 tools 的链接，副本一律还原（放最后，等修复落盘）。

**脚本不猜的，一律留给人工**：观点覆盖要联网检索、字段取值涉及判断、跨链归属要人定、
文档口径冲突（AGENTS／README／专家定义各说一套）改哪份只有人能决定。
"""
import re

from pkb.checks import REGISTRY
from pkb.core import banner

from . import link as link_action
from . import _snapshot as snapshot, sources as sources_action
from ._proc import capture


def _step_snapshot(step):
    """2. 快照刷新：结构修复改过 frontmatter 数值，index 的统计要重算。"""
    code, out = capture(snapshot.run)
    n = re.findall(r'(\d+)\s*处(?:更新|差异)', out)
    print(f'[{step}] 快照刷新            退出码 {code}'
          + (f'，更新 {n[-1]} 处' if n else '，无变化（幂等）'))
    return int(n[-1]) if n else 0


def _step_sources(step):
    """3. 来源清理（只在真有违规时才写盘，平时是 no-op）。"""
    code, out = capture(sources_action.run, ['--dry-run'])
    hits = re.findall(r'命中\s*(\d+)', out) or re.findall(r'(\d+)\s*条', out)
    if hits and int(hits[0]) > 0:
        code2, _ = capture(sources_action.run, ['--apply'])
        print(f'[{step}] 来源清理            清理 {hits[0]} 条违规链接，退出码 {code2}')
        return int(hits[0])
    print(f'[{step}] 来源清理            无违规链接（跳过）')
    return 0


def _step_link(step):
    """4. 专家包入口归位：只把形态改回链接，不涉及任何内容判断。

    副本里有与 tools 不一致的改动时 `link` 会拒绝（exit 1）——那种情况必须人看，
    fix 不替人丢弃别人写的代码，只报「需要人工确认」。
    """
    code, out = capture(link_action.run)
    if code == 0:
        changed = 0 if '无需改动' in out else 1
        print(f'[{step}] 专家包入口          退出码 0'
              + ('，已接回链接（原副本删除）' if changed else '，已是链接'))
        return changed
    print(f'[{step}] 专家包入口          退出码 {code}，副本里有改动需人工确认')
    return 0


def _conclude(changed):
    banner('修复结论')
    print(f'本轮自动修改 {changed} 处。')
    print('\n仍需人工判断（脚本不猜，猜了就是编造）：')
    print('  · 观点覆盖率欠账 —— 要联网检索，属采集活')
    print('  · 信号断档补采 —— 过了日期补不回来，属采集活')
    print('  · 字段取值异常（影响/领域/tags）—— 涉及判断')
    print('  · 跨链归属错位 —— 只报告不移动')
    print('  · 文档口径冲突（含 AGENTS／README／专家定义各说一套）—— 改哪一份须问用户')
    print('\n修完请再跑一次 `python3 tools/run.py check` 确认归零。')
    return 0


def run(argv=None):
    banner('一次性修复')
    changed = 0
    step = 0

    # 1. 注册表里标了 fixable 的检查项，各自实现 run_fix()
    for spec in REGISTRY:
        if not spec.fixable:
            continue
        step += 1
        n, lines = spec.module.run_fix()
        print(f'[{step}] {spec.name:<24} 退出码 0' + (f'，修复 {n} 处' if n else ''))
        for line in lines:
            if re.search(r'修复|改写|删除|替换|更新|跳过', line):
                print('      ' + line.strip()[:96])
        changed += n

    step += 1
    changed += _step_snapshot(step)
    step += 1
    changed += _step_sources(step)
    step += 1
    changed += _step_link(step)
    return _conclude(changed)
