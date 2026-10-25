#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档一致性校验：核对 AGENTS / README / 专家定义 是否还与系统实际相符，并检查 log.md 卫生。

为什么需要它：
    规则只写一处（AGENTS.md），但执行副本散在库外——README、专家包定义、三个自动化
    提示词。库内脚本查不到它们，改一处漏一处也不会报错。历史上因此出过：专家定义
    七节名称写错、README 写了已废弃的目录路径、体检提示词漏跑新脚本。
    本检查把「会撒谎的文档」当成待检对象，每 2 天体检时跑一次。

判据来源（单一）：
    AGENTS.md 是唯一规则来源。其余文档与它不一致，一律报错——不反过来改 AGENTS。
    脚本数量、模板数量这类「易变且无校验价值」的数字，三处都不许写死。

不提供自动修复：「以哪份为准」是人的判断（改 AGENTS 还是改 README，后果不同）。
"""

import argparse
import ast
import json
import re

from pkb.core import (VAULT, CARD_DIR, CHAIN_DIR, TEMPLATE_DIR, INDEX, AGENTS, README, LOG,
                 STATUS, LEDGER, EXPERT_MD, WEEK_TEMPLATE, OVERVIEW_DIR, TOOLS, EXPERT_DIR,
                 read, digest, py_files, Reporter, Result, Verdict)
from pkb import domain as _domain
from pkb.domain import BLACK, DOC_MUST_MENTION  # 黑名单唯一定义处：pkb/domain/blacklist.py
EXPERT = EXPERT_MD
TEMPLATE = WEEK_TEMPLATE

DELETED_PAGES = ['政策跟踪运营方案', '政策链总览', '主题词表']
LOG_TYPES = {'决策', '采集', '体检', '观点', '事故'}
LOG_MAX_LINES = 80
LOG_MAX_BYTES = 200 * 1024

_rep = Reporter()
errors, warns, oks = _rep.errors, _rep.warns, _rep.oks


def ok(msg):
    _rep.ok(msg)


def err(item, msg):
    _rep.err(item, msg)


def warn(item, msg):
    _rep.warn(item, msg)


def interval_days(text):
    """提取文档声明的体检节拍。

    跳过假设性语句——专家定义里有「如体检从每 2 天挪到每 3 天」这类操作示例，
    那是可能发生的变更，不是当前节拍，直接取数会误判成自相矛盾。
    """
    days = set()
    for line in text.split('\n'):
        if any(k in line for k in ('挪到', '改为', '例如', '假如', '如体检', '若')):
            continue
        days.update(int(x) for x in re.findall(r'每\s*(\d+)\s*天', line))
    return days


def check_interval(docs):
    base = interval_days(docs['AGENTS'])
    if len(base) > 1:
        err('AGENTS', f'文件内部节拍互相矛盾：{sorted(base)} 天')
        return
    if not base:
        warn('AGENTS', '未找到「每 N 天」表述，无法校验节拍')
        return
    n = base.pop()
    bad = []
    for name in ('README', '专家定义', '运行状态', '专家包README'):
        t = docs.get(name, '')
        if not t:
            warn(name, '文件不存在，跳过节拍比对')
            continue
        d = interval_days(t)
        if not d:
            warn(name, f'未写体检节拍，无法比对（AGENTS 为每 {n} 天）')
        elif d != {n}:
            bad.append((name, sorted(d)))
    if bad:
        for name, d in bad:
            err(name, f'体检节拍写 {d} 天，AGENTS 是 {n} 天')
    else:
        ok(f'节拍一致：每 {n} 天（AGENTS／两份 README／专家定义／运行状态）')


def check_seven_sections(docs):
    tpl = read(TEMPLATE, '')
    heads = re.findall(r'^##\s+(.+)$', tpl, re.M)
    if len(heads) != 7:
        err('周观点模板', f'节数 {len(heads)}，应为 7')
        return
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        missing = [h.strip() for h in heads if h.strip() not in t]
        if missing:
            err(name, f'周观点七节名称与模板不一致，缺：{"、".join(missing)}')
    if not any(e[0] in ('AGENTS', '专家定义') for e in errors):
        ok('周观点七节名称：AGENTS／专家定义 与模板一致')


ANALYSIS_TEMPLATE = TEMPLATE_DIR / '政策分析报告模板.md'


def check_analysis_sections(docs):
    """分析报告八节名称：AGENTS 与专家定义须与模板逐字一致。

    与周观点七节同一动机：2026-10-25 模板从七节改为八节后，
    专家定义仍写旧七节，属典型副本漂移。此处把分析报告模板也纳入逐字比对。
    """
    if not ANALYSIS_TEMPLATE.exists():
        warn('分析报告模板', '文件不存在，跳过八节比对')
        return
    tpl = read(ANALYSIS_TEMPLATE, '')
    heads = [h.strip() for h in re.findall(r'^##\s+(.+)$', tpl, re.M)
             if h.strip() != '相关页面']
    if len(heads) != 8:
        err('分析报告模板', f'节数 {len(heads)}，应为 8（不含「相关页面」）')
        return
    before = len(errors)
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        missing = [h for h in heads if h not in t]
        if missing:
            err(name, f'分析报告八节名称与模板不一致，缺：{"、".join(missing)}')
    if len(errors) == before:
        ok('分析报告八节名称：AGENTS／专家定义 与模板一致')


def check_blacklist(docs):
    need = list(DOC_MUST_MENTION)
    for name in ('AGENTS', '专家定义'):
        t = docs.get(name, '')
        if not t:
            continue
        miss = [w for w in need if w not in t]
        if miss:
            err(name, f'黑名单缺「{"、".join(miss)}」——读这份文件的 agent 会去采它')
    if not any('黑名单' in e[1] for e in errors):
        ok(f'黑名单：AGENTS／专家定义 均含{"、".join(need)}')


def check_deleted_refs(docs):
    pat_link = re.compile(r'\[\[(' + '|'.join(DELETED_PAGES) + r')')
    pat_path = re.compile(r'wiki/总览/(' + '|'.join(DELETED_PAGES) + r')\.md')
    hit = False
    for name, t in docs.items():
        if not t:
            continue
        for m in pat_link.finditer(t):
            err(name, f'仍以 wikilink 引用已删除页面 [[{m.group(1)}]]')
            hit = True
        for m in pat_path.finditer(t):
            err(name, f'仍引用已删除文件 wiki/总览/{m.group(1)}.md')
            hit = True
    if not hit:
        ok('已删页面：三处均未再引用（仅在说明中提及名称，不算引用）')


def check_structure_numbers(docs):
    n_cards = len(list(CARD_DIR.glob('*.md')))
    n_chains = len(list(CHAIN_DIR.glob('*.md')))
    t = docs.get('AGENTS', '')
    m = re.search(r'(\d+)\s*张产业卡', t)
    if m and int(m.group(1)) != n_cards:
        err('AGENTS', f'「{m.group(1)} 张产业卡」，实际 {n_cards} 张')
    m = re.search(r'(\d+)\s*条索引链', t)
    if m and int(m.group(1)) != n_chains:
        err('AGENTS', f'「{m.group(1)} 条索引链」，实际 {n_chains} 条')
    if not any(e[0] == 'AGENTS' and '张产业卡' in e[1] or '条索引链' in e[1] for e in errors):
        ok(f'结构数字：AGENTS 的 {n_cards} 张卡 / {n_chains} 条链与实际一致')


def check_no_hardcoded_count(docs):
    """「N 个脚本」这类表述在增删脚本后必然过时，必须拦。

    但假设句不算——「增删一个脚本要改三处提示词」说的是「如果」，
    不是「现在有几个」。不排除就会把规则说明本身判成违规，跟节拍那条是同一类误报。
    """
    pat = re.compile(r'([一二三四五六七八九十]|\d+)\s*个\s*脚本')
    ASSUME = ('增删', '新增', '删除', '假如', '如果', '假设', '以后', '将来', '一旦', '例如', '比如')
    hit = False
    for name, t in docs.items():
        if not t:
            continue
        for m in pat.finditer(t):
            line_start = t.rfind('\n', 0, m.start()) + 1
            line_end = t.find('\n', m.end())
            line = t[line_start:line_end if line_end > 0 else len(t)]
            if any(k in line for k in ASSUME):
                continue          # 假设性表述：说的是「如果」，不是「现在有几个」
            err(name, f'写死了脚本数量「{m.group(0)}」——增删脚本后必然过时')
            hit = True
    if not hit:
        ok('脚本数量：三处均未写死（假设句已排除）')


def check_expert_refs(docs):
    t = docs.get('专家定义', '')
    if not t:
        warn('专家定义', '文件不存在，跳过引用检查')
        return
    names = {p.stem for p in VAULT.rglob('*.md') if '.obsidian' not in p.parts}
    bad = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', t):
        target = m.group(1).split('|')[0].split('#')[0].strip()
        if not target or '{' in target or '-X' in target or target.endswith('XXX'):
            continue                      # 模板占位符，不是真链接
        if target not in names:
            bad.append(f'[[{target}]]')
    for m in re.finditer(r'`(wiki/[^`]+\.md)`', t):
        if not (VAULT / m.group(1)).exists():
            bad.append(m.group(1))
    if bad:
        for b in sorted(set(bad)):
            err('专家定义', f'引用的页面/路径不存在：{b}')
    else:
        ok('专家定义：所有页面与路径引用有效')


def check_log():
    if not LOG.exists():
        warn('log', '文件不存在')
        return
    text = read(LOG, '')
    size = LOG.stat().st_size
    if size > LOG_MAX_BYTES:
        warn('log', f'{size / 1024:.0f} KB，超过 {LOG_MAX_BYTES // 1024} KB 上限——应分卷到 log-YYYY-MM.md')

    lines = text.split('\n')
    heads = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith('## ')]
    new_pat = re.compile(r'^(\d{4}-\d{2}-\d{2}) · (' + '|'.join(LOG_TYPES) + r') · (.+)$')

    # 标题重复（按完整标题比，不看日期前缀——同一天可以有多条不同类型的记录）
    seen = {}
    for _, h in heads:
        seen[h] = seen.get(h, 0) + 1
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        warn('log', f'完全重复的标题 {len(dup)} 组：{", ".join(d[:24] for d in dup[:3])}'
                    + ('…' if len(dup) > 3 else ''))

    # 新格式条目
    new_entries = []
    for idx, (line_no, h) in enumerate(heads):
        m = new_pat.match(h)
        if not m:
            continue
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        new_entries.append({'date': m.group(1), 'type': m.group(2),
                            'title': m.group(3), 'lines': end - line_no - 1,
                            'line_no': line_no})

    if not new_entries:
        warn('log', '尚无合规新条目（格式 `## YYYY-MM-DD · 类型 · 一句话`）')
    else:
        dates = [e['date'] for e in new_entries]
        if dates != sorted(dates, reverse=True):
            err('log', f'新格式条目未按日期倒序：{dates}')
        first_old = next((ln for ln, h in heads if not new_pat.match(h)), len(lines))
        late = [e for e in new_entries if e['line_no'] > first_old]
        if late:
            err('log', f'{len(late)} 条新格式条目被追加到历史条目之后，新条目应置顶')
        over = [e for e in new_entries if e['lines'] > LOG_MAX_LINES]
        for e in over:
            err('log', f'{e["date"]} {e["title"][:20]} 占 {e["lines"]} 行，超过 {LOG_MAX_LINES} 行上限——'
                       '报告应写在对应页面，log 只留结论与指针')
        if not over and not late:
            ok(f'log：{len(new_entries)} 条新格式条目，格式/倒序/篇幅均合规')
        bad_type = [e for e in new_entries if e['type'] not in LOG_TYPES]
        if bad_type:
            err('log', f'{len(bad_type)} 条条目类型不在白名单')

    # 历史条目里的大块快照（只提示）
    big = []
    for idx, (ln, h) in enumerate(heads):
        if new_pat.match(h):
            continue
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        if end - ln - 1 > LOG_MAX_LINES:
            big.append((ln, end - ln - 1))
    if big:
        warn('log', f'{len(big)} 条历史条目超过 {LOG_MAX_LINES} 行（最多一条 '
                    f'{max(n for _, n in big)} 行，多为把整份报告贴进日志），'
                    '建议降级为指针，不阻断')


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


def check_expert_scripts():
    """专家包内的脚本副本必须与 `tools/` 同源（按 MANIFEST 的 sha256 逐条比对）。

    为什么单列：专家包要能独立运行就得自带脚本，自带就有了第二份副本。
    副本怕的不是漂移，是**漂移了没人知道**——库内脚本查不到库外那份，
    改了 tools 忘了同步，两边会安静地各说各话（历史 4 次事故全属此类）。
    判据以 `tools/` 为准；不一致不是「报一下」，是 exit 1：要么同步，要么别分发。
    """
    skill = EXPERT_DIR / 'skills' / 'policy-kb-tools'
    man = skill / 'MANIFEST.json'
    if not man.exists():
        err('专家包', 'skills/policy-kb-tools 缺 MANIFEST.json——副本无从校验（跑 `run.py export`）')
        return
    try:
        listed = json.loads(read(man, '{}')).get('files', {})
    except Exception as e:
        err('专家包', f'MANIFEST.json 无法解析：{e}')
        return
    # 键是相对 tools/ 的 posix 路径——pkb/ 是包，不能再按文件名平铺比对
    cur = {p.relative_to(TOOLS).as_posix(): digest(p) for p in py_files(TOOLS)}
    add = sorted(set(cur) - set(listed))
    gone = sorted(set(listed) - set(cur))
    diff = sorted(n for n in set(cur) & set(listed) if cur[n] != listed[n].get('sha256'))
    # 副本里源已不存在的脚本：留着会让 `import lib` 拿到过期实现，同样算漂移
    dest_root = skill / 'scripts'
    stray = []
    if dest_root.exists():
        stray = sorted(p.relative_to(dest_root).as_posix()
                       for p in dest_root.rglob('*.py')
                       if '__pycache__' not in p.parts
                       and p.relative_to(dest_root).as_posix() not in cur)
    if not (add or gone or diff or stray):
        ok(f'专家包脚本与 tools 同源（{len(cur)} 个，哈希一致）')
        return
    for n in add:
        err('专家包', f'tools 有、包内没有：{n}')
    for n in gone:
        err('专家包', f'包内有、tools 已无：{n}')
    for n in diff:
        err('专家包', f'内容已变（改了 tools 未同步）：{n}')
    for n in stray:
        err('专家包', f'包内残留（tools 已无）：{n}')
    err('专家包', '副本已漂移——跑 `run.py fix`（或 `run.py export`）自动同步，不要在专家包内直接改')


def check_sources():
    """来源域名合规：黑名单域名命中即硬错误；统计三类「待核」标记。

    正文/卡片/信号页里的每个 markdown 链接都查一遍。这条检查存在的理由：
    2026-10-24 全库清出 100 条违规链接（今日头条 58 条最多），此前四条规则
    写在三份文件里、一次也没拦住——规则不落到脚本上就等于没有。
    """
    hits, pending = [], 0
    for p in sorted((VAULT / 'wiki').rglob('*.md')):
        if '.obsidian' in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8').split('\n'), 1):
            for u in re.findall(r'\]\((https?://[^)\s]+)', line):
                for k, why in BLACK.items():
                    if k in u:
                        hits.append(f'{p.name}:{i} {why} → {u[:60]}')
                        break
            if any(t in line for t in ('原始出处待核', '原始出处未能核实', '官方链接待补')):
                pending += 1
    if hits:
        for h in hits[:12]:
            err('来源域名', h)
        if len(hits) > 12:
            err('来源域名', f'…另有 {len(hits)-12} 条违规链接')
    else:
        ok('来源域名合规（黑名单 0 命中）')
    if pending:
        warn('来源', f'{pending} 处已标注「原始出处待核／未能核实／官方链接待补」——'
                    '这些来源不可核验，须逐步换回官方链接')


def guarded_literals():
    """口径层的字符串常量 → 归口常量名（`'jiemian.com'` → `BLACK`）。

    判据不另写一份名单——**名单本身就是第二份副本**，正是要防的东西。
    这里反过来做：把 `pkb.domain` 的导出值读出来当扫描词典，
    于是 domain 加一项，扫描自动覆盖那一项，本函数一行都不用改。

    排除 `REQUIRED_FIELDS`：字段名是「读数据的键」（`fm.get('领域')`），
    不是复述口径；把字段名也当地雷，会逼所有检查改写 `fm.get(KEY['领域'])`，
    徒增一层无意义间接。`is_bad` 是函数、`CARD_SIZE_WARN` 是数字，天然不在词典里。
    """
    out = {}
    for name in _domain.__all__:
        if name == 'REQUIRED_FIELDS':
            continue
        val = getattr(_domain, name)
        if isinstance(val, str):
            vals = [val]
        elif isinstance(val, dict):
            vals = list(val)                      # 黑名单是「键即域名」，值只是原因说明
        elif isinstance(val, (set, frozenset, tuple, list)):
            vals = [x for x in val if isinstance(x, str)]
        else:
            continue
        for s in vals:
            if len(s) >= 2:                       # 单字枚举（高/中/低）没有判别力
                out.setdefault(s, name)
    return out


def code_strings(path):
    """文件里**代码用到的**字符串常量：[(行号, 值)]。docstring 与注释不算。

    为什么用 AST 而不逐行找引号：注释和 docstring 里举例子会被正则当成违规，
    等于逼人不敢在注释里说清规则；f-string 里的整句（`f'应为 2026-W42'`）是提示
    文案，也不是复述口径。AST 只认真正作为值参与运算的常量——判断标准与
    「把口径抄进代码」这件事对齐。
    """
    try:
        tree = ast.parse(read(path, ''))
    except SyntaxError as e:
        warn(path.name, f'无法解析，跳过口径扫描：{e}')
        return []
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstring_ids]


def check_domain_literals():
    """口径字面量只能出现在 `pkb/domain/`（设计规则三）。

    判据很窄，只认一件事：**代码里的字符串常量，值与 domain 的某个取值完全相同**。
    自己抄一份黑名单域名、或把领域枚举写成裸字符串，这才是「把口径搬出了 domain」。
    值只是句子的一部分（提示文案、帮助文本里的示例周号）不算——那是措辞不是口径。

    词典从 domain 现读，所以 domain 加一项，扫描自动覆盖那一项，本函数不必改。
    设计文档举的第三个例子「金融强国」属口号类口径，目前库里没有任何 domain
    归属，扫不到；将来若有规则要认口号，先在 domain 声明，这条扫描自动覆盖。
    """
    guard = guarded_literals()
    hits = []
    # 扫 tools/*.py ＋ tools/pkb/**/*.py，跳过 domain 自己
    files = [p for p in py_files(TOOLS)
             if not p.relative_to(TOOLS).as_posix().startswith('pkb/domain/')]
    for p in files:
        rel = p.relative_to(TOOLS).as_posix()
        for lineno, val in code_strings(p):
            if val in guard:
                hits.append(f'{rel}:{lineno} 硬编码 `{val}`——应 import {guard[val]}（domain/）')
    if hits:
        for h in sorted(hits)[:12]:
            err('口径', h)
        if len(hits) > 12:
            err('口径', f'…另有 {len(hits) - 12} 处口径字面量')
        err('口径', '口径只能住在 pkb/domain/——改口径时要能一处改完')
    else:
        ok(f'口径单源：{len(guard)} 个取值只在 domain/ 出现（{len(files)} 个文件已扫）')


def run(argv=None):
    ap = argparse.ArgumentParser(description='文档一致性与 log 卫生校验')
    ap.add_argument('--quiet', action='store_true', help='只报问题')
    args = ap.parse_args(list(argv or []))
    quiet = args.quiet
    if not AGENTS.exists() or not INDEX.exists():
        return Result(Verdict.BAD_INPUT, '路径错误：未找到 AGENTS.md 或 index.md',
                      ['路径错误：未找到 AGENTS.md 或 index.md'])

    # 模块级 reporter 复用，多次调用前必须清空，否则第二次跑会重复上一轮的结论
    _rep.oks.clear()
    _rep.errors.clear()
    _rep.warns.clear()

    docs = {
        'AGENTS': read(AGENTS, ''),
        'index': read(INDEX, ''),
        'README': read(README, ''),
        '专家定义': read(EXPERT, ''),
        '专家包README': read(EXPERT_DIR / 'README.md', ''),
        '运行状态': read(STATUS, ''),
    }

    check_interval(docs)
    check_seven_sections(docs)
    check_analysis_sections(docs)
    check_blacklist(docs)
    check_domain_literals()
    check_deleted_refs(docs)
    check_structure_numbers(docs)
    check_no_hardcoded_count(docs)
    check_expert_refs(docs)
    check_no_direct_calls()
    check_actions()
    check_ledger_numbers()
    check_expert_scripts()
    check_log()
    check_sources()

    lines = []
    if not quiet:
        lines.append('=== 文档一致性与 log 校验 ===')
    lines += _rep.to_lines(quiet=quiet)

    if _rep.errors:
        lines += ['', f'❌ {len(_rep.errors)} 项硬错误（{len(_rep.warns)} 条提示）']
        return Result(Verdict.FAIL,
                      f'文档一致性：{len(_rep.errors)} 项硬错误、{len(_rep.warns)} 条提示 ❌（改文档不改脚本）',
                      lines)
    lines += ['', f'✅ 文档一致 ✅（{len(_rep.warns)} 条提示）']
    return Result(Verdict.PASS,
                  f'文档一致性：0 硬错误、{len(_rep.warns)} 条提示 ✅（来源域名 0 命中）', lines)
