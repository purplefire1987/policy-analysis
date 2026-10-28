#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""观点覆盖率校验：三分类统计，只报进度（恒 PASS）。

为什么独立成一个检查：它原本是 structure 的第 [7] 类，但两类问题语义不同——
结构错误要阻断（FAIL 必须修），观点欠账只报进度（要联网检索，脚本修不了）。
挤在同一个退出码里，欠账会淹没真问题。

三分类口径（与 plan_backlog 的 scan_cards 对齐，判定本身在 domain.fields.views_state）：
  a 完整    ——「各方观点」「观点辨析」两个标题都在，且**这两节范围内**不含（待补全）
  b 待补全  ——标题在，内容是（待补全）占位
  c 无观点  ——缺任一标题
覆盖率 = a / 总小节数，b 计未覆盖。<80% 标红（仅提示，不阻断）。
"""
import argparse

from pkb.core import (CARD_DIR, extract_sections, table_rows, read,
                      card_files, card_parts, card_name, Result, Verdict)
from pkb.domain.fields import views_state, VIEW_ROWS_MIN

RED_LINE = 80.0


def classify(chunk):
    return views_state(chunk)


def _n_rows(chunk):
    """「各方观点」表格里的数据行数（`table_rows` 已跳过表头与分隔行）。"""
    seg = chunk.split('**各方观点**', 1)[1].split('**观点辨析**')[0]
    return len(table_rows(seg.split('\n')))


def _report(a, b, c, thin, cov, mark):
    """明细行。覆盖率与「条数不足」是两件事，分段打。"""
    total = a + b + c
    lines = ['=== 观点覆盖率 ===',
             f'{mark} 覆盖率 {a}/{total} = {cov:.1f}%（a 完整 {a}／b 待补全 {b}／c 无观点 {c}）']
    if cov < RED_LINE:
        lines.append(f'低于 {RED_LINE:.0f}% 红线。补录节奏与配额见 `run.py plan` 第 4、5 段。')
    if thin:
        lines += ['', f'写着观点但不足 {VIEW_ROWS_MIN} 条（{len(thin)} 个，前 20）'
                      f'——不算欠账，但达不到模板的 5~8 条：']
        lines += [f'  · {x}（{n} 条）' for x, n in thin[:20]]
    if b:
        lines += ['', f'待补全（b，{b} 个，前 20）——先补这些，它们计未覆盖：']
    lines.append('')
    lines.append('（本项为历史欠账进度，恒 exit 0，不阻断结构校验结论）')
    return lines


def iter_sections():
    """[(卡片名, 日期, 标题, 小节正文)]——扁平卡与序列卷一并展开。

    序列卡的小节在卷里（2026-10-28）：只扫 `CARD_DIR.glob('*.md')` 会漏掉四张
    大卡的全部小节，而报告上只会显示「总数变小」，**看不出少了谁**。
    """
    for p in card_files(CARD_DIR):
        name = card_name(p)
        for part in card_parts(p):
            for d, t, chunk, _raw in extract_sections(read(part, ''))[0]:
                yield name, d, t, chunk


def run(argv=None):
    """返回 Result；明细在 lines，不打印。"""
    ap = argparse.ArgumentParser(description='观点覆盖率校验（只报进度，不阻断）')
    ap.add_argument('--quiet', action='store_true', help='只给出覆盖率一行')
    args = ap.parse_args(list(argv or []))

    if not CARD_DIR.exists():
        msg = f'✗ 未找到产业卡目录：{CARD_DIR}'
        return Result(Verdict.BAD_INPUT, f'产业卡目录不存在：{CARD_DIR}', [msg])

    a_items, b_items, c_items, thin = [], [], [], []
    for name, d, t, chunk in iter_sections():
        label = f'{name} → {d} · {t}'
        cls = classify(chunk)
        if cls == 'a':
            a_items.append(label)
            n = _n_rows(chunk)
            if n < VIEW_ROWS_MIN:
                thin.append((label, n))
        else:
            (b_items if cls == 'b' else c_items).append(label)

    a, b, c = len(a_items), len(b_items), len(c_items)
    total = a + b + c
    cov = a / total * 100 if total else 100.0
    mark = '🔴' if cov < RED_LINE else '🟢'
    head = (f'观点覆盖率 {a}/{total} = {cov:.1f}%（a {a}／b {b}／c {c}）{mark}'
            + (f'，另有 {len(thin)} 个不足 {VIEW_ROWS_MIN} 条' if thin else ''))

    if args.quiet:
        return Result(Verdict.PASS, head, [head])

    lines = _report(a, b, c, thin, cov, mark)
    if b_items:
        lines += [f'  · {x}' for x in b_items[:20]]
    if c_items:
        lines += ['', f'无观点（c，{c} 个，前 20）：'] + [f'  · {x}' for x in c_items[:20]]
    summary = head + (f'，低于 {RED_LINE:.0f}% 红线' if cov < RED_LINE else '')
    return Result(Verdict.PASS, summary, lines)
