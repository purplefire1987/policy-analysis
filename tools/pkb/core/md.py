#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 与日期解析：小节切块、表格抽取、日期换算、模糊匹配。

这一层不认识「政策」，只认识「### 日期 · 标题」这种结构——
core 不许出现业务词，判据在 domain/ 与各 check 里。
"""
import datetime
import difflib
import re

SECTION_HEAD = re.compile(r'^### (\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\s*$', re.M)


def extract_sections(body):
    """把正文按 `### YYYY-MM-DD · 标题` 切成块。

    返回 (secs, bad)：secs = [(date, title, chunk_text, raw_line)]，
    bad = 不符合日期格式的 ### 标题行。产业卡与信号页共用这一种小节格式。
    """
    secs, bad = [], []
    cur = None
    for line in body.split('\n'):
        if line.startswith('### '):
            if cur:
                secs.append(cur)
            m = SECTION_HEAD.match(line)
            if m:
                cur = [m.group(1), m.group(2), [], line]
            else:
                bad.append(line)
                cur = None
        elif cur is not None:
            cur[2].append(line)
    if cur:
        secs.append(cur)
    return [(d, t, '\n'.join(ch), raw) for d, t, ch, raw in secs], bad


def md_section_lines(text, title):
    """取 `## ` 节（标题含 title 即中）到下一个 `## ` 之间的行。

    用包含匹配而不是全等：台账各节标题带序号，如 `## 四、存量补采队列（…）`。
    """
    out, on = [], False
    for line in text.split('\n'):
        if line.startswith('## '):
            on = title in line
            continue
        if on:
            out.append(line)
    return out


def table_rows(lines):
    """从行序列里抽 markdown 表格数据行（跳过表头与分隔行）。"""
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip().strip('|').split('|')]
        if not cells or set(''.join(cells)) <= set('-: '):
            continue
        rows.append(cells)
    return rows[1:] if rows else []   # 首行是表头


def similar(target, names, cutoff=0.85, n=2):
    """断链自动修复用：返回候选名列表。多个候选时调用方必须放弃（不猜）。"""
    return difflib.get_close_matches(target, list(names), n=n, cutoff=cutoff)


def iso_week(d):
    """date → 'YYYY-Www'。判定周次一律走它，不要凭感觉。"""
    y, w, _ = d.isocalendar()
    return f'{y}-W{w:02d}'


def parse_date(s):
    """'2026-10-20' → date；解析不了返回 None（不抛异常，交给调用方判）。"""
    try:
        return datetime.date.fromisoformat(str(s).strip())
    except (ValueError, TypeError):
        return None


def span(a, b):
    """日期区间显示：相同只写一个。"""
    return f'{a}~{b}' if a != b else f'{a}'
