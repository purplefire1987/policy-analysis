#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""观点覆盖率校验：三分类统计，只报进度（恒 PASS）。

为什么独立成一个检查：它原本是 structure 的第 [7] 类，但两类问题语义不同——
结构错误要阻断（FAIL 必须修），观点欠账只报进度（要联网检索，脚本修不了）。
挤在同一个退出码里，欠账会淹没真问题。

三分类口径（与 plan_backlog 的 scan_cards 对齐）：
  a 完整    ——「各方观点」「观点辨析」两个标题都在，且不含（待补全）
  b 待补全  ——标题在，内容是（待补全）占位
  c 无观点  ——缺任一标题
覆盖率 = a / 总小节数，b 计未覆盖。<80% 标红（仅提示，不阻断）。
"""
import argparse

from pkb.core import CARD_DIR, extract_sections, Result, Verdict

RED_LINE = 80.0


def classify(chunk):
    has_head = '**各方观点**' in chunk and '**观点辨析**' in chunk
    if has_head and '（待补全）' not in chunk:
        return 'a'
    if has_head:
        return 'b'
    return 'c'


def run(argv=None):
    """返回 Result；明细在 lines，不打印。"""
    ap = argparse.ArgumentParser(description='观点覆盖率校验（只报进度，不阻断）')
    ap.add_argument('--quiet', action='store_true', help='只给出覆盖率一行')
    args = ap.parse_args(list(argv or []))

    if not CARD_DIR.exists():
        msg = f'✗ 未找到产业卡目录：{CARD_DIR}'
        return Result(Verdict.BAD_INPUT, f'产业卡目录不存在：{CARD_DIR}', [msg])

    a_items, b_items, c_items = [], [], []
    for p in sorted(CARD_DIR.glob('*.md')):
        name = p.stem.replace('政策卡片-', '')
        text = p.read_text(encoding='utf-8')
        secs, _ = extract_sections(text)
        for d, t, chunk, _raw in secs:
            label = f'{name} → {d} · {t}'
            cls = classify(chunk)
            (a_items if cls == 'a' else b_items if cls == 'b' else c_items).append(label)

    total = len(a_items) + len(b_items) + len(c_items)
    cov = len(a_items) / total * 100 if total else 100.0
    mark = '🔴' if cov < RED_LINE else '🟢'
    head = (f'观点覆盖率 {len(a_items)}/{total} = {cov:.1f}%（a {len(a_items)}／'
            f'b {len(b_items)}／c {len(c_items)}）{mark}')

    if args.quiet:
        line = (f'观点覆盖率 {len(a_items)}/{total} = {cov:.1f}% {mark}'
                f'（待补全 {len(b_items)}／无观点 {len(c_items)}）')
        return Result(Verdict.PASS, head, [line])

    lines = ['=== 观点覆盖率 ===',
             f'{mark} 覆盖率 {len(a_items)}/{total} = {cov:.1f}%'
             f'（a 完整 {len(a_items)}／b 待补全 {len(b_items)}／c 无观点 {len(c_items)}）']
    if cov < RED_LINE:
        lines.append(f'低于 {RED_LINE:.0f}% 红线。补录节奏与配额见 `run.py plan` 第 4、5 段。')
    if b_items:
        lines += ['', f'待补全（b，{len(b_items)} 个，前 20）：']
        lines += [f'  · {x}' for x in b_items[:20]]
    if c_items:
        lines += ['', f'无观点（c，{len(c_items)} 个，前 20）：']
        lines += [f'  · {x}' for x in c_items[:20]]
    lines.append('')
    lines.append('（本项为历史欠账进度，恒 exit 0，不阻断结构校验结论）')

    summary = head + (f'，低于 {RED_LINE:.0f}% 红线' if cov < RED_LINE else '')
    return Result(Verdict.PASS, summary, lines)
