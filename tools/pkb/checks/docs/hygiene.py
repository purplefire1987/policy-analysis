#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""log 卫生：按月分卷、只判**新格式条目**，历史条目豁免。

为什么历史豁免：库里 30 多条 `## 2026-10-24` 式旧标题是既成事实，改写历史等于
伪造。但豁免不能顺带放过「新条目写错类型」——2026-10-26 审计发现类型白名单
被拼进了识别正则，写错类型的条目匹配不上、落进历史分支静默通过。
所以识别正则放宽成任意串，白名单在这里查。

为什么分卷（2026-11-07）：单文件涨到 206 KB，到顶了才想起来拆；拆完还得有人记得
「下个月换新卷」。现在文件名即归属——条目写进标题日期所在的 `log-YYYY-MM.md`，
写错卷由 `_wrong_month` 报，索引漏列由 `_check_index` 报，所以这三件事都不靠记性。
"""
import re

from pkb.core import LOG, read, log_volumes
from pkb.domain.fields import LOG_TYPES        # 口径住 domain，这里只 import（2026-10-29 搬过去）

from ._state import err, warn, ok

LOG_MAX_LINES = 80
LOG_MAX_BYTES = 200 * 1024

# 类型放宽成任意串，白名单在 _judge_new 里查。若直接用 LOG_TYPES 拼正则，
# 「类型写错」的条目就匹配不上、落进历史分支被静默豁免——那条 bad_type 分支
# 永远为空，等于「类型限五类」从未生效（2026-10-26 审计发现）。
LOG_HEAD = re.compile(r'^(\d{4}-\d{2}-\d{2}) · ([^·\s]+) · (.+)$')
LOG_VOL_RE = re.compile(r'^log-(\d{4}-\d{2})\.md$')
# `_log_heads` 交出来的标题**已经去掉行首 `## `**，所以这里不能带它：
# 带上会永远匹配不到，两条判据都变成空转（2026-11-07 单测当场抓到）。
DATE_PREFIX = re.compile(r'^(\d{4}-\d{2})-\d{2}')


def _month_of(name):
    """`log-2026-10.md` → `2026-10`；不是分卷返回 None。"""
    m = LOG_VOL_RE.match(name)
    return m.group(1) if m else None


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


def _judge_new(entries, first_old, where=''):
    """新格式条目：置顶、倒序、单条篇幅、类型白名单。顺序即报告顺序。"""
    at = f'{where}：' if where else ''
    if not entries:
        warn('log', f'{at}尚无合规新条目（格式 `## YYYY-MM-DD · 类型 · 一句话`）')
        return
    dates = [e['date'] for e in entries]
    if dates != sorted(dates, reverse=True):
        err('log', f'{at}新格式条目未按日期倒序：{dates}')
    late = [e for e in entries if e['line_no'] > first_old]
    if late:
        err('log', f'{at}{len(late)} 条新格式条目被追加到历史条目之后，新条目应置顶')
    over = [e for e in entries if e['lines'] > LOG_MAX_LINES]
    for e in over:
        err('log', f'{at}{e["date"]} {e["title"][:20]} 占 {e["lines"]} 行，'
                   f'超过 {LOG_MAX_LINES} 行上限——报告应写在对应页面，log 只留结论与指针')
    if not over and not late:
        ok(f'log：{at}{len(entries)} 条新格式条目，格式/倒序/篇幅均合规')
    bad_type = [e for e in entries if e['type'] not in LOG_TYPES]
    if bad_type:
        err('log', f'{at}{len(bad_type)} 条条目类型不在白名单'
                   f'（限 {"／".join(sorted(LOG_TYPES))}）：'
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


def _wrong_month(name, month, heads):
    """条目日期必须落在文件名那个月：分卷只认标题日期，归错卷等于白分。"""
    bad = [(m.group(1), h[:26]) for _ln, h in heads
           if (m := DATE_PREFIX.match(h)) and m.group(1) != month]
    if bad:
        err('log', f'{name} 里有 {len(bad)} 条属于别的月份（如 {bad[0][0]}「{bad[0][1]}」）'
                   '——条目要放标题日期所在的那一卷')


def _judge_volume(p, seen):
    """单卷：体积、月份归属、卷内顺序、篇幅、类型，并登记标题防跨卷重复。"""
    text = read(p, '')
    month = _month_of(p.name)
    size = p.stat().st_size
    if size > LOG_MAX_BYTES:
        warn('log', f'{p.name} {size / 1024:.0f} KB，超过 {LOG_MAX_BYTES // 1024} KB 上限——'
                    '报告留在对应页面，log 只留结论')
    lines, heads = _log_heads(text)
    _wrong_month(p.name, month, heads)
    entries, first_old = _new_entries(lines, heads)
    _judge_new(entries, first_old, where=p.name)
    _check_big_history(lines, heads)
    for _ln, h in heads:
        if h in seen:
            err('log', f'条目「{h[:24]}」两卷各有一份（{seen[h]}、{p.name}）——只该留一处')
        seen[h] = p.name
    return [m.group(1) for _ln, h in heads if (m := DATE_PREFIX.match(h))]


def _check_index(vols, text):
    """索引列全卷、不指空卷、不写条目——缺一行就没人找得到那一卷。"""
    if not text:
        err('log', '索引文件 log.md 不存在或为空——分卷没有入口')
        return
    listed = set(re.findall(r'\[\[(log-\d{4}-\d{2})\]\]', text))
    have = {p.stem for p in vols}
    missing, extra = sorted(have - listed), sorted(listed - have)
    if missing:
        err('log', f'索引缺 {len(missing)} 卷（{"、".join(missing)}）——分了卷不列出来，等于没分')
    if extra:
        err('log', f'索引指向不存在的分卷（{"、".join(extra)}）')
    if re.search(r'^## \d{4}-\d{2}-\d{2}', text, re.M):
        err('log', 'log.md 里写了条目——索引只列分卷，条目写进当月分卷')
    if not missing and not extra:
        ok(f'log 索引：{len(have)} 卷全部列出')


def _check_current(vols, months):
    """最新条目必须在最新那卷：写进旧卷时，卷名与内容就对不上了。"""
    if not months:
        return
    newest, last = max(months), _month_of(vols[-1].name)
    if newest > last:
        err('log', f'最新条目属于 {newest}，最新分卷却是 {vols[-1].name}——'
                   '当月条目没有自己的卷')


def check_log():
    vols = log_volumes()
    if not LOG.exists() and not vols:
        warn('log', '文件不存在')
        return
    if not vols:
        warn('log', '没有 `log-YYYY-MM.md` 分卷——条目无处可落')
        return
    _check_index(vols, read(LOG, ''))
    seen, months = {}, []
    for p in vols:
        months += _judge_volume(p, seen)
    _check_current(vols, months)


def check_types_declared(docs):
    """AGENTS 写的那串类型，必须等于 domain 的白名单。

    为什么单判一条：格式（`YYYY-MM-DD · 类型 · 一句话`）与类型表 2026-10-29 归口到
    AGENTS 第十节，`log.md` 页首改成了指针——于是「文档写的五种」与「代码限的五种」
    之间再没有第三处可以对照，只能在这里对一次。
    """
    t = docs.get('AGENTS', '')
    m = re.search(r'类型限\s*`([^`]+)`', t)
    if not m:
        err('AGENTS', '找不到「类型限 …」那串，log 类型无法核对——不静默放过')
        return
    declared = {x.strip() for x in re.split(r'[／/、]', m.group(1)) if x.strip()}
    if declared != set(LOG_TYPES):
        err('AGENTS', f'log 类型写「{"／".join(sorted(declared))}」，代码是'
                      f'「{"／".join(sorted(LOG_TYPES))}」——改了白名单要同步这一行')
    else:
        ok(f'log 类型：AGENTS 与 domain 一致（{len(LOG_TYPES)} 类）')
