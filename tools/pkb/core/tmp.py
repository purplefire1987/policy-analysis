#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时目录：把 `tempfile` 的落点钉在工作区，不让它自己探测。

为什么必须有这个模块（2026-10-28 反复出事）：
CPython 的 `tempfile._candidate_tempdir_list()` 在 TMPDIR/TEMP/TMP、/tmp、/var/tmp、
/usr/tmp 之后**无条件把当前工作目录当作最后一个候选**，而 `gettempdir()` 是靠
「建一个文件再删掉」判定可用的。本机沙箱里删除会被安全中心拦，于是探测失败，
而探测过程本身已经在 cwd 留下了 `mkstemp` 建的那个 8 字符随机名空文件——
资料库根目录里那批 `uks9o8gc` 一类文件就是这么来的，清完还长。

所以这里不做「失败后容忍」，而是让探测根本不发生：`tempfile.tempdir` 一旦有值，
`_get_default_tempdir()` 直接返回，不遍历候选、不建探测文件。
判据是「同一份代码在哪跑都落在同一个目录」，与「这次碰巧成功没有」无关。
"""
import tempfile

from .paths import TMP_DIR


def ensure():
    """建目录并钉住 `tempfile.tempdir`；返回该路径字符串。幂等。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(TMP_DIR)
    return tempfile.tempdir
