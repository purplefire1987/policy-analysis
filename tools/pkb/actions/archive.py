#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive_index —— 给 `归档/` 生成索引页。

为什么要有（2026-10-28）：归档目录此前只能 `ls` 着找，而「归档了」这件事本身
需要能被读到——不知道里面有什么，就等于没有归档。索引页还有一个用处：
`raw/articles/` 的每份原文在这里都被链一次，于是断链检查会覆盖到它们
（原文文件被改名/移走时立刻报出来）。

覆盖式重写：它由目录内容生成，手改的部分下次就被冲掉——页首写明这一点。
不写数量读数：数量会变，而这类页面最容易被当成「权威统计」引用。
"""
import argparse
import datetime
import re

from pkb.core import (ARTICLE_DIR, CARD_DIR, VAULT, read, write,
                      card_files, card_parts, card_name, extract_sections)
from pkb.domain import retired

ARCHIVE_DIR = VAULT / '归档'
BACKUP_DIR = ARCHIVE_DIR / '备份'
INDEX = ARCHIVE_DIR / 'index.md'

HEAD = """# 归档索引

> 本页由 `python3 tools/run.py archive` 覆盖式重写，**不要手改**。
> 内容生成于：{ts}（**内容变了才更新，不是每次运行时间**）
> 保留策略见 [[AGENTS]] 第十一节（「删了还能重建吗」）。

## 一、政策原文存档（`raw/articles/`）

一手原文，`run.py fetch` 落盘，只增不改。按日期倒序：

{rows}

## 二、已终止的政策

**归档只认这一种**（2026-10-28 定）：政策被明文废止／取代／失效时，在小节里写
`> **状态**：已废止（被 YYYY-MM-DD《新政策名》取代）`，它就出现在下面这张表里。

不按时间归档——按时间淘汰等于按重要性淘汰，而「三年前的判断」与「三个月前的判断」
价值相同。**已废止是事实判断，可以逐条核；「够老了」不是。**

{retired}

## 三、固定归档

{files}

## 四、备份包（`归档/备份/`）

{backups}
"""

STAMP = re.compile(r'^> 内容生成于：.*$', re.M)


def _same(old, new):
    """只差时间戳就算「没变」。

    为什么必须幂等（2026-10-28 挂成定时任务时才暴露）：原先无条件写盘，
    模板里带时间戳，于是**每次运行都产出一次 diff**——每周跑一次，一年的
    提交历史就多 52 条「只有时间变了」的噪音。定时任务不能只靠「人不在场
    就不会乱改」来保证安静。
    """
    return STAMP.sub('', old) == STAMP.sub('', new)


def _rows():
    if not ARTICLE_DIR.exists():
        return ['（空）']
    items = []
    for p in sorted(ARTICLE_DIR.glob('*.md'), reverse=True):
        parts = p.stem.split('_')
        date = parts[0] if parts else ''
        rest = '　'.join(parts[1:]) if len(parts) > 1 else p.stem
        items.append(f'- `{date}`　[[{p.stem}]]　{rest}')
    return items or ['（空）']


def _retired():
    """已终止的政策清单：日期 · 卡片 · 标题 · 被谁取代。

    读的是**卡片本身**，不是另建的清单——另建一份就意味着「卡片改了它不知道」。
    序列卡的小节在卷里，所以走 card_parts 合并，否则大卡里废止的政策永远不出现。
    """
    out = []
    for p in card_files(CARD_DIR):
        name = card_name(p)
        for part in card_parts(p):
            for d, t, chunk, _r in extract_sections(read(part, ''))[0]:
                st = retired(chunk)
                if st:
                    out.append(f'- `{d}`　[[政策卡片-{name}]]　{t}　— {st[0]}{st[1]}')
    return sorted(out, reverse=True) or ['（当前没有已终止的政策）']


def _files():
    out = []
    for p in sorted(ARCHIVE_DIR.glob('*.md')):
        if p.name == 'index.md':
            continue
        out.append(f'- [[{p.stem}]]')
    for d in sorted(p for p in ARCHIVE_DIR.iterdir() if p.is_dir()):
        if d.name in ('备份', '导出'):
            continue
        n = len(list(d.glob('*')))
        out.append(f'- `{d.name}/`（{n} 个文件）')
    return out or ['（空）']


def _backups():
    if not BACKUP_DIR.exists():
        return ['（空）']
    items = []
    for p in sorted(BACKUP_DIR.glob('*'), reverse=True)[:20]:
        kb = max(1, p.stat().st_size // 1024)
        ts = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d')
        items.append(f'- `{p.name}`　{ts}　{kb} KB')
    more = len(list(BACKUP_DIR.glob('*'))) - 20
    if more > 0:
        items.append(f'- 另有 {more} 份更早的包（只列最近 20 份）')
    return items


def run(argv=None):
    ap = argparse.ArgumentParser(prog='archive', description='生成 归档/index.md（覆盖写）')
    ap.add_argument('--check', action='store_true', help='只打印统计，不写盘')
    args = ap.parse_args(list(argv or []))

    blocks = {'rows': _rows(), 'retired': _retired(), 'files': _files(),
              'backups': _backups()}
    text = HEAD.format(ts=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                       **{k: '\n'.join(v) for k, v in blocks.items()})
    print('\n' + '=' * 62)
    print('归档索引')
    print('=' * 62)
    print('  ' + ' · '.join(f'{k} {len(v)} 行' for k, v in blocks.items()))
    if args.check:
        print('\n  （--check：未写盘）')
        return 0
    if _same(read(INDEX, ''), text):
        print('\n  内容未变，未写盘（时间戳只随内容更新）')
        return 0
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    write(INDEX, text)
    print(f'\n  已写入 归档/index.md（{len(text)} 字符）')
    return 0
