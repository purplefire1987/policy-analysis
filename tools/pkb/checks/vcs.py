#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本控制：改动到底有没有历史（2026-10-28 增，报告里最大的单点缺口）。

为什么单列一项而不是并进 check_docs：它判的不是「文档对不对」，而是
「文档**变没说**」——同一份文件写错了，有 git 就能 diff 出「哪一行哪天被改成这样」，
没有就只能整库倒退。2026-10-28 把库纳入版本控制之前，33 张卡、15 条链、
121 条信号、5 篇周观点全无历史；改 33 张卡靠的是 tar 包，只能整体回滚。

**证据就发生在建库当天**：基线提交后不到十分钟，我在清随机名空文件时误删了
AGENTS.md、index.md、log.md、README.md（删除条件写错），靠刚建的对象库
一条 `git checkout` 全部取回。没有那次提交，四个文件就走了。

判什么、不判什么
----------------
* 判**失败**：不是 git 仓库、`.gitignore` 写了排除但文件仍被跟踪（见下）、一个提交都没有。
* 只**提示**：有未提交改动、久未提交（`VCS_STALE_DAYS`）。提交节奏是人的习惯，
  自动化改完文件本来就是脏的——按脏就报红，体检会天天红，信号就废了。

**判据为什么不写死 raw/articles**（2026-10-28 当天改过一次）
----------------------------------------------------------
第一版写的是「`raw/articles/` 被跟踪就是排除规则失效」。几小时后决定把
`raw/articles/` 纳入 git（实测每份均 12.7 KB，原先「体积远大于其余全部」的
排除理由没量过），**判据立刻把正确的做法判成硬问题**。

改成核「`.gitignore` 声明要排除的，实际有没有被跟踪」（`git ls-files -ci`）：
规则住在 `.gitignore` 里，判据只问「声明的和事实一致吗」。这样改排除清单时
不用同步改代码，也不会出现「判据记住的是旧决定」。
"""
import argparse
import time

from pkb.core import VAULT, Result, Verdict
from pkb.core.git import available, is_repo, run_git
from pkb.domain import VCS_STALE_DAYS

# 未提交明细最多打几条：全打会把 33 张卡的改动铺满一屏，反而看不见结论。
SHOW = 8


def _facts():
    """收集事实：不判断，只把 git 里的读数取出来。"""
    _, cnt = run_git('rev-list', '--count', 'HEAD')
    _, last = run_git('log', '-1', '--format=%ct%x00%s')
    _, dirty = run_git('status', '--porcelain')
    # -c 已跟踪 / -i 被忽略 / --exclude-standard 按 .gitignore 算：交集即「声明排除却仍在库」
    _, leaked = run_git('ls-files', '-ci', '--exclude-standard')
    f = {'commits': cnt.strip(),
         'dirty': [l for l in dirty.splitlines() if l.strip()],
         'leaked': [l for l in leaked.splitlines() if l.strip()],
         'last_ts': 0, 'last_subj': ''}
    if '\x00' in last:
        ts, subj = last.split('\x00', 1)
        f['last_ts'], f['last_subj'] = int(ts or 0), subj.strip()
    return f


def _group(paths):
    """把泄漏路径归到前两段：`raw/articles/x.md` → `raw/articles/`。

    只取第一层会把 `raw/articles/` 显示成 `raw/`，看不出到底是哪条规则失效；
    取全部又会让一条规则刷出几十行。前两段正好对上 `.gitignore` 的写法。
    """
    out = set()
    for x in paths:
        parts = x.split('/')[:-1]
        if parts:
            out.add('/'.join(parts[:2]) + '/')
    return sorted(out)


def _diagnose(f):
    """返回 (硬问题, 提示)。硬问题＝结论不成立，提示＝该知道但不阻断。"""
    hard, soft = [], []
    if not f['commits'].isdigit() or not int(f['commits']):
        hard.append('仓库里一个提交都没有——有目录无历史，等于没纳入版本控制')
    if f['leaked']:
        dirs = _group(f['leaked'])
        hard.append(f".gitignore 声明要排除、实际仍被跟踪 {len(f['leaked'])} 个文件"
                    f"（{('、'.join(dirs[:3]) or '根目录')}）——"
                    '排除规则失效，下次改动会继续进库')
    if f['dirty']:
        soft.append(f"{len(f['dirty'])} 处改动未提交："
                    + '、'.join(x[:40] for x in f['dirty'][:SHOW])
                    + ('' if len(f['dirty']) <= SHOW else f' 等 {len(f["dirty"])} 处'))
    if f['last_ts']:
        days = max(0, int((time.time() - f['last_ts']) // 86400))
        if days > VCS_STALE_DAYS:
            soft.append(f'最近一次提交在 {days} 天前（判据 {VCS_STALE_DAYS} 天）——'
                        '这期间的改动没有历史，只有末态')
    return hard, soft


def run(argv=None):
    ap = argparse.ArgumentParser(description='版本控制：改动有没有历史（只报不阻断）')
    ap.parse_args(list(argv or []))

    if not available():
        msg = '本机没有 git 可执行文件，本项无结论'
        return Result(Verdict.BAD_INPUT, msg, [f'✗ {msg}'])
    if not is_repo():
        msg = f'资料库不在版本控制：{VAULT} 不是 git 仓库——改错了没法 diff、没法回滚'
        return Result(Verdict.FAIL, msg,
                      [f'✗ {msg}', '  处置：git init 后建基线提交（见 log.md 2026-10-28）'])

    f = _facts()
    hard, soft = _diagnose(f)
    lines = ['=== 版本控制 ===',
             f"提交 {f['commits']} 次 · 未提交 {len(f['dirty'])} 处"
             f" · 最近一次：{(f['last_subj'] or '（无）')[:48]}"]
    lines += [f'  ✗ {m}' for m in hard] + [f'  · {m}' for m in soft]
    if not hard and not soft:
        lines.append('（工作区干净：当前所有改动都已进历史）')

    if hard:
        return Result(Verdict.FAIL, f'版本控制 {len(hard)} 个硬问题：' + hard[0][:52], lines)
    mark = '✅' if not soft else '⚠️'
    summary = f"版本控制：已提交 {f['commits']} 次 · 未提交 {len(f['dirty'])} 处 {mark}"
    return Result(Verdict.PASS, summary, lines)
