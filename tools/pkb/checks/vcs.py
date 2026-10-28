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

沙箱探针（2026-10-29 增）
------------------------
沙箱拦下删除（安全中心「询问」层，不是规则拒绝）时，为了判断「这个目录能不能写」，
会在**被操作的目录**里落一个探测文件：8 位随机名（字符集 `[a-z0-9_]`）、
内容固定 4 字节 `blat`、权限 0600。随后真正要删的那一步同样被拦，探针就留在原地。

它不属于本项目，也没有任何代码引用它；但因为它不是 `.gitignore` 里写明的排除项，
`git add -A` 会照收——2026-10-29 一天里就有 109 个这样进了版本库。
**判据三重全中才认**（名字 8 位 `[a-z0-9_]` ＋ 大小 4 字节 ＋ 内容恰为 `blat`），
宁可漏认也不错认：删错一个 4 字节文件，比多留十个垃圾严重。
"""
import argparse
import os
import re
import time
from pathlib import Path

from pkb.core import (SKIP_DIRS, TMP_DIR, TOOLS, VAULT, WORKSPACE, Result,
                      Verdict)
from pkb.core.git import available, is_repo, run_git
from pkb.domain import VCS_STALE_DAYS

# 未提交明细最多打几条：全打会把 33 张卡的改动铺满一屏，反而看不见结论。
SHOW = 8

# 探针的三重特征。三者缺一不认——只凭「4 字节」或「8 字符名」会误伤正常小文件。
PROBE_NAME = re.compile(r'^[a-z0-9_]{8}$')
PROBE_BODY = b'blat'
PROBE_SIZE = 4
# 只查「命令会落脚的四处」的浅层。整树走一遍要 283 ms（工作区 .cache/ 里一万多个
# 抓取缓存），而探针只出现在执行命令的当前目录。漏在更深处的那些，`git status`
# 的未跟踪提示看得见，不靠这条兜底。
PROBE_BASES = (WORKSPACE, TOOLS, VAULT, TMP_DIR)
PROBE_DEPTH = 1


def _shallow(base, depth):
    """限深列出文件：`depth=1` 只到 base 与它的一级子目录。

    为什么不整树 walk：工作区 `.cache/` 里躺着一万多个抓取缓存文件（53 MB），
    全走一遍 283 ms，而这项判据一年也答不上一次「有」。
    """
    if not base.is_dir():
        return
    stack = [(base, 0)]
    while stack:
        d, lv = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        here = []
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if lv < depth and e.name not in SKIP_DIRS:
                        stack.append((Path(e.path), lv + 1))
                elif e.is_file(follow_symlinks=False):
                    here.append(e)
            except OSError:
                continue
        yield d, here


def _probes():
    """找出沙箱探针（三重特征全中）。只读，不改盘。"""
    found = []
    for base in PROBE_BASES:
        for d, entries in _shallow(base, PROBE_DEPTH):
            for e in entries:
                if not PROBE_NAME.match(e.name):
                    continue
                try:
                    if e.stat(follow_symlinks=False).st_size != PROBE_SIZE:
                        continue
                    with open(e.path, 'rb') as fh:
                        if fh.read() != PROBE_BODY:
                            continue
                except OSError:
                    continue
                found.append(os.path.join(str(d), e.name))
    return found


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
         'probes': _probes(),
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
    if f['probes']:
        # 只举一个例子：这类文件长得一模一样，列全了反而看不出「它们是什么」。
        sample = f['probes'][0].replace(str(WORKSPACE) + '/', '').replace(str(VAULT) + '/', '')
        hard.append(f"{len(f['probes'])} 个沙箱探针残留（4 字节 `blat`／8 位随机名，"
                    f"如 `{sample}`）——不属于本项目，下次 `git add -A` 会连它们一起进库；"
                    '跑 `run.py fix` 清掉（三重特征全中才删，不会误伤）')
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


def run_fix():
    """`run.py fix` 的探针清理。返回 (清掉几个, 明细行)。

    只删 `_probes()` 认定过的（名／大小／内容三重全中），**不做任何猜测**：
    4 字节的文件很多（空 `.gitkeep` 之类），凭大小删会重演 10-28 那次误删四个文档。
    """
    removed, lines = 0, []
    for p in _probes():
        try:
            os.remove(p)
        except OSError as e:
            lines.append(f'  删不掉 {p}：{e}')
            continue
        removed += 1
        lines.append(f'  删除 沙箱探针 {p}')
    if not removed and not lines:
        lines.append('  跳过 无沙箱探针')
    return removed, lines


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
             + (f" · 沙箱探针 {len(f['probes'])} 个" if f['probes'] else '')
             + f" · 最近一次：{(f['last_subj'] or '（无）')[:48]}"]
    lines += [f'  ✗ {m}' for m in hard] + [f'  · {m}' for m in soft]
    if not hard and not soft:
        lines.append('（工作区干净：当前所有改动都已进历史）')

    if hard:
        return Result(Verdict.FAIL, f'版本控制 {len(hard)} 个硬问题：' + hard[0][:52], lines)
    mark = '✅' if not soft else '⚠️'
    summary = f"版本控制：已提交 {f['commits']} 次 · 未提交 {len(f['dirty'])} 处 {mark}"
    return Result(Verdict.PASS, summary, lines)
