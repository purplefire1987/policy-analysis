#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：link —— 让专家包的脚本入口指向 `tools/` 本体，不保留第二份代码。

用法
----
    python3 tools/run.py link            归位：不是链接就建成链接
    python3 tools/run.py link --check    只核对不写盘；不是链接 exit 1
    python3 tools/run.py link --force    副本里有改动也照样删掉重建

为什么不再是「导出」
--------------------
    同源问题的解不是「复制得更及时」，是**不要有第二份**。此前 export 复制一份并写
    MANIFEST.json 记 sha256，靠体检事后发现漂移；4 次事故说明发现得太晚。链接把
    「保持同源」从一个需要维护的纪律，变成文件系统的事实。
    所以动作名也换了：它不再导出任何东西，它做的是一件事——把入口接回本体。

边界
----
    · 只动 `skills/policy-kb-tools/scripts`；SKILL.md／plugin.json／agents 不碰。
    · 副本里若有与 `tools/` 不一致的改动，默认**拒绝删除并逐条列出**：那通常意味着
      有人把修复写在了错误的副本上。要丢弃必须显式 `--force`——脚本不替人决定。
    · 建成链接后真跑一次 `<链接>/run.py --help`。链接存在 ≠ 能跑：Python 的
      `__file__` 走的是符号路径，路径常量若按物理路径写死，只有真跑才暴露。

退出码：归位成功 0；`--check` 已是链接 0、否则 1；副本有改动且未加 `--force` 1；
入口自检失败 1。
"""
import argparse
import shutil
import subprocess
import sys

from pkb.core import EXPERT_SCRIPTS, TOOLS, expert


def _print_drift(items):
    for rel, kind in items:
        print(f'  · [{kind}] {rel}')


def _report(dest):
    """`--check`：只说事实，一个字节都不写。"""
    st = expert.state(dest)
    if st == expert.LINK:
        print(f'专家包入口是链接：{dest} → {TOOLS}（同一份代码，无副本）')
        return 0
    if st == expert.COPY:
        print(f'专家包入口是实体副本：{dest}')
        _print_drift(expert.drift(dest))
        print('副本形态本身就是错的——跑 `run.py link` 还原成链接。')
        return 1
    if st == expert.MISSING:
        print(f'专家包入口不存在：{dest}')
    else:
        print(f'专家包入口指向别处：{dest} → {expert.link_target(dest) or "(悬空)"}（应为 {TOOLS}）')
    print('跑 `run.py link` 归位。')
    return 1


def _clear(dest):
    """删掉占位物（链接／目录／普通文件）。返回是否真删了东西。"""
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
        return True
    if dest.is_dir():
        shutil.rmtree(dest)
        return True
    return False


def _verify(dest):
    """建成后真跑一次入口——符号链接存在不等于能跑。"""
    try:
        r = subprocess.run([sys.executable, str(dest / 'run.py'), '--help'],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)[:200]
    if r.returncode == 0 and '可用动作' in r.stdout:
        return True, ''
    return False, (r.stderr or r.stdout or '').strip()[:300]


def _ensure(dest, force):
    st = expert.state(dest)
    if st == expert.LINK:
        print(f'专家包入口已就位（{dest} → {TOOLS}），无需改动')
        return 0
    if st == expert.COPY:
        items = expert.drift(dest)
        if items and not force:
            print(f'副本里有 {len(items)} 处与 tools 不一致，先别删：')
            _print_drift(items)
            print('确认可以丢弃后跑 `run.py link --force`；'
                  '若这些改动该保留，先搬回 tools/ 再跑 link。')
            return 1
        if items:
            print(f'按 --force 丢弃副本里的 {len(items)} 处差异')
    removed = _clear(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(TOOLS)
    print(f'专家包入口已接回本体：{dest} → {TOOLS}' + ('（原副本已删除）' if removed else ''))
    good, detail = _verify(dest)
    if not good:
        print('入口自检失败：<链接>/run.py --help 没能正常退出')
        if detail:
            print('  ' + detail)
        print('链接在、代码跑不起来——查 pkb/core/paths.py 的 TOOLS 与 sys.path 假设')
        return 1
    print('入口自检：<链接>/run.py --help 正常')
    return 0


def run(argv=None):
    ap = argparse.ArgumentParser(description='让专家包脚本入口指向 tools 本体（符号链接）')
    ap.add_argument('--check', action='store_true', help='只核对不写盘；不是链接 exit 1')
    ap.add_argument('--force', action='store_true', help='副本里有改动也删掉重建')
    args = ap.parse_args(list(argv or []))
    return _report(EXPERT_SCRIPTS) if args.check else _ensure(EXPERT_SCRIPTS, args.force)
