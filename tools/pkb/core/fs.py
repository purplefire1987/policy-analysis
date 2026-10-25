#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件读写：遍历、读、写、哈希。

判据：同一件事在两处以上出现，就搬到这里。
"""
import hashlib
from pathlib import Path

from .paths import VAULT, SKIP_DIRS


def md_files(skip_log=True, roots=None):
    """全库 md 文件（已排除 .obsidian/.trash）。

    skip_log：log.md 是历史，多数校验应跳过；只有 log 卫生检查会显式带上它。
    """
    bases = roots or [VAULT]
    seen = set()
    for base in bases:
        if not Path(base).exists():
            continue
        for p in sorted(Path(base).rglob('*.md')):
            if any(d in p.parts for d in SKIP_DIRS):
                continue
            if skip_log and p.name == 'log.md':
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


def read(p, default=None):
    """读文本。文件不存在时：给了 default 就返回 default，否则抛异常。

    default 参数的由来：check_docs 与 plan_backlog 各自写过「文件不存在返回空串」
    的 read——同一件事两份拷贝，漏改不报错。统一到这里。
    """
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        raise FileNotFoundError(p)
    return p.read_text(encoding='utf-8', errors='ignore')


def write(p, text):
    Path(p).write_text(text, encoding='utf-8')


def digest(p):
    """文件内容的 sha256（副本是否同一份，只认这个）。

    为什么在共用层：导出时写清单、体检时比清单，是同一次计算的两端。
    两边各写一份哈希实现，正是本项目反复出事的「副本漂移」。
    """
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def all_names():
    """全库页面名（不含 .md），用于 wikilink 断链判断。"""
    return {p.stem for p in md_files(skip_log=False)}


def py_files(root, subdir='pkb'):
    """工具脚本树：root 下的 *.py ＋ root/<subdir> 包内的 *.py。

    「哪些文件该被导出/校验」只在这里定义一次——导出（写清单）与体检（比清单）
    是同一次判定的两端，各写一份就会漂（本库历史上 4 次事故都是这么来的）。
    """
    root = Path(root)
    out = [p for p in sorted(root.glob('*.py')) if p.is_file()]
    pkg = root / subdir
    if pkg.exists():
        out += [p for p in sorted(pkg.rglob('*.py')) if '__pycache__' not in p.parts]
    return out
