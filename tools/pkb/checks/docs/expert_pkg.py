#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包入口形态：链接？实体副本？链错地方？

判形态而非内容。比哈希是在**事后发现**漂移，而那时通常已按旧代码跑过几轮
（本库 4 次事故全是这个时间差）。链接让「同一份代码存在两处」这个前提消失，
于是漂移不再是需要被发现的东西——它没有发生的载体。
"""
from pkb.core import TOOLS, expert, py_files

from ._state import err, ok


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
