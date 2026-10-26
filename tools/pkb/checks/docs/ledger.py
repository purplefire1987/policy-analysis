#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**入口与台账的统一性**：动作表三处一致、库内不直调脚本、台账不写读数。

这一组守的都是「同一事实只有一个出口」：
动作清单只有 `run.py` 一份实现、命令只有 `run.py` 一个入口、
现状数字只有 `plan`／`check` 一个出口。三份副本一旦出现，漏改不会报错。
"""
import re

from pkb.core import AGENTS, INDEX, README, EXPERT_MD, STATUS, OVERVIEW_DIR, LEDGER, TOOLS, read

from ._state import err, warn, ok

EXPERT = EXPERT_MD


def check_no_direct_calls():
    """库内文档不得直调 tools 下的脚本（2026-10-25 新增）。

    只认「调用」形态：`python3 …/xxx.py`，或 `tools/xxx.py` 后面紧跟参数。
    只写脚本名、或括注「（`tools/xxx.py`）」这类指路叙述不算——
    体检报告的历史记录、AGENTS 里「实现见某脚本」的括注都不会被误判。历史是史实，不该被改写。

    为什么单列一项：三页台账是**每个自动化开工都会读**的文件。它们写着直调脚本，
    等于规则副本绕过了入口——2026-10-25 实测仍有 8 处（任务台账 2、采集日志 3、
    体检报告 1、政策速览 1、运行状态 1），而这一路没有任何校验能发现。
    """
    SCRIPT = r'(?:check_|plan_backlog|refresh_snapshot|clean_sources|status_report|week_sources)[\w]*\.py'
    # 模块化之后多出两种直调形态：`python3 -m pkb.checks.weeks`、`python3 …/pkb/checks/weeks.py`。
    # 表达力强了，但「绕过 run.py 就没有统一摘要与退出码聚合」这一点没变，两种都要认。
    PKGPY = r'\S*pkb/[\w/]*\.py'
    MODULE = r'pkb(?:\.[\w]+)*'
    CALL = re.compile(r'python3\s+(?:-m\s+' + MODULE + r'|\S*' + SCRIPT + r'|' + PKGPY + r')'
                      + r'|(?:' + SCRIPT + r'|' + PKGPY + r')\s+(?:--|-\w|\{|\d|\*)')
    paths = [AGENTS, INDEX, README, EXPERT, STATUS,
             OVERVIEW_DIR / '采集日志.md', OVERVIEW_DIR / '任务台账.md',
             OVERVIEW_DIR / '体检报告.md', OVERVIEW_DIR / '政策速览.md']
    hit = False
    for p in paths:
        text = read(p, '')
        for i, line in enumerate(text.split('\n'), 1):
            if CALL.search(line):
                hit = True
                err(p.name, f'第 {i} 行直调脚本，应改为 `run.py <动作>`：{line.strip()[:70]}')
    if not hit:
        ok('库内文档 0 处直调脚本（统一走 run.py）')


def check_actions():
    """入口动作表三处必须一致：`run.py` 的 ACTIONS ／ AGENTS 第十节 ／ 专家定义二点五。

    为什么单列：同一张表写在三个文件里＝三份副本，加一个动作要改三处，漏改不会报错，
    只会让读者按旧表去调一个不存在的动作（或不知道新动作存在）。2026-10-25 加 `week`
    就是手工改三处——这条检查把它变成机器活。
    判据以 `run.py` 为准：它是实现，文档是它的说明书。
    """
    src = read(TOOLS / 'run.py', '')
    m = re.search(r'^ACTIONS\s*=\s*\{(.*?)^\}', src, re.S | re.M)
    if not m:
        err('动作表', 'run.py 里找不到 ACTIONS 定义，本项无法校验')
        return
    impl = set(re.findall(r"'(\w+)':\s*\(", m.group(1)))

    segs = {
        'AGENTS': read(AGENTS, '').split('### 统一入口', 1)[-1].split('### 硬门槛', 1)[0],
        '专家定义': read(EXPERT, '').split('、统一入口', 1)[-1].split('**不要手写统计数字', 1)[0],
    }
    bad = False
    for name, seg in segs.items():
        documented = set(re.findall(r'^\|\s*`(\w+)', seg, re.M))
        if not documented:
            warn(name, '未找到入口动作表（如已改版，请同步更新本检查）')
            continue
        for a in sorted(impl - documented):
            bad = True
            err(name, f'入口有动作 `{a}`，本文件未列出')
        for a in sorted(documented - impl):
            bad = True
            err(name, f'列出了动作 `{a}`，但 run.py 里没有——按它调用会报未知动作')
    if not bad:
        ok(f'入口动作表三处一致（{len(impl)} 个：{"、".join(sorted(impl))}）')


LEDGER_HOMES = {'未闭环项': 8, '关闭记录': 5}


def _task_sections(text):
    """按 `## ` 切节，只留含 `| T-` 行的节：{节名: [行]}。"""
    out, cur = {}, ''
    for line in text.split('\n'):
        if line.startswith('## '):
            cur = line[3:].strip()
        elif line.startswith('| T-'):
            out.setdefault(cur, []).append(line)
    return out


def check_ledger_shape():
    """台账结构：T- 行必须住在两节之内、列数与表头一致、未闭环项里编号唯一。

    为什么单列（2026-10-26）：一条记录被粘成两行共用一行的形态（`… | ✅ 已关闭 | … || T-x | …`），
    `plan` 按行首取编号，后半条就**静默消失**——T-20261026-01 因此两天没进过派活清单，
    谁也没发现。同理有一行 ✅ 落在第五节后面，也读不到。判据认列数与节位，不认内容。
    """
    text = read(LEDGER, '')
    if not text:
        warn('台账', '读不到任务台账，本项无法校验')
        return
    secs = _task_sections(text)
    bad = False
    for name, rows in secs.items():
        home = next((k for k in LEDGER_HOMES if k in name), None)
        if not home:
            bad = True
            err('台账', f'{len(rows)} 行落在「{name}」——T- 行只能住「未闭环项」与「关闭记录」，'
                        f'放错节等于漏登记（plan 与体检都读不到）')
            continue
        for line in rows:
            c = [x.strip() for x in line.strip().strip('|').split('|')]
            if len(c) != LEDGER_HOMES[home]:
                bad = True
                err('台账', f'{c[0]} 有 {len(c)} 列，「{home}」应为 {LEDGER_HOMES[home]} 列——'
                            f'多半是两条粘成一行，后半条会被静默丢掉')
    live = [re.match(r'\| (T-\S+)', x).group(1)
            for k, rows in secs.items() if '未闭环项' in k for x in rows]
    for i in sorted({x for x in live if live.count(x) > 1}):
        bad = True
        err('台账', f'{i} 在未闭环项出现 {live.count(i)} 次——编号唯一，不复用不重排')
    if not bad:
        ok(f'台账结构自洽（{len(live)} 条在「未闭环项」内，列数对齐、编号唯一）')


def check_ledger_numbers():
    """任务台账的「问题」列不得写**现状读数**——现状数字只有一个出口：`run.py plan`／`run.py check`。

    为什么单列：2026-10-25 发现同一份 `plan` 自己打自己——第 1 段照抄台账写「国防军事 78 天（最近
    08-07，5 条）」，第 3 段按实时数据写「72 天（最近 08-14，6 条）」，只因台账那句话是 10-24 的快照。
    采集看到两处矛盾只能自己猜信谁。规则改成「台账定性、脚本定量」：
    · 未关闭行（🆕/🟡/⏳/🚧）的问题列出现裸读数 → 硬错误，改成「以 run.py plan 为准」；
    · 已关闭行（✅）不查——那是历史记录，写死当时的数字是它的职责；
    · 备注列不查——带日期的读数带有时间戳，天然限定为「当时」，不会冒充现状。
    """
    text = read(LEDGER, '')
    if not text:
        warn('台账', '读不到任务台账，本项无法校验')
        return
    pat = re.compile(r'(?<![~\d])\d+\s*(?:天|个|条|篇|张|处)|[\d.]+\s*%|(?<![~\d])\d+/\d+')
    bad = []
    for line in text.splitlines():
        if not line.startswith('| T-'):
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) < 8 or '✅' in c[5]:
            continue
        hits = pat.findall(c[2])
        if hits:
            bad.append((c[0], hits))
    for tid, hits in bad:
        err('台账', f'{tid} 的问题列写了现状读数 {"/".join(hits)}——'
                    f'删掉，改成「以 `run.py plan` 为准」（数字只留一个出口）')
    if not bad:
        ok('台账问题列无现状读数（数字统一出口：run.py plan／check）')
