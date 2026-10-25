#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 tools/ 下的脚本导出到专家包，并写哈希清单。

用法：
    python3 tools/export_expert.py            # 导出（覆盖专家包内旧副本）
    python3 tools/export_expert.py --check    # 只比对，不写盘；不一致 exit 1

为什么需要它：
    专家包要在别的会话／机器上独立运行，就得自带脚本；自带就必然有第二份副本。
    副本真正的风险不是「会不会漂移」，而是「漂移了没人知道」——所以导出时写
    MANIFEST.json（文件名＋sha256），体检时 check_docs 拿它逐条比对，不一致即 exit 1。

边界：
    · **源永远是 `tools/`**，专家包内那份是部署副本，不许反向修改后再同步回来
      （改回去的话，库外副本又变成了规则本体，正是要防的事）。
    · 只导 `.py`，不导 `__pycache__`；SKILL.md 与 references 是手写的，不在导出范围。
    · 本脚本不读库内文件，只做搬运与记账。

退出码：导出恒 0；`--check` 一致 0、不一致 1。
"""

import argparse
import datetime
import json
import shutil
import sys

from lib import EXPERT_DIR, TOOLS, digest, read

SKILL = EXPERT_DIR / 'skills' / 'policy-kb-tools'
DEST = SKILL / 'scripts'
MANIFEST = SKILL / 'MANIFEST.json'


def sources():
    """待导出的脚本：tools 下的 *.py（排除缓存）。"""
    return sorted(p for p in TOOLS.glob('*.py') if p.is_file())


def load_manifest():
    txt = read(MANIFEST, '')
    if not txt:
        return {}
    try:
        return json.loads(txt).get('files', {})
    except Exception:
        return {}


def do_export():
    DEST.mkdir(parents=True, exist_ok=True)
    old = load_manifest()
    files, added, updated, same = {}, 0, 0, 0
    for p in sources():
        h = digest(p)
        files[p.name] = {'sha256': h, 'size': p.stat().st_size}
        tgt = DEST / p.name
        if not tgt.exists() or old.get(p.name, {}).get('sha256') != h:
            if tgt.exists():
                updated += 1
            else:
                added += 1
            shutil.copy2(p, tgt)
        else:
            same += 1
    MANIFEST.write_text(json.dumps({
        'source': str(TOOLS),
        'exported_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(files),
        'files': files,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'导出到 {DEST}')
    print(f'  新增 {added}｜更新 {updated}｜未变 {same}｜清单 {MANIFEST.name} 记 {len(files)} 个')
    if updated:
        print('  变更的文件：' + '、'.join(
            n for n in sorted(files) if old.get(n, {}).get('sha256') != files[n]['sha256']))
    return 0


def do_check():
    if not MANIFEST.exists():
        print('专家包内没有 MANIFEST.json——副本无从校验。跑 `run.py export` 生成。')
        return 1
    old = load_manifest()
    cur = {p.name: digest(p) for p in sources()}
    add = sorted(set(cur) - set(old))
    gone = sorted(set(old) - set(cur))
    diff = sorted(n for n in set(cur) & set(old) if cur[n] != old[n]['sha256'])
    if not (add or gone or diff):
        print(f'专家包脚本与 tools 同源（{len(cur)} 个，哈希一致）')
        return 0
    for n in add:
        print(f'  + tools 有、专家包没有：{n}')
    for n in gone:
        print(f'  - 专家包有、tools 没有：{n}')
    for n in diff:
        print(f'  ! 内容已变：{n}')
    print('副本已漂移。跑 `python3 tools/export_expert.py` 或 `run.py export` 重新同步。')
    return 1


def main():
    ap = argparse.ArgumentParser(description='导出脚本到专家包并写哈希清单')
    ap.add_argument('--check', action='store_true', help='只比对不写盘，不一致 exit 1')
    args = ap.parse_args()
    return do_check() if args.check else do_export()


if __name__ == '__main__':
    sys.exit(main())
