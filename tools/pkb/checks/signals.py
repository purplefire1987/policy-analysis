#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政策信号页断档检查。

目的：政策信号（无文号的会议/表态/吹风会）与政策文件不同——过时就失效，
无法事后补救。本检查让「哪一天、哪个大类没采」变成可数的事实，而不是靠目测。

用法（由 run.py check 调度）：
  --since 2026-10-19   # 该日期之后各页新增；异常时 FAIL
  --week 2026-W43      # 指定 ISO 周；异常时 FAIL
  （不带参数时是 15 页状态总览，信息性，恒 PASS）

异常判定（--since / --week）：
  · 窗口内 0 条                          → 异常
  · 窗口 >= 3 天，有新增的页数 < 3        → 异常
  理由：国常会（每周）、商务部例行发布会（每周四）、金融口发布会（常态）
  覆盖不同大类，跨 3 个页是常态；只 1 页有新增，几乎只能说明只扫了热点。
  异常只提示核查，不要求凑数——信号宁缺不凑。
"""

import argparse
import datetime
import re

from pkb.core import SIGNAL_DIR, iso_week, Result, Verdict

DATE_LINE = re.compile(r'^### (\d{4}-\d{2}-\d{2}) · (.+?)\s*$', re.M)
ISO_WEEK = re.compile(r'^(\d{4})-W(\d{2})$')


def load_pages():
    """返回 {页名: [(date, title), ...]}，按日期倒序"""
    pages = {}
    if not SIGNAL_DIR.exists():
        return pages
    for p in sorted(SIGNAL_DIR.glob('*.md')):
        if p.name.startswith('.'):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        items = [(m.group(1), m.group(2)) for m in DATE_LINE.finditer(text)]
        items.sort(key=lambda x: x[0], reverse=True)
        pages[p.stem.replace('政策信号-', '')] = items
    return pages


def parse_week(s):
    m = ISO_WEEK.match(s.strip())
    if not m:
        return None
    y, w = int(m.group(1)), int(m.group(2))
    try:
        mon = datetime.date.fromisocalendar(y, w, 1)
        sun = datetime.date.fromisocalendar(y, w, 7)
    except ValueError:
        return None
    return mon, sun


def window_of(args):
    """返回 (start, end, label)；无窗口参数返回 None；参数坏掉抛 ValueError。

    原来是 print + sys.exit(2)——「有退出码没摘要」，入口那一行会空白。
    现在把错误抛给 run()，由它统一构造带摘要的 Result。
    """
    today = datetime.date.today()
    if args.week:
        got = parse_week(args.week)
        if not got:
            raise ValueError(f'✗ 周号格式不对：{args.week}（应形如 2026-W43）')
        return got[0], min(got[1], today), args.week
    if args.since:
        # 提示词里传的是「窗口起点」，实际调用会写成 `2026-10-24 09:00` 这种时间点。
        # 取日期部分即可（窗口粒度是天），否则一条合法调用会被判成「参数格式错」而静默空跑。
        raw = args.since.strip().replace('T', ' ').split(' ')[0]
        try:
            start = datetime.date.fromisoformat(raw)
        except ValueError:
            raise ValueError(f'✗ 日期格式不对：{args.since}'
                             '（应形如 2026-10-19 或 2026-10-19 09:00）')
        return start, today, f'{raw} 起'
    return None


def scan_fields():
    """八字段完整度（只统计，不阻断）。

    「关联政策」「政策走向」是周观点第二节五列表的直接来源。模板 2026-10-24 才补齐，
    此前 111 条存量均缺这两项，因此这里只报数、不判异常——补录按任务台账存量批次做。
    """
    tot = assoc = direc = both = 0
    for p in sorted(SIGNAL_DIR.glob('*.md')):
        if p.name.startswith('.'):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        hits = list(DATE_LINE.finditer(text))
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            chunk = text[m.end():end]
            a = '**关联政策**' in chunk
            d = '**政策走向**' in chunk
            tot += 1
            assoc += a
            direc += d
            both += (a and d)
    return tot, assoc, direc, both


def _gap_rows(pages, today):
    """每页的（页名, 条数, 最近条目, 断档天数），按断档从大到小排。"""
    rows = []
    for name, items in pages.items():
        if not items:
            rows.append((name, 0, None, 9999))
            continue
        try:
            last = datetime.date.fromisoformat(items[0][0])
            rows.append((name, len(items), last, (today - last).days))
        except ValueError:
            rows.append((name, len(items), None, 9999))
    rows.sort(key=lambda r: -r[3])
    return rows


def _gap_tag(gap):
    """断档天数 → (分档名, 状态标注)。分档同时用于表格与「分布」行。"""
    if gap <= 7:
        return '≤7 天', '近'
    if gap <= 14:
        return '8~14 天', '⚠ 一周以上'
    if gap <= 30:
        return '15~30 天', '⚠ 半月以上'
    return '>30 天或空', '✗ 空白'


def _gap_block(rows):
    """断档表与分布。返回 (lines, 条数合计, 分档计数)。"""
    lines = [f'{"页":<16}{"条数":>5}  {"最近条目":<12}{"断档":>7}   状态', '-' * 56]
    total, buckets = 0, {'≤7 天': 0, '8~14 天': 0, '15~30 天': 0, '>30 天或空': 0}
    for name, n, last, gap in rows:
        total += n
        key, tag = _gap_tag(gap)
        buckets[key] += 1
        lines.append(f'{name:<16}{n:>5}  {str(last or "—"):<12}'
                     f'{gap if gap < 9999 else "—":>7}   {tag}')
    lines.append('-' * 56)
    lines.append(f'合计 {total} 条')
    lines.append('分布：' + '｜'.join(f'{k} {v} 页' for k, v in buckets.items()))
    return lines, total, buckets


def report_all(pages):
    """全页状态：断档表 + 分档 + 八字段完整率（恒 PASS，只报进度）。"""
    today = datetime.date.today()
    lines = ['=== 政策信号页状态 ===',
             f'今天 {today}（{iso_week(today)}）｜共 {len(pages)} 页', '']
    block, _total, buckets = _gap_block(_gap_rows(pages, today))
    lines += block
    if buckets['>30 天或空']:
        lines.append(f'注：{buckets[">30 天或空"]} 页断档超 30 天，属历史空白（只报不阻断），'
                     '补采时按日期逐日扫，不按页是否"最旧"决定。')

    tot, assoc, direc, both = scan_fields()
    pct = f'{both * 100 / tot:.1f}%' if tot else '—'
    lines += ['', f'八字段完整率：{both}/{tot}（{pct}）'
                  f'｜含「关联政策」{assoc}｜含「政策走向」{direc}']
    if tot and both < tot:
        lines.append('注：这两项是周观点第二节五列表的直接来源，缺了只能由写作者现场判断。'
                     '模板已于 2026-10-24 补齐（八字段），存量补录按任务台账批次推进，不阻断。')
    return Result(Verdict.PASS, f'信号 {tot} 条，八字段完整率 {both}/{tot}（{pct}）', lines)


def _window_problems(hits, total, days, start, end):
    """窗口期的三条判据 + 连续工作日空白。返回问题描述列表，空表示正常。"""
    problems = []
    if total == 0:
        problems.append(f'窗口 {days} 天内 0 条信号')
    if days >= 3 and total < days:
        problems.append(f'日均不足 1 条（{total} 条 / {days} 天，近四周均值约 2.1~2.6 条/天）')
    if days >= 3 and len(hits) < 3:
        problems.append(f'仅 {len(hits)} 个页有新增（国常会、商务部发布会、金融口分属不同大类，'
                        '正常应 ≥3 页）')

    # 连续工作日空白：最直接定位漏采日
    marked = {d for ds in hits.values() for d in ds}
    blanks, run = [], []
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur.isoformat() not in marked:
            run.append(cur)
        else:
            if len(run) >= 2:
                blanks.append(run)
            run = []
        cur += datetime.timedelta(days=1)
    if len(run) >= 2:
        blanks.append(run)
    if blanks:
        seg = '、'.join(f'{r[0]}~{r[-1]}（{len(r)} 个工作日）' for r in blanks)
        problems.append(f'连续工作日无信号：{seg}')
    return problems


def report_window(pages, start, end, label, quiet=False):
    days = (end - start).days + 1
    hits = {}
    for name, items in pages.items():
        got = [d for d, _ in items if start.isoformat() <= d <= end.isoformat()]
        if got:
            hits[name] = got
    total = sum(len(v) for v in hits.values())

    lines = []
    if not quiet:
        lines.append(f'=== {label} 政策信号新增（窗口 {start} ~ {end}，共 {days} 天）===')
        if hits:
            for name, ds in sorted(hits.items(), key=lambda x: -len(x[1])):
                lines.append(f'  {name:<16}{len(ds):>3} 条   {min(ds)} ~ {max(ds)}')
        else:
            lines.append('  （无任何新增）')
        lines += ['', f'合计 {total} 条，覆盖 {len(hits)} / {len(pages)} 页']

    problems = _window_problems(hits, total, days, start, end)
    if problems:
        lines += ['', '⚠️ 疑似漏采：']
        lines += [f'   · {p}' for p in problems]
        lines.append('   核查建议：按日期逐日扫国常会、国新办发布会、商务部例行发布会（周四）、'
                     '发改委/央行/财政部/金监总局/证监会发布会、政治局会议与领导人讲话。')
        lines.append('   注意：此项只提示核查，不得为过检查而记入无方向性表述的普通工作动态。')
        return Result(Verdict.FAIL, f'{label}：{len(problems)} 个工作日无信号 ❌', lines)

    lines += ['', '✅ 窗口内信号覆盖正常']
    return Result(Verdict.PASS, f'{label}：信号覆盖正常 ✅', lines)


def run(argv=None):
    ap = argparse.ArgumentParser(description='政策信号页断档检查')
    ap.add_argument('--since', metavar='YYYY-MM-DD', help='该日期起的新增检查（异常 FAIL）')
    ap.add_argument('--week', metavar='YYYY-Www', help='指定 ISO 周（异常 FAIL）')
    ap.add_argument('--quiet', action='store_true', help='只输出结论行')
    args = ap.parse_args(list(argv or []))

    pages = load_pages()
    if not pages:
        return Result(Verdict.BAD_INPUT, f'信号页目录不存在：{SIGNAL_DIR}',
                      [f'✗ 未找到信号页目录：{SIGNAL_DIR}'])

    try:
        win = window_of(args)
    except ValueError as e:
        return Result(Verdict.BAD_INPUT, f'{str(e)}；本次未检查（结论不含该范围）  ⚠', [str(e)])

    if win is None:
        return report_all(pages)
    start, end, label = win
    if start > end:
        return Result(Verdict.BAD_INPUT, f'窗口起点 {start} 晚于终点 {end}（无结论）',
                      [f'✗ 窗口起点 {start} 晚于终点 {end}'])
    return report_window(pages, start, end, label, quiet=args.quiet)
