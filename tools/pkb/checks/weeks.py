#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周观点政策覆盖度校验。

用途：把「本周政策是否全部进了周观点速览表」从人工目测变成脚本对账。
三种跑法：指定周号（`--week` 或位置参数，由 run.py 透传）、`--all` 全量、`--add-missing`
只打印可粘贴的行。

退出语义：PASS = 通过（含 LEGACY_WEEKS 归档周，差异不计）；
          FAIL = 有漏项／数字不一致／文件不存在／缺信号节；BAD_INPUT = 没给周号也没给 --all。
"""
import argparse
import datetime
import difflib
import re

from pkb.core import CARD_DIR, WEEKLY_DIR, Result, Verdict
from pkb.domain import FIELD_MAP, LEGACY_WEEKS, STAT_DOMAINS


STOPWORDS = ['关于', '的通知', '通知', '的意见', '意见', '实施方案', '方案', '公告',
             '决定', '办法', '规定', '若干', '进一步', '加强', '推动', '促进', '做好',
             '有关', '工作', '实施', '开展', '印发', '发布', '年度', '我国', '国家']


def norm(s):
    """归一化：去括号内容、去标点、去通用词"""
    s = re.sub(r'[（(][^）)]*[）)]', '', s)
    s = re.sub(r'[《》〈〉「」“”"\'\-—－、，,。．\.：:；;\s]', '', s)
    for w in STOPWORDS:
        s = s.replace(w, '')
    return s


def similarity(a, b):
    """两个政策名的相近度 0~1。

    与 core.similar 刻意不合并：core.similar 是断链候选匹配（通用件），
    本函数依赖 STOPWORDS 这份政策文体停用词表——那是口径，口径不进共用层。
    """
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    # 核心词命中加成：取较长串的 2~4 字连续片段做包含判断
    bonus = 0.0
    for i in range(1, len(na) - 1):
        for L in (4, 3, 2):
            frag = na[i:i + L]
            if len(frag) == L and frag in nb and L >= 2:
                if L == 4:
                    bonus = max(bonus, 0.30)
                elif L == 3:
                    bonus = max(bonus, 0.18)
                break
    return min(1.0, ratio + bonus)


def load_cards():
    """返回 [(date, title, card), ...]"""
    items = []
    for f in sorted(CARD_DIR.glob('*.md')):
        card = f.stem.replace('政策卡片-', '')
        txt = f.read_text(encoding='utf-8')
        for m in re.finditer(r'^### (\d{4}-\d{2}-\d{2}) · (.+)$', txt, re.M):
            items.append((m.group(1), m.group(2).strip(), card))
    return items


def week_window(week_str):
    """2026-W42 → (mon, sun) date"""
    m = re.match(r'^(\d{4})-W(\d{2})$', week_str)
    if not m:
        raise ValueError(f'周号格式错误：{week_str}，应为 2026-W42')
    year, wk = int(m.group(1)), int(m.group(2))
    mon = datetime.date.fromisocalendar(year, wk, 1)
    sun = datetime.date.fromisocalendar(year, wk, 7)
    return mon, sun


def parse_weekly_table(path):
    """解析周观点速览表，返回 (rows, txt, lines, placeholders)"""
    txt = path.read_text(encoding='utf-8')
    lines = txt.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r'^##\s*一、', ln):
            start = i
            break
    if start is None:
        return [], txt, lines, []
    rows = []
    placeholders = []
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if re.match(r'^##\s', ln):
            break
        if not ln.strip().startswith('|'):
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if len(cells) < 2:
            continue
        if set(cells[0]) <= set('-: ') or cells[0] == '领域':
            continue
        # 占位废行：第 2 列以「（」开头且第 3 列为 — 或空，例如
        # 「（本周科技与数字化领域无新增卡片）」「（民用航空/…已列）」
        body = cells[2] if len(cells) > 2 else ''
        if cells[1].startswith('（') and (body in ('—', '-', '–', '') or body.startswith('—')):
            placeholders.append({'line': i + 1, '政策': cells[1]})
            continue
        rows.append({'line': i + 1, '领域': cells[0], '政策': cells[1]})
    return rows, txt, lines, placeholders


def check_week(week_str, verbose=True):
    """校验一周。返回 (Verdict, res|None, lines)。文件不存在时 res 为 None。"""
    mon, sun = week_window(week_str)
    f = WEEKLY_DIR / f'周观点-{week_str}.md'
    if not f.exists():
        return Verdict.BAD_INPUT, None, [f'✗ 找不到文件：{f}']

    cards = load_cards()
    in_window = [(d, t, c) for d, t, c in cards if mon.isoformat() <= d <= sun.isoformat()]
    rows, txt, lines, placeholders = parse_weekly_table(f)

    # 匹配：每个窗口内政策找最佳表格行
    matched, orphan_rows = {}, []
    used = set()
    row_claims = {}          # 行号 -> 认领它的政策列表
    for d, t, c in in_window:
        best, best_s, best_i = None, 0.0, None
        for idx, r in enumerate(rows):
            s = similarity(t, r['政策'])
            if s > best_s:
                best, best_s, best_i = r, s, idx
        if best_s >= 0.42:
            matched[(d, t)] = (best, best_s)
            used.add(best_i)
            row_claims.setdefault(best_i, []).append((d, t))
    for idx, r in enumerate(rows):
        if idx not in used:
            orphan_rows.append(r)

    missing = [(d, t, c) for d, t, c in in_window if (d, t) not in matched]
    # 一行被多条政策共用：要么有意合并（需在表内注明），要么是误匹配
    merged = {i: v for i, v in row_claims.items() if len(v) > 1}
    # 未注明合并的判定必须在 verbose 之外做——否则 --all 永远看不到它
    # （2026-10-25 前这里只写在打印分支里，同一判据两种结果）
    undeclared_merge = [rows[i] for i in merged if '合并' not in rows[i]['政策']]

    # 数字对账
    declared = None
    for pat in (r'表内\s*([0-9]+)\s*行', r'^政策数[:：]\s*([0-9]+)\s*$', r'本周\s*([0-9]+)\s*项'):
        mdecl = re.search(pat, txt, re.M)
        if mdecl:
            declared = int(mdecl.group(1))
            break
    fm = re.search(r'^政策数[:：]\s*([0-9]+)\s*$', txt, re.M)
    fm_count = int(fm.group(1)) if fm else None
    dom_re = '|'.join(STAT_DOMAINS)
    dist = re.findall(rf'({dom_re})\s*([0-9]+)\s*项', txt)
    dist_sum = sum(int(v) for _, v in dist) if dist else None

    ok = True
    if missing:
        ok = False
    if orphan_rows or placeholders or undeclared_merge:
        ok = False
    if declared is not None and declared != len(rows):
        ok = False
    if fm_count is not None and fm_count != len(rows):
        ok = False
    if dist_sum is not None and dist_sum != len(rows):
        ok = False

    out = []
    if verbose:
        out += [f'══ 周观点 {week_str} 覆盖度校验 ══',
                f'窗口：{mon} ~ {sun}',
                f'产业卡内政策：{len(in_window)} 项',
                f'速览表行数：{len(rows)} 行',
                f'成功匹配：{len(matched)} 项（占用表内 {len(used)} 行）',
                '']
        if missing:
            out.append(f'❌ 漏列 {len(missing)} 项（窗口内有、表里没有）：')
            for d, t, c in missing:
                field = FIELD_MAP.get(c, '?')
                out.append(f'   [{d}] [{field} / {c}] {t}')
                out.append(f'      → 建议行：| {field} | {t} | （待补核心要点） | （待补变化点） | （待补影响） |')
        else:
            out.append('✅ 无漏项')
        out.append('')
        if merged:
            out.append(f'📎 合并行 {len(merged)} 处（同一行覆盖多条政策，须在表内注明「合并」）：')
            for i, pols in merged.items():
                declared_merge = '合并' in rows[i]['政策']
                mark = '✅ 已注明合并' if declared_merge else '❌ 未注明合并'
                out.append(f'   第 {rows[i]["line"]} 行「{rows[i]["政策"][:40]}」← 认领 {len(pols)} 项  [{mark}]')
                for d, t in pols:
                    out.append(f'      · [{d}] {t}')
            out.append('')
        if placeholders:
            out.append(f'🧹 表内占位废行 {len(placeholders)} 行（须删除，不得用空行凑领域）：')
            for r in placeholders:
                out.append(f'   第 {r["line"]} 行 {r["政策"]}')
            out.append('')
        if orphan_rows:
            out.append(f'⚠️ 表内 {len(orphan_rows)} 行无法对应到窗口内政策（可能是窗口外错位或重复）：')
            for r in orphan_rows:
                out.append(f'   第 {r["line"]} 行 | {r["领域"]} | {r["政策"]}')
        else:
            out.append('✅ 无错位/多余行')
        out.append('')
        out.append('数字对账：')
        out.append(f'  表内实际行数 = {len(rows)}')
        out.append(f'  正文声明数   = {declared if declared is not None else "（未声明）"}'
                   + ('  ✅' if declared == len(rows) else '  ❌ 不一致' if declared is not None else ''))
        if fm_count is not None:
            out.append(f'  frontmatter 政策数 = {fm_count}'
                       + ('  ✅' if fm_count == len(rows) else '  ❌ 与表内行数不一致'))
        elif declared is not None and declared == len(rows):
            out.append('  frontmatter 政策数 = （未设置，建议补）')
        if dist:
            detail = ' + '.join(f'{k}{v}' for k, v in dist)
            out.append(f'  分领域合计   = {detail} = {dist_sum}'
                       + ('  ✅' if dist_sum == len(rows) else '  ❌ 不一致'))
        out.append('')
        out.append('✅ 校验通过' if ok else '❌ 校验未通过，请修正后重跑')

    return (Verdict.PASS if ok else Verdict.FAIL), {
        'week': week_str, 'in_window': in_window, 'rows': rows,
        'missing': missing, 'orphans': orphan_rows, 'placeholders': placeholders,
        'merged': merged, 'undeclared_merge': undeclared_merge,
        'declared': declared, 'dist_sum': dist_sum,
    }, out


def run_all():
    files = sorted(WEEKLY_DIR.glob('周观点-*.md'))
    tbl = []
    worst = Verdict.PASS
    for f in files:
        wk = f.stem.replace('周观点-', '')
        verdict, res, _ = check_week(wk, verbose=False)
        if res is None:
            continue
        # 豁免对象来自 LEGACY_WEEKS 名单，不再靠「有没有信号节」推断
        legacy = wk in LEGACY_WEEKS
        n_miss = len(res['missing'])
        n_orph = len(res['orphans']) + len(res['placeholders'])
        total = len(res['in_window'])
        rate = (total - n_miss) / total * 100 if total else 100.0
        tbl.append((wk, total, len(res['rows']), n_miss, n_orph, rate, verdict, legacy))
        if not legacy and verdict is Verdict.FAIL:   # 归档周差异不进退出码，否则永远修不好
            worst = Verdict.FAIL

    lines = [f'{"周号":<12}{"窗口内":>7}{"表行":>6}{"漏":>4}{"错位":>6}{"覆盖率":>9}  结果',
             '-' * 62]
    for wk, total, nrow, n_miss, n_orph, rate, verdict, legacy in tbl:
        mark = '历史归档' if legacy else ('✅' if verdict is Verdict.PASS else '❌')
        lines.append(f'{wk:<12}{total:>7}{nrow:>6}{n_miss:>4}{n_orph:>6}{rate:>8.1f}%  {mark}')
    lines += ['',
              '（对本汇总表的统计口径：覆盖率 = 已列入表内的窗口内政策 / 窗口内政策总数）',
              '（标「历史归档」的周为六节旧版、无信号节，用户已决定不回补——',
              '  它们的差异不计入退出码，也不得列为待修项。规则见 AGENTS。）']

    live = [t for t in tbl if not t[7]]
    bad = [t[0] for t in live if t[6] is Verdict.FAIL]
    latest = live[-1] if live else None
    summary = (f'{len(tbl)} 周（有效 {len(live)}／历史归档 {len(tbl) - len(live)}）：'
               + (f'最新 {latest[0]} 覆盖率 {latest[5]:.1f}%' if latest else '无有效周')
               + (f'；未过 {len(bad)} 周（{",".join(bad)}）' if bad else '；全部通过'))
    return Result(worst, summary, lines)


def run(argv=None):
    ap = argparse.ArgumentParser(description='周观点政策覆盖度校验')
    ap.add_argument('week_pos', nargs='?', metavar='week', help='如 2026-W42')
    ap.add_argument('--week', dest='week', help='同上（与位置参数等价，供 run.py 透传）')
    ap.add_argument('--all', action='store_true', help='校验全部周观点')
    args = ap.parse_args(list(argv or []))
    args.week = args.week or args.week_pos

    if args.all:
        return run_all()

    if not args.week:
        return Result(Verdict.BAD_INPUT, '未指定周号，也没有 --all（无结论）',
                      ['用法：--week 2026-W43 或 --all'])

    legacy = args.week in LEGACY_WEEKS
    f = WEEKLY_DIR / f'周观点-{args.week}.md'
    if f.exists() and not legacy and '## 二、本周政策信号' not in f.read_text(encoding='utf-8'):
        return Result(Verdict.FAIL,
                      f'{args.week} 结构缺节：无「二、本周政策信号」  ❌',
                      ['✗ 缺「二、本周政策信号」节：七节模板要求该节必在，',
                       f'  只有 LEGACY_WEEKS 名单内的归档周可豁免，{args.week} 不在名单里。'])

    verdict, res, lines = check_week(args.week)
    if res is None:                       # 文件不存在
        return Result(Verdict.FAIL,
                      f'{args.week} 周观点尚未生成（无文件，不是覆盖不足）  ❌', lines)
    total = len(res['in_window'])
    n_miss = len(res['missing'])
    n_orph = len(res['orphans']) + len(res['placeholders'])
    rate = (total - n_miss) / total * 100 if total else 100.0
    if legacy:
        return Result(Verdict.PASS,
                      f'{args.week} 历史归档（规则变更前六节旧篇）：覆盖率 {rate:.1f}%'
                      f'（漏 {n_miss}，错位 {n_orph}），差异不计入退出码', lines)
    return Result(verdict,
                  f'{args.week} 覆盖率 {rate:.1f}%（漏 {n_miss}，错位 {n_orph}）'
                  + ('  ✅' if verdict is Verdict.PASS else '  ❌'), lines)
