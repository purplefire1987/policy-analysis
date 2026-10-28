#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时目录：把 `tempfile` 的落点钉在工作区，不让它自己探测；顺手清旧残留。

为什么必须钉住（2026-10-28 反复出事）
----------------------------------
CPython 的 `tempfile._candidate_tempdir_list()` 在 TMPDIR/TEMP/TMP、/tmp、/var/tmp、
/usr/tmp 之后**无条件把当前工作目录当作最后一个候选**，而 `gettempdir()` 是靠
「建一个文件再删掉」判定可用的。本机沙箱里删除会被安全中心拦，于是探测失败，
而探测过程本身已经在 cwd 留下了 `mkstemp` 建的那个 8 字符随机名空文件——
资料库根目录里那批 `uks9o8gc` 一类文件就是这么来的，清完还长。

所以这里不做「失败后容忍」，而是让探测根本不发生：`tempfile.tempdir` 一旦有值，
`_get_default_tempdir()` 直接返回，不遍历候选、不建探测文件。
判据是「同一份代码在哪跑都落在同一个目录」，与「这次碰巧成功没有」无关。

为什么还要清（2026-10-29 增 `sweep`）
----------------------------------
钉住落点解决了「垃圾落在数据目录」，没解决「垃圾一直堆」：沙箱拦删时
`TemporaryDirectory.cleanup()` 会抛异常，`conftest` 为了让测试结论只取决于代码
而吞掉了它（这个处置是对的）。代价是残留无声累积——实测一天 3992 个目录 / 42 MB，
而**没有任何读数会告诉你它在长**。

清理不另设定时任务，就放在每次运行的开头：脚本每天至少跑两次（采集 09:00／18:00），
体检每 2 天一次，**「下次运行」本身就是那个定时器**。多一个自动化任务，要在 AGENTS
时刻表、运行状态、专家定义、提示词四处各同步一遍，成本远大于收益。

三条约束，都来自「清一次太贵」的实测：
* **只清 `KEEP_SECONDS` 之前的**：采集一轮可能跑几十分钟，自己建的临时目录还在用。
* **`SWEEP_GAP` 内不重复扫**：清一次要 stat 一遍整个目录，没必要每条命令都做。
* **有 `SWEEP_BUDGET` 秒的预算**：沙箱审查下单个 `rmtree` 要 0.2 秒，4000 个要
  11 分钟——`status` 卡 11 分钟比垃圾更糟。超预算就停，先清最老的，下次接着清。

删不掉的计数不重试、不静默：调用方拿到数字自己决定怎么说。
**「删不掉」是沙箱的状态，不是库的问题**，所以这里不抛异常、不影响退出码。
"""
import os
import shutil
import tempfile
import time

from .paths import TMP_DIR

KEEP_SECONDS = 24 * 3600     # 临时条目留一天
SWEEP_GAP = 6 * 3600         # 六小时内不重复扫
SWEEP_BUDGET = 1.5           # 单次扫的时间预算（秒）
STAMP_NAME = '.swept'        # 记「上次扫过」的戳，用 mtime，不存内容


def ensure():
    """建目录并钉住 `tempfile.tempdir`；返回该路径字符串。幂等。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(TMP_DIR)
    return tempfile.tempdir


def _size(path, is_dir):
    """条目占用字节。目录要 walk 一遍，但实测这里几乎全是空目录，开销可忽略。"""
    if not is_dir:
        try:
            return os.lstat(path).st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def sweep(force=False, budget=SWEEP_BUDGET):
    """清掉 `KEEP_SECONDS` 之前遗留的临时条目。

    返回 `(删除数, 失败数, 释放字节, 是否扫完)`。`force=True` 忽略节流（`fix` 用）。
    不抛异常：临时目录出事不该让主命令崩。
    """
    if not TMP_DIR.is_dir():
        return (0, 0, 0, True)
    stamp = TMP_DIR / STAMP_NAME
    now = time.time()
    if not force:
        try:
            if now - stamp.stat().st_mtime < SWEEP_GAP:
                return (0, 0, 0, True)
        except OSError:
            pass
    cutoff = now - KEEP_SECONDS
    todo = []
    try:
        with os.scandir(TMP_DIR) as it:
            for e in it:
                if e.name == STAMP_NAME:
                    continue
                try:
                    mt = e.stat(follow_symlinks=False).st_mtime
                except OSError:
                    continue
                if mt < cutoff:
                    todo.append((mt, e.path, e.is_dir(follow_symlinks=False)))
    except OSError:
        return (0, 0, 0, True)
    todo.sort()                      # 先清最老的：超预算时留下的是「刚过期」的那批
    removed = failed = freed = 0
    deadline = time.time() + budget
    done = 0
    for _mt, path, is_dir in todo:
        if time.time() > deadline:
            break
        freed += _size(path, is_dir)
        try:
            shutil.rmtree(path) if is_dir else os.remove(path)
            removed += 1
        except OSError:
            failed += 1
        done += 1
    try:
        stamp.touch()                # 扫过就记一笔，哪怕一个都没删
    except OSError:
        pass
    return (removed, failed, freed, done >= len(todo))
