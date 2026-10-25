#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判断台账校验：编号能不能回原文、到期的判断结算了没有。

为什么独立成一项检查：判断是**跨周对象**——卡片「影响」列引用它、下一期第七节复盘它、
Brier 记分要跨十几周数它。此前它只活在某一周的正文里，「这条到期没」只能靠人记得。
台账是它的家；本检查只做一件事：**保证台账不自说自话**——每一行都要在对应周观点的
第八节里找到原文，第八节出现过的编号都要在台账里有户头，卡片引用的编号同理。

退出语义：
  FAIL = 台账与正文对不上（重号／列数不对／编号格式错／状态越界／判定日解析不了／
         第八节查无此号／第八节有而台账没登记／卡片引用了查无此号）
  PASS = 结构没问题；「到期未结算」「可回填」只列明细——那是欠账，不是结构错，
         欠账一旦阻断退出码，就会淹没真问题（与 check_views 同一分工）。
"""
import argparse
import datetime
import re

from pkb.core import (CARD_DIR, JUDGE_LEDGER, OVERVIEW_DIR, WEEKLY_DIR,
                      Result, Verdict, md_section_lines, parse_date, table_rows, read)
from pkb.domain import JUDGE_PENDING, JUDGE_SINCE, JUDGE_STATES

# 编号是索引，不是口径：正则守的是「形状」（J+四位年份+-W+两位周号+-序号）。
ID_RE = re.compile(r'^J(\d{4})-W(\d{2})-(\d+)$')
REF_RE = re.compile(r'J\d{4}-W\d{2}-\d+')
# 卡片里「暂不判断：待 W43 周观点登记」——采集与周观点之间的交接单
PENDING_RE = re.compile(r'待\s*W(\d{2})\s*周观点登记')

COLS = 7          # 编号｜判断｜指标与阈值｜裁判｜判定日｜状态｜结算依据
COL_DUE, COL_STATE, COL_BASIS = 4, 5, 6


def ledger_rows(text):
    """只认「四、台账」那一节的表：正文里别的表（状态说明）不是台账。"""
    return table_rows(md_section_lines(text, '四、台账'))


def audit(rows, lookup):
    """rows → (errors, items)。lookup(编号) 返回对应周观点正文或 None。

    纯函数：不读盘、不打印，单测直接喂行。
    """
    errors, items, seen = [], [], set()
    for n, cells in enumerate(rows, 1):
        if len(cells) < COLS:
            errors.append(f'第 {n} 行 {len(cells)} 列（需 {COLS} 列）')
            continue
        jid = cells[0]
        m = ID_RE.match(jid)
        if not m:
            errors.append(f'第 {n} 行编号「{jid}」不合 J周号-序 格式')
            continue
        if jid in seen:
            errors.append(f'{jid} 重复登记（只许一行）')
            continue
        seen.add(jid)
        if parse_date(cells[COL_DUE]) is None:
            errors.append(f'{jid} 判定日「{cells[COL_DUE]}」不是 YYYY-MM-DD')
        if cells[COL_STATE] not in JUDGE_STATES:
            errors.append(f'{jid} 状态「{cells[COL_STATE]}」不在四值内')
        src = lookup(jid)
        if src is None:
            errors.append(f'{jid} 找不到 {m.group(1)}-W{m.group(2)} 的周观点文件')
        elif jid not in src:
            errors.append(f'{jid} 在该周观点的第八节里不存在——台账不能有第八节没有的判断')
        items.append({'id': jid, 'state': cells[COL_STATE],
                      'due': parse_date(cells[COL_DUE]), 'basis': cells[COL_BASIS]})
    return errors, items


def overdue(items, today):
    """判定日已过、状态仍是待判的编号。日期没解析成功的已在 audit 里报错，这里跳过。"""
    return [it['id'] for it in items
            if isinstance(it['due'], datetime.date) and it['due'] < today
            and it['state'] == JUDGE_PENDING]


def card_refs():
    """扫卡片：引用了哪些编号、还有哪些等着回填。返回 (refs, pending)。"""
    refs, pending = {}, []
    if not CARD_DIR.exists():
        return refs, pending
    for p in sorted(CARD_DIR.glob('*.md')):
        text = read(p)
        for jid in REF_RE.findall(text):
            refs.setdefault(jid, []).append(p.stem)
        for m in PENDING_RE.finditer(text):
            pending.append((p.stem, m.group(1)))
    return refs, pending


def weekly_ids():
    """自 JUDGE_SINCE 起，各期周观点里出现过的全部编号 → {编号: 文件名}。

    文件名即周号，不必解析正文；只比到「周」这一级，所以字符串比大小就够。
    这一层是「台账不能漏行」的兜底：某期出了判断却没登记，台账会慢慢变成节选。
    """
    out = {}
    if not WEEKLY_DIR.exists():
        return out
    for p in sorted(WEEKLY_DIR.glob('周观点-*.md')):
        if p.stem.replace('周观点-', '') < JUDGE_SINCE:
            continue
        for jid in REF_RE.findall(read(p)):
            out.setdefault(jid, p.name)
    return out


def _lookup_factory():
    """按编号定位周观点文件，同一文件只读一次。"""
    cache = {}

    def lookup(jid):
        m = ID_RE.match(jid)
        key = f'周观点-{m.group(1)}-W{m.group(2)}.md'
        if key not in cache:
            p = WEEKLY_DIR / key
            cache[key] = read(p) if p.exists() else None
        return cache[key]

    return lookup


def _render(items, errors, due, refs, pend, today):
    """明细：先错误后欠账，一行一条，便于体检直接抄。

    「查无此号」已在 errors 里，这里不再重复渲染——同一件事说两遍，读者会以为是两个问题。
    """
    out = [f'  ✗  {e}' for e in errors]
    out += [f'  !  {j} 判定日已过（今天 {today}）仍未结算' for j in due]
    if not errors:
        out.append(f'  OK  {len(items)} 条判断：台账与第八节逐条对得上')
    known = sorted(set(refs) & {it['id'] for it in items})
    if known:
        out.append(f'  ·  {len(known)} 个编号已被卡片引用（影响档位挂得住）')
    for w in sorted({w for _, w in pend}):
        out.append(f'  ·  有卡片写着「待 W{w} 周观点登记」——该周已出稿则回填编号')
    return out


def run(argv=None):
    """返回 Result；明细在 lines，不打印。"""
    ap = argparse.ArgumentParser(description='判断台账校验（编号可回原文、到期已结算）')
    ap.add_argument('--today', help='用来判到期，默认今天（YYYY-MM-DD）')
    args = ap.parse_args(list(argv or []))

    if not OVERVIEW_DIR.exists():
        return Result(Verdict.SKIP, '空库：无总览目录，判断台账不适用', [])
    if not JUDGE_LEDGER.exists():
        return Result(Verdict.FAIL, '判断台账缺失：wiki/总览/判断台账.md 不在',
                      [f'  ✗  未找到 {JUDGE_LEDGER}'])

    today = parse_date(args.today) or datetime.date.today()
    rows = ledger_rows(read(JUDGE_LEDGER))
    errors, items = audit(rows, _lookup_factory())
    due = overdue(items, today)
    refs, pend = card_refs()

    unknown = sorted(set(refs) - {it['id'] for it in items})
    errors += [f'{j} 被卡片引用但台账查无此号（{len(refs[j])} 张卡）' for j in unknown]

    filed = weekly_ids()
    missing = sorted(set(filed) - {it['id'] for it in items})
    errors += [f'{j} 在 {filed[j]} 里出现过但台账没登记——台账在漏行' for j in missing]

    settled = sum(1 for it in items if it['state'] != JUDGE_PENDING)
    summary = (f'判断 {len(items)} 条（待判 {len(items) - settled}／已结算 {settled}）'
               f'· 到期未结算 {len(due)} · 未登记 {len(missing)}'
               f' · 卡片引用 {len(refs)} 号'
               + (f'（查无 {len(unknown)}）' if unknown else '')
               + f' · 待回填 {len(pend)} 处')
    verdict = Verdict.FAIL if errors else Verdict.PASS
    return Result(verdict, summary + ('' if not errors else f'  ✗ {len(errors)} 处'),
                  _render(items, errors, due, refs, pend, today))
