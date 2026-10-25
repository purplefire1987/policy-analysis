#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""来源域名合规：黑名单命中即硬错误，并统计三类「待核」标记。

存在的理由：2026-10-24 全库清出 100 条违规链接（今日头条 58 条最多），
此前四条规则写在三份文件里、一次也没拦住——规则不落到脚本上就等于没有。
"""
import re

from pkb.core import VAULT
from pkb.domain import BLACK

from ._state import err, warn, ok


def check_sources():
    hits, pending = [], 0
    for p in sorted((VAULT / 'wiki').rglob('*.md')):
        if '.obsidian' in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8').split('\n'), 1):
            for u in re.findall(r'\]\((https?://[^)\s]+)', line):
                for k, why in BLACK.items():
                    if k in u:
                        hits.append(f'{p.name}:{i} {why} → {u[:60]}')
                        break
            if any(t in line for t in ('原始出处待核', '原始出处未能核实', '官方链接待补')):
                pending += 1
    if hits:
        for h in hits[:12]:
            err('来源域名', h)
        if len(hits) > 12:
            err('来源域名', f'…另有 {len(hits) - 12} 条违规链接')
    else:
        ok('来源域名合规（黑名单 0 命中）')
    if pending:
        warn('来源', f'{pending} 处已标注「原始出处待核／未能核实／官方链接待补」——'
                    '这些来源不可核验，须逐步换回官方链接')
