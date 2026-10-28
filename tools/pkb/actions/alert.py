#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""alert —— 把「要人知道的事」写成一张页面，而不是留在会滚走的终端里。

为什么要有（2026-10-28）：此前体检只在输出里说「采集根本没跑」，而体检是流水，
跑完那一屏就没了；没有告警渠道，等于要求人每天主动来看。三个自动化互不通信，
其中一个挂了另一个照跑——**不知道自己读到的是旧数据的报告，比没有报告更危险**，
因为它看起来是新的。

只做两件事：跑一遍检查、把非绿的东西按「要处置／要知道」两档写进 `告警.md`。
不判断该不该修（那是台账与人的事），不发通知（本机没有可靠通道，写页面最实在）。

**分类与渲染是纯函数，`check` 直接复用**（2026-10-28 晚）
--------------------------------------------------------
起先 `check` 和 `alert` 各跑一遍注册表：同一次体检把十项检查跑两遍，慢一倍，
而且两次之间文件可能已变，跑出来的两个结论会互相打架。现在 `classify`／
`collect`／`render` 都只吃 `Result`，谁跑的结果都能喂进来——`check` 用自己的，
`alert` 自己跑。**判据只有一份，跑几次都同一个答案。**
"""
import argparse
import datetime

from pkb.checks import REGISTRY
from pkb.core import ALERT, Verdict, read, write
from pkb.core.stamp import unchanged

HEAD = """# 告警

> 本页由 `python3 tools/run.py alert` 或 `run.py check`（全量）覆盖式重写，
> **不要手改**——手改的内容下次就被冲掉。
> 生成时间：{ts}
>
> 分两档：**要处置**＝检查判失败或没有结论；**要知道**＝通过但不该当没看见
> （如「采集跑了但 0 新增」「库有未提交改动」）。

"""


def _run_all():
    """跑一遍注册表，返回 [(名字, Result|None, 异常文本)]。"""
    out = []
    for spec in REGISTRY:
        args = ['--all'] if spec.needs_all else []
        try:
            out.append((spec.name, spec.module.run(args), ''))
        except Exception as e:                      # 检查自身炸了也是告警，不能静默
            out.append((spec.name, None, f'{type(e).__name__}: {e}'))
    return out


def classify(name, res, err=''):
    """→ (档, 一句话)。档为 None 表示这条不用写进告警页。"""
    if res is None:
        return 'hard', f'`{name}` 检查自身异常：{err}'
    if res.verdict in (Verdict.FAIL, Verdict.BAD_INPUT):
        return 'hard', f'`{name}`：{res.summary}'
    soft = ('⚠️' in res.summary or '根本没跑' in res.summary
            or '0 新增' in res.summary or '未回流' in res.summary and '未回流 0' not in res.summary)
    return ('soft', f'`{name}`：{res.summary}') if soft else (None, '')


def collect(results):
    """[(名字, Result|None, 异常)] → (要处置[], 要知道[])。"""
    hard, soft = [], []
    for name, res, err in results:
        kind, msg = classify(name, res, err)
        if kind == 'hard':
            hard.append(msg)
        elif kind == 'soft':
            soft.append(msg)
    return hard, soft


def render(hard, soft, ts):
    """两档清单 → 告警页全文。"""
    body = [HEAD.format(ts=ts), '## 一、要处置\n']
    body += [f'- {m}' for m in hard] or ['- （无）']
    body += ['', '## 二、要知道\n']
    body += [f'- {m}' for m in soft] or ['- （无）']
    body += ['', '## 三、怎么看\n',
             '- 「要处置」逐条进任务台账（`wiki/总览/任务台账.md`），标机器可修的跑 `run.py fix`；',
             '- 「要知道」里最常见的是采集 `0 新增`：那通常是当天真没有政策，'
             '但如果连续两天，先看采集日志有没有那一行（0 也写 0）。']
    return '\n'.join(body) + '\n'


def save(hard, soft):
    """写盘，返回是否成功。写不进去不能连带把体检判失败——告警页是产物，不是判据。

    **除时间戳外没变就不写**（2026-10-29）：本页每次 `check` 都会被重写，而模板第一行
    就带生成时间，于是每跑一次体检就产一次「只有时间变了」的 diff——`check_vcs` 的
    「未提交」再也清不掉，真变化被埋在噪音里。与 `归档/index.md` 同一处理，
    判定共用 `core/stamp.py`。
    """
    body = render(hard, soft, datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
    if unchanged(read(ALERT, ''), body, '生成时间：'):
        return 'same'
    try:
        ALERT.parent.mkdir(parents=True, exist_ok=True)
        write(ALERT, body)
        return 'written'
    except OSError:
        return 'fail'


def run(argv=None):
    ap = argparse.ArgumentParser(prog='alert', description='生成告警页（覆盖写 wiki/总览/告警.md）')
    ap.add_argument('--check', action='store_true', help='只打印，不写盘')
    args = ap.parse_args(list(argv or []))

    hard, soft = collect(_run_all())

    print('\n' + '=' * 62)
    print(f'告警：要处置 {len(hard)} 条 · 要知道 {len(soft)} 条')
    print('=' * 62)
    for m in hard:
        print('  ✗ ' + m)
    for m in soft:
        print('  · ' + m)
    if args.check:
        print('\n  （--check：未写盘）')
        return 0
    res = save(hard, soft)
    if res == 'same':
        print('\n  内容未变，未写盘（时间戳只随内容更新）')
    elif res == 'written':
        print(f'\n  已写入 {ALERT.relative_to(ALERT.parents[2])}')
    else:
        print('\n  ⚠ 告警页写不进去（目录或权限问题），上面的清单是本次结论')
    return 0
