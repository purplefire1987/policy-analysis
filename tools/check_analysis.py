#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析报告校验：结构、结论三段式、判断表与篇幅。

用法：
    python3 tools/check_analysis.py            # 全量检查
    python3 tools/check_analysis.py --quiet    # 只报问题

为什么需要它：
    分析报告的纪律（AGENTS 第九节十条硬规则）大部分是「义」，脚本查不了；
    但有一部分是「形」——八节结构、结论三段式、判断表修正条件列、8000 字上限。
    历史上这些「形」全靠人记，专题-人工智能管制一稿就曾超字数一倍、
    结论缺检验方式。把能查的形固化下来，人只负责义。

判据来源（单一）：AGENTS.md 第九节 + templates/政策分析报告模板.md。
校验对象：wiki/分析/ 下除「政策分析索引」外的全部报告。

退出码：0 通过（可含提示）；1 有硬错误；2 路径错误。
本脚本不提供 --fix：结构与字数怎么改是写作判断，不是机械修复。
"""

import argparse
import re
import sys

from pkb.core import ANALYSIS_DIR, parse_fm, read, Reporter, summary  # 路径与通用件唯一定义处：pkb/core/paths.py

_rep = Reporter()

ANALYSIS_TYPES = {'产业沿革', '链梳理', '专题评估', '口径对比'}
WORD_LIMIT = 8000  # 正文汉字上限（不含引用清单与 wiki 链接），AGENTS 第九节第 10 条

# 八节骨架：第四节按类型定名，只校验前缀；其余逐字
SPINE = ['一、背景与范围', '二、政策基本情况', '三、演变脉络', '四、',
         '五、主要矛盾', '六、判断', '七、不确定与验证点', '八、引用清单']

errors, warns, oks = _rep.errors, _rep.warns, _rep.oks


def ok(msg):
    _rep.ok(msg)


def err(item, msg):
    _rep.err(item, msg)


def warn(item, msg):
    _rep.warn(item, msg)


def body_for_count(text):
    """字数口径：去 frontmatter；从「八、引用清单」起不计；wiki 链接只留显示文字。"""
    _, body = parse_fm(text)
    body = re.split(r'^##\s+八、引用清单', body, maxsplit=1, flags=re.M)[0]
    body = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', body)
    body = re.sub(r'\[\[([^\]|]+)\]\]', r'\1', body)
    return len(re.findall(r'[一-龥]', body))


def check_report(path):
    name = path.stem
    text = read(path)
    fm, body = parse_fm(text)

    # 1. frontmatter
    if fm.get('类型') != '政策分析':
        err(name, 'frontmatter「类型」应为 政策分析')
    at = fm.get('分析类型', '')
    if at not in ANALYSIS_TYPES:
        err(name, f'frontmatter「分析类型」应为 {"/".join(sorted(ANALYSIS_TYPES))} 之一，现为「{at or "空"}」')
    for k in ('主题', '分析日期'):
        if not fm.get(k):
            err(name, f'frontmatter 缺「{k}」')
    if '修订' in fm:
        warn(name, 'frontmatter 含「修订」字段——修订史记 log.md，不进报告')

    # 2. 八节骨架
    heads = [h.strip() for h in re.findall(r'^##\s+(.+)$', body, re.M)]
    missing = [s for s in SPINE if not any(h.startswith(s) for h in heads)]
    if missing:
        err(name, f'缺节：{"、".join(missing)}')

    # 3. 结论三段式（一级标题下、第一节之前）
    pre = re.split(r'^##\s+一、背景与范围', body, maxsplit=1, flags=re.M)[0]
    for seg in ('目的', '主要结论', '检验方式'):
        if seg not in pre:
            err(name, f'结论段缺「{seg}」')

    # 4. 判断表含修正条件列
    m = re.search(r'^##\s+六、判断.*?(?=^##\s|\Z)', body, re.S | re.M)
    if m and '修正条件' not in m.group(0):
        err(name, '判断表缺「修正条件」列')

    # 5. 篇幅
    n = body_for_count(text)
    if n > WORD_LIMIT:
        err(name, f'正文 {n} 字，超上限 {WORD_LIMIT}（不含引用清单与 wiki 链接）')

    if not any(e[0] == name for e in errors):
        ok(f'{name}：结构／结论段／篇幅（{n} 字）')


def main():
    ap = argparse.ArgumentParser(description='分析报告校验')
    ap.add_argument('--quiet', action='store_true', help='只报问题')
    args = ap.parse_args()
    if not ANALYSIS_DIR.exists():
        print('路径错误：未找到 wiki/分析/')
        return 2

    reports = [p for p in sorted(ANALYSIS_DIR.glob('*.md')) if p.stem != '政策分析索引']
    if not reports:
        print('  （尚无分析报告，跳过）')
        return 0
    for p in reports:
        check_report(p)

    if not args.quiet:
        print('=== 分析报告校验 ===')
    _rep.render(quiet=args.quiet)

    if errors:
        print(f'\n❌ {len(errors)} 项硬错误（{len(warns)} 条提示）')
        summary(f'分析报告 {len(reports)} 篇：{len(errors)} 项硬错误 ❌')
        return 1
    print(f'\n✅ 分析报告 {len(reports)} 篇一致 ✅（{len(warns)} 条提示）')
    summary(f'分析报告 {len(reports)} 篇：结构/结论/篇幅均通过 ✅（{len(warns)} 条提示）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
