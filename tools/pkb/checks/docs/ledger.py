#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**入口与台账的统一性**：库内不直调脚本、台账结构与生命周期。

这一组守的都是「同一事实只有一个出口」：命令只有 `run.py` 一个入口、
现状数字只有 `plan`／`check` 一个出口。副本一旦出现，漏改不会报错。
（动作表那一项 2026-10-28 已取消——三份表都删了，规则只写「跑 `run.py list`」，
不留副本就不必核副本是否一致。）
台账另有一件事没人管：**四态之间没有自动过渡**。写完 🟡 就再也不动、
✅ 堆在未闭环项里不分新旧，读者只能自己猜哪条还在办——2026-10-26 清理时
12 条 ✅ 与 4 天没动的 🟡 同时存在，就是没人执行过「该退就退」。
"""
import datetime
import re

from pkb.core import (AGENTS, INDEX, README, EXPERT_MD, STATUS, OVERVIEW_DIR,
                      LEDGER, CHECK_REPORT, read, parse_date)
from pkb.domain import ARCHIVE_DAYS, STALE_DAYS, VERIFY_DAYS, OBSERVE
from pkb.domain.ledger import (LEDGER_TYPES, LEDGER_OWNERS, LEDGER_SOLUTIONS,
                               LEDGER_COLS, col)   # 不在 __all__，见 domain/__init__ 说明

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


LEDGER_HOMES = {'未闭环项': len(LEDGER_COLS), '关闭记录': 5}


def _task_sections(text):
    """按 `## ` 切节，只留含 `| T-` 行的节：{节名: [行]}。"""
    out, cur = {}, ''
    for line in text.split('\n'):
        if line.startswith('## '):
            cur = line[3:].strip()
        elif line.startswith('| T-'):
            out.setdefault(cur, []).append(line)
    return out


def _header(text, key):
    """`key` 那节的表头单元格；读不到返回 None。"""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('## ') and key in line:
            for nxt in lines[i + 1:]:
                if nxt.startswith('## '):
                    return None
                if nxt.lstrip().startswith('|'):
                    return [x.strip() for x in nxt.strip().strip('|').split('|')]
            return None
    return None


def check_ledger_shape():
    """台账结构：T- 行必须住在两节之内、列数与表头一致、未闭环项里编号唯一。

    为什么单列（2026-10-26）：一条记录被粘成两行共用一行的形态（`… | ✅ 已关闭 | … || T-x | …`），
    `plan` 按行首取编号，后半条就**静默消失**——T-20261026-01 因此两天没进过派活清单，
    谁也没发现。同理有一行 ✅ 落在第五节后面，也读不到。判据认列数与节位，不认内容。

    2026-10-28 加一条：**表头必须与 `domain/ledger.LEDGER_COLS` 逐字一致**。
    理由是列序被三个模块按下标读——表头加了列而代码没跟上，读出来的就是相邻列，
    「不报错、只是读错」。让表头本身成为契约，改列就必须改代码。
    """
    text = read(LEDGER, '')
    if not text:
        warn('台账', '读不到任务台账，本项无法校验')
        return
    secs = _task_sections(text)
    bad = False
    head = _header(text, '未闭环项')
    if head and tuple(head) != LEDGER_COLS:
        bad = True
        err('台账', f'「未闭环项」表头是 {"｜".join(head)}，应为 {"｜".join(LEDGER_COLS)}'
                    f'——列序是三个模块的下标契约，改表头必须同时改 domain/ledger.LEDGER_COLS')
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
        if len(c) < len(LEDGER_COLS) or '✅' in c[col('状态')]:
            continue
        hits = pat.findall(c[col('问题')])
        if hits:
            bad.append((c[0], hits))
    for tid, hits in bad:
        err('台账', f'{tid} 的问题列写了现状读数 {"/".join(hits)}——'
                    f'删掉，改成「以 `run.py plan` 为准」（数字只留一个出口）')
    if not bad:
        ok('台账问题列无现状读数（数字统一出口：run.py plan／check）')


def ledger_rows(text):
    """未闭环项里的 T- 行：[(全文行号, 九列)]。

    只认「未闭环项」这一节——落在别节的是结构问题，由 `check_ledger_shape` 报，
    这里不重复判（同一件事两处判，改口径就要改两处）。
    """
    out, cur = [], ''
    for i, line in enumerate(text.split('\n')):
        if line.startswith('## '):
            cur = line
        elif line.startswith('| T-') and '未闭环项' in cur:
            out.append((i, [x.strip() for x in line.strip().strip('|').split('|')]))
    return out


def age_of(cell, today):
    """「最近更新」→ 距今天数；解析不了返回 None（不猜）。"""
    d = parse_date(cell)
    return (today - d).days if d else None


def triage(text, today=None):
    """把未闭环项分四堆：{archive, stale, overdue, observe} → [(行号, 九列, 为什么)]。

    动作（`run.py ledger`）与检查（每期体检）共用这一份判定：
    判定与执行各写一份，迟早一个判 3 天、一个判 5 天。
    """
    today = today or datetime.date.today()
    out = {'archive': [], 'stale': [], 'overdue': [], 'observe': []}
    for i, c in ledger_rows(text):
        if len(c) < len(LEDGER_COLS):
            continue
        age, st = age_of(c[col('最近更新')], today), c[col('状态')]
        if '✅' in st and age is not None and age >= ARCHIVE_DAYS:
            out['archive'].append((i, c, f'关闭已 {age} 天'))
        elif '🟡' in st and age is not None and age > STALE_DAYS:
            out['stale'].append((i, c, f'{age} 天无动作'))
        elif '⏳' in st and age is not None and age > VERIFY_DAYS:
            out['overdue'].append((i, c, f'待验 {age} 天没结论'))
        m = OBSERVE.search(c[col('关闭依据与下一步')])
        if m:
            ym = f'{m.group(1)}-{m.group(2)}'
            if ym <= today.strftime('%Y-%m'):
                out['observe'].append((i, c, f'观察窗口 {ym} 已到，该核了'))
    return out


def check_ledger_values():
    """「类型」「负责环节」「解法」三列只能取约定值（2026-10-26 增，10-28 加解法）。

    为什么单列：取值表写在 AGENTS 与台账第一节，但以前一个字都没校验过。写错的代价
    不是报错，是**静默不被读**——`plan` 只抽「负责环节＝采集」，写成「采集入库」这一行
    就永远轮不到派活；类型写成「结构问题」，「内容类缺档」与「结构错」在体检里混成一类。
    与 T-20261026-01 那条「后半条静默消失」同形：账还在，只是没人再看它。

    只判这三列，不判状态：状态是四态＋若干收尾写法（`✅ 已闭环`／`🚫 已放弃`／`⛔ 搁置`），
    措辞还在演进，硬判会把正确写法判错（判据宁窄不错认）。
    关闭记录（五列）没有这三列，不查。
    """
    text = read(LEDGER, '')
    if not text:
        warn('台账', '读不到任务台账，本项无法校验')
        return
    bad = 0
    checks = ((col('类型'), LEDGER_TYPES, '类型'),
              (col('负责环节'), LEDGER_OWNERS, '负责环节'),
              (col('解法'), LEDGER_SOLUTIONS, '解法'))
    for i, c in ledger_rows(text):
        if len(c) < len(LEDGER_COLS):
            continue                      # 列数不对由 check_ledger_shape 报，这里不重复判
        for idx, allowed, label in checks:
            if c[idx] in allowed:
                continue
            bad += 1
            err('台账', f'{c[0]} 第 {i + 1} 行{label}「{c[idx]}」不在取值表内'
                        f'（{"／".join(allowed)}）——取值写错不会报错，只会让这一行不再被读')
    if not bad:
        ok(f'台账取值合规（{len(LEDGER_TYPES)} 类类型、{len(LEDGER_OWNERS)} 个负责环节、'
           f'{len(LEDGER_SOLUTIONS)} 种解法）')


def _queue():
    """任务台账「存量补采队列」：{页: {'claim': date|None, 'status': str}}。

    不复用 `actions/plan.py` 的同名解析：checks 不许 import actions（分层单向），
    两处读的是同一张表，但一处为「派活」、一处为「核对做没做」，取舍不同。
    """
    out, inq = {}, False
    for line in read(LEDGER, '').split('\n'):
        if line.startswith('## '):
            inq = '存量补采队列' in line
        elif inq and line.startswith('|') and not line.startswith('|---'):
            c = [x.strip() for x in line.strip().strip('|').split('|')]
            if len(c) >= 6 and '页' not in c[0]:
                out[c[0]] = {'claim': parse_date(c[4]), 'status': c[5]}
    return out


def _latest_check_section():
    """体检报告最新一节：(日期, 正文)。

    只认带日期的 `### YYYY-MM-DD` 标题——`### 下一轮（2026-10-26 22:00）应核对的事项`
    这类占位标题不是一次真实体检，不能被当成「最新一节」。
    """
    text = read(CHECK_REPORT, '')
    if not text:
        return None
    heads = [(m.start(), parse_date(m.group(1)))
             for m in re.finditer(r'^### (\d{4}-\d{2}-\d{2})', text, re.M)]
    if not heads:
        return None
    start, day = heads[0]
    end = heads[1][0] if len(heads) > 1 else len(text)
    return day, text[start:end]


def _released(body, pages):
    """「释放」二字之后紧跟的页名：只认宾语，不认整节出现过。

    为什么这么窄：10-24 那节既有「**本期释放**：存量补采「国防军事」页」，又有
    「三页首次纳入规则：国防军事／区域经济／科技创新，本期释放最旧的国防军事页」。
    按整节匹配，三页全会被算成已释放，于是「区域经济」被判「说了没记」——假警。
    取 `释放` 之后 80 字、到第一个句号或换行为止，页名出现在这里才算释放的对象。
    """
    out = []
    for m in re.finditer('释放', body):
        tail = re.split(r'[。\n]', body[m.end():m.end() + 80])[0]
        out += [p for p in pages if p in tail]
    return sorted(set(out))


def check_release_logged():
    """每期体检必须交代「释放了哪页哪批」，且台账要记领取（2026-10-26 增）。

    为什么单列：体检报告开头自己写着「每节末尾要写『本次释放的页／批次』」，提示词第五节
    也要求「必须写明，或写明本期不释放，不许留空」——但从 10-24 起到现在，这个要求
    **没有任何判据**：2026-10-24 那节就真的没写（释放记录只落在 [[运行状态]]），
    而页面上的那句要求读起来仍然像真的。

    判三件事：
      ① 最新一节有没有出现「释放」二字（含「本期不释放」）；
      ② 说了释放，点名的页是否真在存量队列里；
      ③ 点名的页，台账「最近领取」是否不早于该节日期——写了没记，下一期会重复释放。
    """
    seq = _latest_check_section()
    if not seq:
        warn('体检报告', '读不到带日期的检查记录，本项无法校验')
        return
    day, body = seq
    if '释放' not in body:
        err('体检报告', f'最新一节（{day}）没有交代「本期释放了哪页哪批」或「本期不释放」——'
                       f'这是领取闸门的唯一留痕，缺了下一期只能靠猜')
        return
    pages = _queue()
    named = _released(body, pages)
    if '不释放' in body or '无页可释放' in body:
        pend = [p for p, v in pages.items() if not v['claim'] and '✅' not in v['status']]
        if pend:
            warn('体检报告', f'写「本期不释放」，但队列里还有未领页（{"、".join(pend)}）——'
                            f'核对闸门，别让页卡在队列里')
        else:
            ok(f'体检释放留痕：{day} 本期不释放（队列无未领页）')
        return
    if not named:
        warn('体检报告', '写了「释放」，但没点名队列里的任何一页——'
                        '照抄队列里的页名，否则无法核对是否真释放')
        return
    bad = False
    for p in named:
        claim = pages[p]['claim']
        if not claim or claim < day:
            bad = True
            err('体检报告', f'本节写明释放「{p}」，台账「最近领取」是 '
                            f'{claim or "空"}——说了没记，下一期会重复释放同一页')
    if not bad:
        ok(f'体检释放留痕：{day} 释放 {"、".join(named)}，台账领取日已对齐')


def check_ledger_hygiene():
    """台账生命周期：四态之间没人推的那一步，交给人看。

    一律 **warn 不 err**：整理是卫生，不是正确性。把「台账有点乱」判成 exit 1，
    整篇文档校验就长期红着，红久了没人看（与 `check_views` 同一分工）。
    但也不能只靠人记——`run.py ledger` 是执行端，本项只负责让它在体检摘要里露面。
    """
    text = read(LEDGER, '')
    if not text:
        return
    t = triage(text)
    tips = {'archive': '归档：`run.py ledger --apply` 搬进第六节',
            'stale': '退回 🆕：三天没动等于没记',
            'overdue': '待验过期：要么给结论，要么说清为什么验不了',
            'observe': '观察窗口已到：核完回写本行'}
    n = 0
    for key, msg in tips.items():
        for _i, c, why in t[key]:
            warn('台账', f'{c[0]} {why}——{msg}')
            n += 1
    if not n:
        ok('台账生命周期：无到期未归档、无停滞、无待验过期')
