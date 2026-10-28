#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""history —— 翻改动历史：这个文件改过几次、这条口径是哪次改的。

补的是「审计只能 grep」：log.md 一千多行，查「这条口径哪次改的」原来要靠人翻，
而 git 早就有答案——`-S` 能直接列出「增删了某句话」的那次提交。
只检索不判断：它不给结论、不说哪次改得对，只说改在哪。
"""
import argparse

from pkb.core import VAULT
from pkb.core.git import available, is_repo, run_git


def _list(args, path):
    """某文件／目录的提交列表：哈希、日期、标题。"""
    cmd = ['log', f'--max-count={args.limit}', '--date=short',
           '--format=%h  %ad  %s']
    if path:
        cmd.append('--follow')
        cmd.append('--')
        cmd.append(path)
    code, out = run_git(*cmd)
    return code, out.strip()


def _word(args):
    """pickaxe：哪些提交增删过这个词。--all 是因为改动可能只在分支上。"""
    cmd = ['log', '--all', f'--max-count={args.limit}', '--date=short',
           '--format=%h  %ad  %s', f'-S{args.word}']
    if args.since:
        cmd.append(f'--since={args.since}')
    code, out = run_git(*cmd)
    return code, out.strip()


def run(argv=None):
    ap = argparse.ArgumentParser(
        prog='history', description='翻 git 历史：文件改过几次／这条口径哪次改的')
    ap.add_argument('path', nargs='?', default='',
                    help='库内相对路径（文件或目录）；不写则看全库')
    ap.add_argument('--word', default='', help='找增删过这个词的提交（pickaxe）')
    ap.add_argument('--since', default='', help='只看到此日期之后（YYYY-MM-DD）')
    ap.add_argument('--limit', type=int, default=15, help='最多几条（默认 15）')
    args = ap.parse_args(list(argv or []))

    if not available():
        print('本机没有 git 可执行文件，查不了历史')
        return 2
    if not is_repo():
        print(f'资料库不在版本控制：{VAULT} 不是 git 仓库——没有历史可查')
        print('处置：git init 后建基线提交（见 log.md 2026-10-28）')
        return 2

    if args.word:
        code, out = _word(args)
        title = f'哪些提交增删过「{args.word}」'
    else:
        code, out = _list(args, args.path)
        title = f'历史：{args.path or "全库"}'
    if code != 0:
        print(f'git 返回 {code}：{out[:200]}')
        return 2

    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)
    if not out:
        print('  （没有匹配的提交）')
    else:
        for line in out.splitlines():
            print('  ' + line)
        print(f'\n  共 {len(out.splitlines())} 条（上限 {args.limit}，--limit 可改）')
    print('\n  提示：`history <路径>` 看某文件；`history --word 词` 看这句话哪次被加进来／删掉')
    return 0
