#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：把超限卡按日期拆成「文件夹序列卡」。

跑法（默认只报计划，不写盘）：
    python3 tools/scripts/split_cards.py            # dry-run，打印切分方案
    python3 tools/scripts/split_cards.py --apply    # 写盘

拆出来长什么样
--------------
    wiki/政策卡片/政策卡片-金融/
        政策卡片-金融.md       主卡：frontmatter、基本信息、序列索引表
        2025-02至2026-06.md    卷一（8 项）
        2026-07至2026-10.md    卷二（5 项）

为什么按日期而不是按主题切：卡片本来就是「按时间倒序」的编年体，按主题切会
把一个政策的演进拆散到两卷里；按日期切只在时间轴上断开一处，读者知道「往下
就是更早的」。

为什么每卷上限取 19000：`CARD_SIZE_WARN` 是 20000，卷文件还要加标题与扉行，
留 1000 字符余量。**装箱从最旧往最新装**，这样最新那一卷总是「正在增长」的，
下次添政策只需追加，不必重排历史卷。
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import (CARD_DIR, card_files, card_name, extract_sections,  # noqa: E402
                      parse_fm, read, write)
from pkb.domain import CARD_SIZE_WARN                                          # noqa: E402

BUDGET = CARD_SIZE_WARN - 1000

# 主卡除了 frontmatter／callout，可能还有一段「## 政策演进」下的小节之外的正文。
SEC_HEAD = re.compile(r'(?m)^### ')


def split_header(text):
    """→ (前半, 小节列表 raw_chunks)。前半到第一个 `### ` 之前为止。"""
    m = SEC_HEAD.search(text)
    if not m:
        return text, []
    return text[:m.start()], text[m.start():]


def pack(secs, budget=BUDGET):
    """按「旧→新」装箱，每箱正文合计 ≤ budget → [[(d, t, raw), ...], ...]。

    装入的是原始 chunk 而不是重新渲染：小节正文里有表格、列表、粗体，
    重新生成一遍等于把 157 个节各重写一次，任何一处措辞不同都是新的漂移。
    """
    boxes, cur, size = [], [], 0
    for item in sorted(secs, key=lambda x: x['date']):
        n = len(item['raw'])
        if cur and size + n > budget:
            boxes.append(cur)
            cur, size = [], 0
        cur.append(item)
        size += n
    if cur:
        boxes.append(cur)
    return boxes


def vol_name(box):
    """卷文件名＝本卷日期区间：`2025-02至2026-06`；同一月内只写 `2026-10`。

    为什么用区间而不是卷号：卷号要人记「第几卷覆盖哪段」，而区间本身就是答案，
    且字典序＝时间序（`2026-07至2026-09` < `2026-10`），
    `fs.card_parts` 靠文件名倒排就能拿到「新的在前」。
    """
    a, b = box[0]['date'][:7], box[-1]['date'][:7]
    return a if a == b else f'{a}至{b}'


def render_vol(card, box, idx, total):
    """一卷的正文：扉行写清「本卷是第几卷、几项、怎么回到主卡」，小节倒序。"""
    head = (f"# {card} · {vol_name(box).replace('至', ' 至 ')}\n\n"
            f"> 序列第 {idx} 卷／共 {total} 卷 ｜ 本卷 {len(box)} 项 ｜ "
            f"回到 [[政策卡片-{card}]]\n"
            f">\n"
            f"> 卷内按时间倒序，最新在前。上一卷（更新）／下一卷（更早）见主卡索引表。\n\n"
            f"## 政策演进（按时间倒序，最新第一）\n\n")
    body = '\n'.join(item['raw'].rstrip('\n') + '\n'
                     for item in sorted(box, key=lambda x: x['date'], reverse=True))
    return head + body


def render_main(card, header, boxes):
    """主卡：原头部（frontmatter＋标题＋callout）＋序列索引表。"""
    # 去掉头部的 `## 政策演进` 标题——小节已经不在主卡里，留着是空壳
    head = re.sub(r'(?m)^##\s*政策演进.*$', '', header).rstrip('\n')
    rows = ['', '## 政策演进（按时间倒序，最新第一）', '',
            f'本卡共 {sum(len(b) for b in boxes)} 项，按日期分 {len(boxes)} 卷。'
            '**先读最上面那一卷**：', '',
            '| 卷 | 覆盖日期 | 项数 |', '|---|---|---|']
    for i, box in enumerate(reversed(boxes), 1):
        d0, d1 = box[0]['date'], box[-1]['date']
        rows.append(f'| [[政策卡片-{card}/{vol_name(box)}]] | {d0} ~ {d1} | {len(box)} |')
    rows += ['',
             '> 为什么拆：单卡超过 20000 字符时，每加一条政策都要把全文读一遍，'
             '读的是历史，改的只有末尾。按日期切卷后，新政策只进最新那一卷。',
             '> 卷不是新卡：frontmatter 的 `政策数` 与 `时间跨度` 仍指**全卡**。']
    return head + '\n' + '\n'.join(rows) + '\n'


def plan_one(p):
    """→ (卡片名, 头部, 箱子) 或 None（不需要拆）。"""
    text = read(p)
    if len(text) <= CARD_SIZE_WARN:
        return None
    header, _ = split_header(text)
    body = text[len(header):]
    secs = []
    for d, t, chunk, raw_line in extract_sections(body)[0]:
        # 第 4 个返回值只有标题行本身，整段要自己拼——拼错的话拆出来的卷会丢正文
        secs.append({'date': d, 'title': t, 'raw': raw_line + '\n' + chunk})
    if not secs:
        return None
    boxes = pack(secs)
    # 已经是一卷（拆了没意义，比如 20 节全是同一天）就照拆，但至少说明
    return card_name(p), header, boxes


def main(argv=None):
    ap = argparse.ArgumentParser(prog='split_cards', description='超限卡按日期拆卷（dry-run 默认）')
    ap.add_argument('--apply', action='store_true', help='真写盘')
    ap.add_argument('--only', default='', help='只处理名字含该词的卡')
    args = ap.parse_args(argv)

    todo = []
    for p in card_files():
        if p.parent != CARD_DIR:            # 已经是目录形态，跳过
            continue
        if args.only and args.only not in p.stem:
            continue
        got = plan_one(p)
        if got:
            todo.append((p, got))

    if not todo:
        print('没有超过 %d 字符的扁平卡，无需拆分。' % CARD_SIZE_WARN)
        return 0

    for p, (name, header, boxes) in todo:
        print(f'\n=== {name}（{len(read(p))} 字符 → {len(boxes)} 卷）===')
        for i, box in enumerate(boxes, 1):
            n = sum(len(x['raw']) for x in box)
            print(f'  卷{i} {vol_name(box):<18} {len(box):>2} 项  {n:>6} 字符  '
                  f'{box[0]["date"]} ~ {box[-1]["date"]}')

    if not args.apply:
        print('\n（dry-run：加 --apply 才写盘）')
        return 0

    for p, (name, header, boxes) in todo:
        d = CARD_DIR / f'政策卡片-{name}'
        d.mkdir(parents=True, exist_ok=True)
        for i, box in enumerate(boxes, 1):
            write(d / f'{vol_name(box)}.md', render_vol(name, box, i, len(boxes)))
        # 主卡最后写：万一中途失败，旧卡还在，不会两头空
        write(d / f'政策卡片-{name}.md', render_main(name, header, boxes))
        p.unlink()
        parts = [len(read(x)) for x in sorted(d.glob('*.md'))]
        print(f'已拆 {name}：主卡 + {len(boxes)} 卷，体积 {parts}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
