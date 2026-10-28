#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件读写：遍历、读、写、哈希。

判据：同一件事在两处以上出现，就搬到这里。
"""
import hashlib
from pathlib import Path

from .paths import VAULT, TOOLS, SKIP_DIRS, CARD_DIR

CARD_PREFIX = '政策卡片-'


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


def action_names():
    """`pkb/actions/` 的动作名：**文件名即动作名**，下划线开头是内部件。

    为什么在共用层：两个调用方都要它——`actions/list.py` 用来列清单（不手写名单），
    `checks/prompts.py` 用来验「提示词里写的 `run.py <动作>` 是否真的存在」。
    各写一份 glob 就是又一份副本；而 checks 不许反向 import actions，所以只能下沉。
    走文件系统而不 import 包，是为了让 core 不依赖上层。
    """
    d = TOOLS / 'pkb' / 'actions'
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob('*.py') if not p.stem.startswith('_'))


def card_files(base=None):
    """卡片主文件——**全库唯一的卡片发现规则**。

    两种形态共存（2026-10-28 引入序列卡）：
    * 扁平：`政策卡片-X.md`                      —— 常态，单卷装得下的卡；
    * 目录：`政策卡片-X/政策卡片-X.md` ＋ 若干卷  —— 单卡超限时按日期拆卷。

    为什么下沉到这里：此前 5 处各自 `CARD_DIR.glob('*.md')`（structure／archives／
    views／weeks／docs）。拆卷后这 5 份 glob 会同时看不见卷里的小节——**判据不会
    报错，只会静默少数**，正是本项目最怕的那类失效。

    base 显式传入而不是直接用模块里的 CARD_DIR：测试把目录指到临时库时，
    「patch 了调用方的 CARD_DIR、函数却读 fs 的 CARD_DIR」会让测试悄悄去扫真库，
    本地绿、CI 空库红。**扫描哪个库必须是调用方说了算。**
    """
    base = Path(base) if base is not None else CARD_DIR
    if not base.exists():
        return []
    flat = [p for p in base.glob('*.md') if p.is_file()]
    nested = [p for d in base.iterdir() if d.is_dir()
              for p in d.glob(f'{CARD_PREFIX}*.md')]
    return sorted(flat + nested)


def card_volumes(main):
    """主卡的序列卷：同目录下除主文件外的 .md，按文件名（＝日期区间）升序。

    扁平卡没有目录，自然没有卷。卷不是独立卡片，不该出现在卡片清单里。
    这里不需要 base：卷一定在主文件旁边，主文件已经定位好了。
    """
    main = Path(main)
    if main.parent == CARD_DIR:
        return []
    return sorted(p for p in main.parent.glob('*.md') if p != main)


def card_parts(main):
    """[主文件] + 卷（卷按新的在前）——判据合并小节时一律走这个顺序。

    顺序即「时间倒序」：主卡若仍留有小节，它装的是最新的；其后依次是较新的卷。
    `check_numbers` 判「小节未按时间倒序」依赖这个顺序不被重排——
    合并后再 sort 一次，那条判据就永远查不出问题了。
    """
    vols = card_volumes(main)
    return [Path(main)] + sorted(vols, reverse=True)


def card_name(main):
    """主文件 → 卡片名（`政策卡片-金融.md` → `金融`）。"""
    return Path(main).stem.replace(CARD_PREFIX, '')
