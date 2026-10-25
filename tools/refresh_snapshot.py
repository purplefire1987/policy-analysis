#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新知识库里的「统计快照」，避免手写数字长期漂移。

用法：
    python3 tools/refresh_snapshot.py            # 刷新并写入
    python3 tools/refresh_snapshot.py --dry-run  # 只看差异，不写

它会做三件事，全部作用在 index.md 一处：
1. 扫描 wiki/政策卡片/，统计产业卡数、每张卡的政策数（取 frontmatter `政策数`）；
2. 按卡片的 `所属政策链` 汇总每条链的「卡数」与「政策数」，重写 index.md 第二节
   表格的末两列，并把快照日期改成今天；
3. 校正 index.md 的「共 N 张产业卡」。

设计取舍：
- 2026-10-24 起「政策链总览」已并入 index.md（原本两页各写一份同样的表，
  改一处漏一处）。所以本脚本只读写一个文件，不再有跨页同步问题。
- 卡数是结构事实，实时反映；政策数是快照，允许在两次刷新之间滞后。
- 只改数字与日期，不改表格里的卡片名单（名单变更是结构变更，须人工或结构校验）。
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date

from lib import CARD_DIR, INDEX  # 路径唯一定义处：lib.py


def collect():
    cards = defaultdict(int)
    policies = defaultdict(int)
    n_cards = 0
    n_policies = 0
    for p in sorted(CARD_DIR.glob('*.md')):
        t = p.read_text(encoding='utf-8')
        m = re.match(r'---\n(.*?)\n---', t, re.S)
        if not m:
            continue
        fm = m.group(1)
        n_cards += 1
        cnt = 0
        mc = re.search(r'^政策数:\s*(\d+)', fm, re.M)
        if mc:
            cnt = int(mc.group(1))
        n_policies += cnt
        mch = re.search(r'^所属政策链:\s*"?\[\[政策链-(.+?)\]\]"?', fm, re.M)
        if mch:
            cards[mch.group(1).strip()] += 1
            policies[mch.group(1).strip()] += cnt
    return n_cards, n_policies, cards, policies


def refresh(n_cards, cards, policies, today, dry):
    if not INDEX.exists():
        print('路径错误：未找到 index.md', INDEX)
        return 0
    t = INDEX.read_text(encoding='utf-8')
    changes = 0

    def fix_row(m):
        nonlocal changes
        line = m.group(0)
        mm = re.search(r'政策链-([^\\|\]]+)', line)
        if not mm:
            return line
        name = mm.group(1).strip()
        k, v = cards.get(name), policies.get(name)
        if k is None:
            return line
        cells = line.strip().strip('|').split('|')
        if len(cells) < 3:
            return line
        if cells[-2].strip() != str(k) or cells[-1].strip() != str(v):
            changes += 1
        cells[-2], cells[-1] = f' {k} ', f' {v} '
        return '|' + '|'.join(cells) + '|'

    t = re.sub(r'^\| \[\[政策链-.*$', fix_row, t, flags=re.M)

    # 快照日期：「（快照 YYYY-MM-DD）」
    t2 = re.sub(r'快照 \d{4}-\d{2}-\d{2}', f'快照 {today}', t)
    if t2 != t:
        changes += 1
        t = t2

    # 「共 N 张产业卡」
    t2 = re.sub(r'共 \d+ 张产业卡', f'共 {n_cards} 张产业卡', t)
    if t2 != t:
        changes += 1
        t = t2

    if changes and not dry:
        INDEX.write_text(t, encoding='utf-8')
    return changes


def main():
    ap = argparse.ArgumentParser(description='刷新 index.md 统计快照')
    ap.add_argument('--dry-run', action='store_true', help='只看差异，不写')
    args = ap.parse_args()
    dry = args.dry_run
    today = date.today().isoformat()
    n_cards, n_policies, cards, policies = collect()
    if n_cards == 0:
        print('未找到产业卡，检查路径：', CARD_DIR)
        return 2
    c = refresh(n_cards, cards, policies, today, dry)
    print(f'{"[dry-run] " if dry else ""}产业卡 {n_cards} 张 | 政策 {n_policies} 项')
    for name in sorted(cards):
        print(f'  {name:<12} 卡 {cards[name]:>2} | 政策 {policies[name]:>3}')
    print(f'\nindex.md：{c} 处更新' + ('（未写入）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
