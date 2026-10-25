#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：check —— 全量自检。

三件事，顺序不能换：
1. 先刷快照（dry-run 比对）：结构检查读的是 index 的统计，快照旧了会报假警；
2. 按注册表逐项跑检查，取各自的一句话结论；
3. 聚合退出码：任一项 FAIL 即 1；参数没人认领即 2（并明说结论不含该范围）。

输出详略只有这一层决定（摘要 / 14 行 / 全量），checks 自己不打印。
"""
import re

from pkb.core import TOOLS, Result, Verdict
from pkb.checks import REGISTRY

from ._proc import PY, sh

SUMMARY_MARK = '▸摘要:'          # 与 core.report 同一契约，这里只用于回显明细尾部


def head(title):
    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)


def route_args(spec, rest):
    """把命令行参数交给这一项认得的部分，认不得的不传。"""
    out, i = [], 0
    while i < len(rest):
        a = rest[i]
        if a.startswith('--'):
            flag = a.split('=')[0]
            if flag in spec.flags:
                out.append(a)
                if '=' not in a and i + 1 < len(rest) and not rest[i + 1].startswith('--'):
                    out.append(rest[i + 1])
                    i += 1
        elif re.match(r'\d{4}-W\d{2}$', a):           # 裸周号 → 转成 --week
            if '--week' in spec.flags:
                out += ['--week', a]
        i += 1
    return out


def detail_lines(result):
    """明细行 + 摘要行（摘要放末尾，与迁移前子进程 stdout 的形状一致）。"""
    body = list(result.lines) + [f'{SUMMARY_MARK} {result.summary}']
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return body


def run(rest=None):
    rest = list(rest or [])
    only, full = None, False
    if '--only' in rest:
        i = rest.index('--only')
        only = rest[i + 1] if i + 1 < len(rest) else ''
        del rest[i:i + 2]
    if '--full' in rest:
        full = True
        rest.remove('--full')

    head('全量自检' if not only else f'自检（只跑匹配 {only} 的脚本）')

    specs = list(REGISTRY)
    if only is not None:
        specs = [s for s in specs if only.lower() in s.name.lower()]
        if not specs:
            print(f'没有检查项名匹配「{only}」。可用：'
                  + '、'.join(s.name.replace('check_', '').replace('.py', '') for s in REGISTRY))
            return 2
        full = True                       # 单跑一项时，默认看全量输出

    # [0] 快照比对：必须在结构检查之前
    snap = TOOLS / 'refresh_snapshot.py'
    if snap.exists() and only is None:
        code, out = sh([PY, str(snap), '--dry-run'], cwd=str(TOOLS))
        n = re.findall(r'(\d+)\s*处(?:更新|差异)', out)
        cnt = int(n[-1]) if n else 0
        print(f'[0] refresh_snapshot --dry-run        退出码 {code}'
              + (f'（{cnt} 处待更新，需跑 fix）' if cnt else '（已是最新）'))

    bad, missed = [], set()
    routed = set()
    for i, spec in enumerate(specs, 1):
        extra = route_args(spec, rest)
        for x in extra:
            if x.startswith('--'):
                routed.add(x.split('=')[0])
        if '--week' in extra:
            routed.add('周号')
        # 需要 --all 才能给结论的项：显式传了参数就以调用方意图为准，不再补 --all
        argv = extra if (extra and '--all' not in extra) else (['--all'] if spec.needs_all else []) + extra

        try:
            result = spec.module.run(argv)
        except Exception as e:                    # 一项崩了不许拖垮其余五项
            result = Result(Verdict.FAIL, f'检查自身异常：{e}', [f'✗ 检查自身异常：{e}'])
        if not isinstance(result, Result):
            result = Result(Verdict.FAIL, '检查未返回 Result（契约违规）',
                            [f'✗ {spec.name} 未返回 Result'])

        print(f'[{i}] {spec.name:<28} 退出码 {result.code}   {result.summary}')
        if result.code != 0:
            bad.append(spec.name)
        if result.code != 0 or full:
            body = detail_lines(result)
            if body:
                show = body if full else body[:14]
                print('\n'.join('      ' + l for l in show))

    # 参数拼错/不被任何脚本认领时必须出声：静默丢弃会让人以为窗口核过了
    for a in rest:
        flag = a.split('=')[0]
        if flag.startswith('--') and flag not in routed:
            missed.add(flag)
        elif re.match(r'\d{4}-W\d{2}$', a) and '周号' not in routed:
            missed.add(a)
    if missed:
        print(f'\n⚠ 参数没有任何检查项认领：{"、".join(sorted(missed))}')
        print('   可用：--since YYYY-MM-DD（信号窗口）／--week YYYY-Www 或裸周号（周观点）')
        print('   本次运行的结论**不含**你要的那个窗口——别拿 exit 0 当它已通过。')

    head('自检结论')
    if bad:
        print(f'❌ {len(bad)} 个检查未通过：{", ".join(bad)}')
        print('   处置：先跑 `python3 tools/run.py fix` 自动修复；')
        print('   修完仍非 0 的，用 `run.py check --only <名字>` 看完整明细——')
        print('   那通常是脚本修不了的判断类问题。')
        return 1
    if missed:
        print('检查本身全部通过，但参数没送到（见上面的 ⚠），等于没核你要的范围。')
        return 2
    print('✅ 全部检查通过。')
    return 0
