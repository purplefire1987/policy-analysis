#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pytest 的全局前置：临时目录钉在工作区。

为什么需要（2026-10-28）：测试里 `tempfile.TemporaryDirectory()` 用得极多，
而 `tempfile` 在没有可用临时目录时会退到 **cwd** 去建探测文件——在库目录里跑测试，
库根就多一个 8 字符随机名空文件，而且删不掉时会连带让测试报
`No usable temporary directory`。这里一行把落点固定，两个后果一起消掉：
失败不再取决于「这台机器这次探测成不成」，垃圾也不再落在数据目录里。

注：这不是绕过沙箱删除限制的权宜写法——`tempfile.tempdir` 有值时 CPython
根本不遍历候选，问题被去掉而不是被容忍。见 `pkb/core/tmp.py`。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import tmp  # noqa: E402

tmp.ensure()
# 上一轮留下的临时目录先清掉（2026-10-29）：`cleanup` 失败被下面吞掉，残留没人管，
# 一天就堆到 3992 项 / 42 MB。**谁生产谁收拾**——测试造的垃圾，测试开场先扫一遍。
tmp.sweep()


# 清理失败不该让测试失败（2026-10-28）
# ------------------------------------
# 本机沙箱拦删除时，`TemporaryDirectory.__exit__` 会抛 PermissionError，于是
# **断言全部通过的用例照样报红**——112 个用例因此变成「环境坏了的读数」，
# 而报告里看不出这一点，只会显得代码有问题。
#
# 清理是测试的尾巴，不是测试本身：残留目录落在 `.cache/tmp/`（已进 .gitignore），
# 代价是几百 KB 的垃圾，代价的另一面是「测试结论只取决于代码」。
_cleanup = tempfile.TemporaryDirectory.cleanup


def _quiet_cleanup(self):
    try:
        _cleanup(self)
    except (PermissionError, OSError):
        pass


tempfile.TemporaryDirectory.cleanup = _quiet_cleanup
