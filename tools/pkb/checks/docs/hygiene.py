#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""log.md 卫生：只判**新格式条目**，历史条目豁免。

为什么历史豁免：库里 30 多条 `## 2026-10-24` 式旧标题是既成事实，改写历史等于
伪造。但豁免不能顺带放过「新条目写错类型」——2026-10-26 审计发现类型白名单
被拼进了识别正则，写错类型的条目匹配不上、落进历史分支静默通过。
所以识别正则放宽成任意串，白名单在这里查。
"""
import re

from pkb.core import LOG, read

from ._state import err, warn, ok

LOG_TYPES = {'决策', '采集', '体检', '观点', '事故'}
LOG_MAX_LINES = 80
LOG_MAX_BYTES = 200 * 1024

# 类型放宽成任意串，白名单在 _judge_new 里查。若直接用 LOG_TYPES 拼正则，
# 「类型写错」的条目就匹配不上、落进历史分支被静默豁免——那条 bad_type 分支
# 永远为空，等于「类型限五类」从未生效（2026-10-26 审计发现）。
LOG_HEAD = re.compile(r'^(\d{4}-\d{2}-\d{2}) · ([^·\s]+) · (.+)$')


def _log_heads(text):
    """(全部行, 二级标题 [(行号, 标题)])。"""
    lines = text.split('\n')
    heads = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith('## ')]
    return lines, heads


def _new_entries(lines, heads):
    """合规新条目及其后第一条历史条目的行号（用来判「新条目是否置顶」）。"""
    out = []
    for idx, (line_no, h) in enumerate(heads):
        m = LOG_HEAD.match(h)
        if not m:
            continue
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        out.append({'date': m.group(1), 'type': m.group(2), 'title': m.group(3),
                    'lines': end - line_no - 1, 'line_no': line_no})
    first_old = next((ln for ln, h in heads if not LOG_HEAD.match(h)), len(lines))
    return out, first_old


def _judge_new(entries, first_old):
    """新格式条目：置顶、倒序、单条篇幅、类型白名单。顺序即报告顺序。"""
    if not entries:
        warn('log', '尚无合规新条目（格式 `## YYYY-MM-DD · 类型 · 一句话`）')
        return
    dates = [e['date'] for e in entries]
    if dates != sorted(dates, reverse=True):
        err('log', f'新格式条目未按日期倒序：{dates}')
    late = [e for e in entries if e['line_no'] > first_old]
    if late:
        err('log', f'{len(late)} 条新格式条目被追加到历史条目之后，新条目应置顶')
    over = [e for e in entries if e['lines'] > LOG_MAX_LINES]
    for e in over:
        err('log', f'{e["date"]} {e["title"][:20]} 占 {e["lines"]} 行，超过 {LOG_MAX_LINES} 行上限——'
                   '报告应写在对应页面，log 只留结论与指针')
    if not over and not late:
        ok(f'log：{len(entries)} 条新格式条目，格式/倒序/篇幅均合规')
    bad_type = [e for e in entries if e['type'] not in LOG_TYPES]
    if bad_type:
        err('log', f'{len(bad_type)} 条条目类型不在白名单（限 {"／".join(sorted(LOG_TYPES))}）：'
                   + '、'.join(f"{e['date']}「{e['type']}」" for e in bad_type[:3]))


def _check_big_history(lines, heads):
    """历史条目里的大块快照：只提示，不阻断（那是既成事实）。"""
    big = []
    for idx, (ln, h) in enumerate(heads):
        if LOG_HEAD.match(h):
            continue
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        if end - ln - 1 > LOG_MAX_LINES:
            big.append((ln, end - ln - 1))
    if big:
        warn('log', f'{len(big)} 条历史条目超过 {LOG_MAX_LINES} 行（最多一条 '
                    f'{max(n for _, n in big)} 行，多为把整份报告贴进日志），'
                    '建议降级为指针，不阻断')


def check_log():
    if not LOG.exists():
        warn('log', '文件不存在')
        return
    text = read(LOG, '')
    size = LOG.stat().st_size
    if size > LOG_MAX_BYTES:
        warn('log', f'{size / 1024:.0f} KB，超过 {LOG_MAX_BYTES // 1024} KB 上限——应分卷到 log-YYYY-MM.md')

    lines, heads = _log_heads(text)
    seen = {}
    for _, h in heads:
        seen[h] = seen.get(h, 0) + 1
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        warn('log', f'完全重复的标题 {len(dup)} 组：{", ".join(d[:24] for d in dup[:3])}'
                    + ('…' if len(dup) > 3 else ''))

    entries, first_old = _new_entries(lines, heads)
    _judge_new(entries, first_old)
    _check_big_history(lines, heads)
