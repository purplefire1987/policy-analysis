#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包 `scripts` 的形态判定：是链接、是副本，还是根本没有。

为什么改成链接（2026-10-25）：
    此前是「复制一份 ＋ MANIFEST.json 记 sha256，体检时逐条比对」。那套办法只能
    **事后发现**漂移——本库 4 次事故全都发生了，且都是等到体检或某条报错才暴露，
    中间可能已经按旧代码跑过若干轮。判定再严，也改变不了「同一份代码存在两处」
    这个事实本身。改成符号链接后，物理上只有 `tools/` 一份，漂移不再需要被发现：
    它没有发生的载体。
    代价写在明处：专家包不再自包含（整包拷到别的机器跑不起来）。这个包是本机的
    个人专家、不分发，所以这个代价可以付。真要分发时应该另做「物化」动作，
    而不是把副本当成日常形态——日常形态是什么样的，就会往哪个方向漂。

四种形态，处置各不相同（措辞不同，动作就不同）：
    link    —— 指向 tools：正常
    copy    —— 实体目录：有人拷过，或打包时被物化；**从此开始漂移**
    alien   —— 链接指向别处（或只是个文件）：比副本更危险，它看起来是对的
    missing —— 不存在：技能里写的 scripts/run.py 会直接 404
"""
from pathlib import Path

from .fs import py_files
from .paths import EXPERT_SCRIPTS, TOOLS

LINK, COPY, ALIEN, MISSING = 'link', 'copy', 'alien', 'missing'


def state(dest=None, target=None):
    """`dest` 属于哪种形态。`target` 只给测试用——判据默认是 `tools/` 本体。"""
    dest = Path(dest or EXPERT_SCRIPTS)
    want = Path(target or TOOLS).resolve()
    if dest.is_symlink():
        try:
            return LINK if dest.resolve() == want else ALIEN
        except OSError:
            return ALIEN          # 悬空链接：解不开，一律当"链错地方"
    if dest.is_dir():
        return COPY
    return ALIEN if dest.exists() else MISSING


def link_target(dest=None):
    """链接指向哪儿。不是链接、或解不开，返回空串。"""
    dest = Path(dest or EXPERT_SCRIPTS)
    if not dest.is_symlink():
        return ''
    try:
        return str(dest.resolve())
    except OSError:
        return ''


# 副本里出现这些不算「差异」：解释器缓存与访达的垃圾文件，删了没人损失。
NOISE = {'.DS_Store'}


def _is_noise(p):
    return p.name in NOISE or p.suffix == '.pyc' or '__pycache__' in p.parts


def drift(dest=None, src=None):
    """副本与源树的差异：[(相对路径, '改过'|'包内多'|'包内缺')]。

    只在 state == COPY 时有意义。要删一个目录之前，得先能说出里面有什么不一样——
    因为「不一样」往往意味着有人把修复写在了错误的副本上，那不是可以静默丢弃的东西。

    **比的是全部文件，不只是 .py**（2026-10-26 改）：此前只 `rglob('*.py')`，于是副本里
    一份 README、一张便签、一个 MANIFEST.json 都不算差异——`_clear()` 会把它们连同目录
    一起 rmtree 掉，一句都不说。而这正是本函数存在的理由：「能说出里面有什么不一样」。
    只比 .py 的话，这句话对非代码文件是假的。缓存与 .DS_Store 属噪音，不计入。
    """
    root, src_root = Path(dest or EXPERT_SCRIPTS), Path(src or TOOLS)
    if not root.is_dir():
        return []
    have = {p.relative_to(root).as_posix(): p
            for p in root.rglob('*') if p.is_file() and not _is_noise(p)}
    want = {p.relative_to(src_root).as_posix(): p for p in py_files(src_root)}
    out = []
    for rel in sorted(have):
        if rel not in want:
            out.append((rel, '包内多'))
        elif have[rel].read_bytes() != want[rel].read_bytes():
            out.append((rel, '改过'))
    for rel in sorted(set(want) - set(have)):
        out.append((rel, '包内缺'))
    return out
