#!/usr/bin/env python3
"""观点覆盖率校验：三分类统计，只报进度，恒 exit 0。

为什么独立成一个脚本：它原本是 check_structure.py 的第 [7] 类，但两类问题
语义不同——结构错误要阻断（exit 1 必须修），观点欠账只报进度（要联网检索，
脚本修不了）。挤在同一个退出码里，欠账会淹没真问题。

三分类口径（与 plan_backlog.py 的 scan_cards 对齐）：
  a 完整    ——「各方观点」「观点辨析」两个标题都在，且不含（待补全）
  b 待补全  ——标题在，内容是（待补全）占位
  c 无观点  ——缺任一标题
覆盖率 = a / 总小节数，b 计未覆盖。<80% 标红（仅提示，不阻断）。
"""
import argparse
import sys

from pkb.core import CARD_DIR, extract_sections, summary

RED_LINE = 80.0


def classify(chunk):
    has_head = '**各方观点**' in chunk and '**观点辨析**' in chunk
    if has_head and '（待补全）' not in chunk:
        return 'a'
    if has_head:
        return 'b'
    return 'c'


def main():
    ap = argparse.ArgumentParser(description='观点覆盖率校验（只报进度，不阻断）')
    ap.add_argument('--quiet', action='store_true', help='只打印覆盖率一行')
    args = ap.parse_args()

    if not CARD_DIR.exists():
        print(f'✗ 未找到产业卡目录：{CARD_DIR}')
        return 2

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

    if args.quiet:
        print(f'观点覆盖率 {len(a_items)}/{total} = {cov:.1f}% {mark}'
              f'（待补全 {len(b_items)}／无观点 {len(c_items)}）')
        summary(f'观点覆盖率 {len(a_items)}/{total} = {cov:.1f}%（a {len(a_items)}／'
                f'b {len(b_items)}／c {len(c_items)}）{mark}')
        return 0

    print('=== 观点覆盖率 ===')
    print(f'{mark} 覆盖率 {len(a_items)}/{total} = {cov:.1f}%'
          f'（a 完整 {len(a_items)}／b 待补全 {len(b_items)}／c 无观点 {len(c_items)}）')
    if cov < RED_LINE:
        print(f'低于 {RED_LINE:.0f}% 红线。补录节奏与配额见 `run.py plan` 第 4、5 段。')
    if b_items:
        print(f'\n待补全（b，{len(b_items)} 个，前 20）：')
        for x in b_items[:20]:
            print(f'  · {x}')
    if c_items:
        print(f'\n无观点（c，{len(c_items)} 个，前 20）：')
        for x in c_items[:20]:
            print(f'  · {x}')
    print('\n（本项为历史欠账进度，恒 exit 0，不阻断结构校验结论）')
    summary(f'观点覆盖率 {len(a_items)}/{total} = {cov:.1f}%（a {len(a_items)}／'
            f'b {len(b_items)}／c {len(c_items)}）{mark}'
            + (f'，低于 {RED_LINE:.0f}% 红线' if cov < RED_LINE else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
