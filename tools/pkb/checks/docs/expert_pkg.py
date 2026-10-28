#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包入口形态：链接？实体副本？链错地方？

判形态而非内容。比哈希是在**事后发现**漂移，而那时通常已按旧代码跑过几轮
（本库 4 次事故全是这个时间差）。链接让「同一份代码存在两处」这个前提消失，
于是漂移不再是需要被发现的东西——它没有发生的载体。
"""
from pkb.core import TOOLS, expert, py_files

from ._state import err, ok, warn


def check_expert_scripts():
    st = expert.state()
    if st == expert.LINK:
        ok(f'专家包入口是链接 → tools（{len(py_files(TOOLS))} 个脚本同一份，无副本）')
        return
    if st == expert.COPY:
        items = expert.drift()
        for rel, kind in items[:12]:
            err('专家包', f'副本[{kind}] {rel}')
        if len(items) > 12:
            err('专家包', f'副本另有 {len(items) - 12} 处差异未列出')
        err('专家包', '专家包 scripts 是实体副本，不是链接——跑 `run.py link --force` 还原；'
                      '副本里的改动若该保留，先搬回 tools/')
        return
    if st == expert.MISSING:
        err('专家包', '专家包缺 skills/policy-kb-tools/scripts——跑 `run.py link` 建立链接')
        return
    err('专家包', f'专家包 scripts 指向别处：{expert.link_target() or "(悬空)"}'
                  f'（应为 {TOOLS}）——跑 `run.py link` 归位')


def check_expert_cache():
    """平台缓存（实际加载的那份）与专家包源是否一致。

    比 `check_expert_scripts` 弱一档：那里要求「物理只有一份」，这里**只能比对**——
    缓存目录归平台写。所以这一项的作用不是消灭副本，是「副本敢漂就当场说」。
    """
    items = expert.cache_drift()
    if items is None:
        warn('专家包缓存', '没找到 plugins/cache 下的这个专家（未安装或换了机器），跳过')
        return
    if not items:
        ok('专家包缓存与源一致（平台加载的就是这份）')
        return
    for rel, kind in items[:8]:
        err('专家包缓存', f'{kind}：{rel}')
    if len(items) > 8:
        err('专家包缓存', f'另有 {len(items) - 8} 处差异未列出')
    err('专家包缓存', '缓存落后于源——在实际加载的是缓存：把源同步进 cache 目录（改源后必须同步）')
