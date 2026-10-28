#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「只有时间戳变了」不算变了：覆盖式页面写盘前的幂等判定。

为什么单独一件：`归档/index.md` 与 `wiki/总览/告警.md` 都是**覆盖写**，两个模板
都带一行生成时间。没有这一步，每跑一次就产一次 diff——挂上定时任务后，一年五十多次
「只有时间变了」的提交，真正的变化淹没在里面，`check_vcs` 的「未提交」也因此
永远清不掉。

判据：把指定的时间戳行抹掉再逐字比。**行首锚定、整行抹掉**——只比内容不比措辞，
所以模板改了称谓（「生成时间」→「内容生成于」）只要把前缀传对，判定不受影响。
"""

import re


def strip(text, *prefixes):
    """抹掉以 `> <prefix>` 开头的整行。prefixes 按字面匹配，不当正则。"""
    pat = re.compile(r'^> (?:%s).*$' % '|'.join(re.escape(p) for p in prefixes), re.M)
    return pat.sub('', text)


def unchanged(old, new, *prefixes):
    """旧文件内容与将要写入的内容，除时间戳行外是否一致。

    `old` 为空（文件不存在）时一律返回 False——第一次必须写。
    """
    if not old:
        return False
    return strip(old, *prefixes) == strip(new, *prefixes)
