#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""frontmatter 解析与改写（本库只用一层扁平键值，不上 yaml 依赖）。"""
import re

FM_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.S)


def parse_fm(text):
    """解析 YAML frontmatter 的扁平键值。

    返回 (dict, body)。数组写成 `[a, b]` 或花键下的多行 `- item` 都会被解析成 list，
    `tags: [政策, 国际博弈]` 这类必须保持数组，否则 Dataview 失效。
    无 frontmatter 时返回 ({}, 原文)。
    """
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm, body = {}, text[m.end():]
    cur = None
    for raw in m.group(1).split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # 多行列表项：`tags:` 下一行的 `- 政策`
        if line.startswith('- ') and cur is not None:
            item = line[2:].strip().strip('"').strip("'")
            if item:
                if not isinstance(fm.get(cur), list):
                    fm[cur] = []
                fm[cur].append(item)
            continue
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        cur = k.strip()
        v = v.strip().strip('"').strip("'")
        # 行内数组，但排除 `[[wikilink]]`——双括号是链接不是数组
        if v.startswith('[') and v.endswith(']') and not v.startswith('[['):
            fm[cur] = [x.strip().strip('"').strip("'")
                       for x in v[1:-1].split(',') if x.strip()]
        else:
            fm[cur] = v
    return fm, body


def set_fm_field(text, key, value):
    """改 frontmatter 里的一个键值（冒号半角/全角都认）。

    库里实际用半角 `政策数: 3`，只写全角会让替换静默失效——
    2026-10-24 的自动修复就栽在这里，一处没改却不报错。
    """
    return re.sub(rf'(?m)^{re.escape(key)}[:：].*$', f'{key}: {value}', text, count=1)
