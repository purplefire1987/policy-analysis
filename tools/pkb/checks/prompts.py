#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提示词本体守门：现行唯一、命令真实、引用可达、不直调、抬头自洽。

为什么需要它：三个自动化提示词在**库外**（`automation-prompts/`），库内所有断言
都扫不到它们。2026-10-26 审计发现四份体检提示词并存、其中一份索引页自称
「当前版本 v5」而实际生效的是 v8——这类漂移过去只能靠人通读。

本项只守**结构化**的部分：
    A 现行唯一  每个自动化在顶层只能有一份提示词（旧版移进 `旧版/`）
    B 命令真实  `run.py <动作>`、`--only <项>` 必须在包内真实存在
    C 引用可达  `[[页面]]`、`` `wiki/…` `` 等路径、必含锚点必须真实存在
    D 不直调    提示词不得绕过入口直调 `tools/*.py`
    E 抬头自洽  自称「当前版本 vX」的文件，必须就是 vX 那份

**查不出来的**（别把这份检查当完整防线）：
  * 提示词里的口径说法是否与 AGENTS 一致——「影响三档」「黑名单」「第八节」
    有没有说过头，脚本只能比字面量，比不了语义；
  * 「脚本会自动发现」这类叙述性描述是否过期（就是它让 v5 那份静默失效）；
  * **存档是否等于真实跑在服务器上的那份**——运行源在自动化配置里，脚本读不到。
    所以本项能保证「存档内部自洽」，不能保证「存档就是现行」。
"""
import argparse
import re

from pkb.core import (
    PROMPT_DIR, PROMPT_ARCHIVE, VAULT,
    action_names, all_names, read, Reporter, Result, Verdict,
)
from pkb.domain import AUTOMATIONS, PROMPT_ANCHORS

ACTION_RE = re.compile(r'run\.py\s+([a-z][a-z_-]*)')
ONLY_RE = re.compile(r'--only\s+([a-z_]+)')
DIRECT_RE = re.compile(r'python[\d.]*\s+\S*tools/([A-Za-z_]\w*\.py)')
LINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
PATH_RE = re.compile(r'`((?:wiki|templates|raw)/[^`\s]+)`')
VERSION_RE = re.compile(r'当前版本[：:]\s*\**v(\d+)')

PLACEHOLDERS = ('{', '…', 'XX')


def _placeholder(text):
    """模板占位符不是真链接（`周观点-{周号}.md`、`[[页面-X]]`）。"""
    return any(k in text for k in PLACEHOLDERS)


def _registry_names():
    """检查项名（按名片段匹配 `--only`）。

    延迟导入：本模块由 `pkb.checks.__init__` 在顶部加载，顶层再 import 它就是环。
    """
    from pkb.checks import REGISTRY
    return [s.name for s in REGISTRY]


def _judge_group(rep, aid, aname, hits):
    """A 现行唯一：0 份＝丢了，多份＝不知道哪份生效，文件名缺 ID＝认不出来。"""
    if not hits:
        rep.err(aname, f'顶层没有提示词存档（缺 `{aname}-{aid}-<日期>.md`）——'
                       '自动化在跑、存档却没有，改动就无从对照')
        return
    if len(hits) > 1:
        rep.err(aname, f'{len(hits)} 份并存（{"、".join(p.name for p in hits)}）——'
                       '无法判断哪份生效；旧版移进 `旧版/`，顶层只留现行一份')
    elif aid not in hits[0].name:
        rep.err(aname, f'文件名缺自动化 ID「{aid}」——文件名是唯一能机器认领的凭据')
    else:
        rep.ok(f'{aname}（{aid}）：{hits[0].name}')


def _current(rep):
    """按自动化分组认领顶层文件。返回 [(aid, aname, [命中的文件])]。"""
    top = sorted(p for p in PROMPT_DIR.glob('*.md') if p.is_file())
    groups = []
    for aid, aname in AUTOMATIONS.items():
        hits = [p for p in top if aname in p.name or aid in p.name]
        _judge_group(rep, aid, aname, hits)
        groups.append((aid, aname, hits))
    return groups


def _commands(rep, name, text, actions, checks):
    """B 命令真实：动作名与 `--only` 目标都要能在包内找到。"""
    for m in ACTION_RE.finditer(text):
        if m.group(1) not in actions:
            rep.err(name, f'写了不存在的动作 `run.py {m.group(1)}`——'
                          f'现有：{"／".join(actions)}')
    for m in ONLY_RE.finditer(text):
        if not any(m.group(1).lower() in c for c in checks):
            rep.err(name, f'`--only {m.group(1)}` 匹配不到任何检查项（按名字片段匹配）')


def _direct(rep, name, text):
    """D 不直调：绕过入口拼脚本路径，模块一改名就失配且不报错。

    判据认**调用形态**（`python3 …/tools/xxx.py`）而不是「出现 tools/xxx.py」：
    采集提示词的正文里写着「不要自己拼 `tools/xxx.py` 路径」——那是禁令的例子，
    按字面判就会把「不准这样干」判成「这样干了」（本库 2026-10-25 在 `sys.exit(`
    判据上栽过同一跤）。
    """
    for m in DIRECT_RE.finditer(text):
        if m.group(1) != 'run.py':
            rep.err(name, f'直调 `tools/{m.group(1)}`——提示词只许走 `run.py`')


def _anchors(rep, name, text):
    """C-1 必含锚点：少了它这份提示词就不再「先读规则、收工自检」。"""
    for anchor, why in PROMPT_ANCHORS:
        if anchor not in text:
            rep.err(name, f'缺「{anchor}」（{why}）')


def _refs(rep, name, text, pages):
    """C-2 引用可达：wikilink 与库内路径必须真的存在。"""
    for m in LINK_RE.finditer(text):
        t = m.group(1).split('|')[0].split('#')[0].strip()
        if not t or _placeholder(t):
            continue
        if t not in pages:
            rep.err(name, f'[[{t}]] 在库里不存在——照着它走的 agent 会自己编一份')
    for m in PATH_RE.finditer(text):
        t = m.group(1).rstrip('/')
        if _placeholder(t):
            continue
        if not (VAULT / t).exists():
            rep.err(name, f'`{m.group(1)}` 不存在')


def _version(rep, name, text):
    """E 抬头自洽：自称 vX 却不是 vX 那份，就是索引页式漂移。"""
    m = VERSION_RE.search(text)
    if m and f'v{m.group(1)}' not in name:
        rep.err(name, f'抬头写「当前版本 v{m.group(1)}」，而文件名不是 v{m.group(1)} 那份'
                      '——索引页式漂移（旧版靠它冒充现行）')


def _inspect(rep, groups, actions, checks, pages):
    """逐份文件跑 E→B→D→C：顺序固定，输出顺序稳定，体检报告对得上。"""
    for _aid, _aname, hits in groups:
        for p in hits:
            text = read(p, '')
            _version(rep, p.name, text)
            _commands(rep, p.name, text, actions, checks)
            _direct(rep, p.name, text)
            _anchors(rep, p.name, text)
            if pages:
                _refs(rep, p.name, text, pages)


def run(argv=None):
    ap = argparse.ArgumentParser(
        description='提示词本体守门（现行唯一／命令真实／引用可达／不直调／抬头自洽）')
    ap.parse_args(list(argv or []))
    if not PROMPT_DIR.exists():
        msg = f'未找到提示词存档目录：{PROMPT_DIR}'
        return Result(Verdict.BAD_INPUT, msg, [msg, '（提示词守门不成立：无从比对）'])

    rep = Reporter()
    groups = _current(rep)
    n = sum(len(hits) for _a, _b, hits in groups)
    pages = all_names() if VAULT.exists() else set()
    if not pages:
        rep.warn('引用', '库内 0 页（空库或路径未挂载），跳过 wikilink 与路径校验')

    before = len(rep.errors)
    _inspect(rep, groups, action_names(), _registry_names(), pages)
    if len(rep.errors) == before:
        rep.ok(f'命令／引用／抬头：{n} 份文件 0 问题'
               f'（动作 {len(action_names())} 个、检查项 {len(_registry_names())} 个现读）')

    archived = len(list(PROMPT_ARCHIVE.glob('*.md'))) if PROMPT_ARCHIVE.exists() else 0
    rep.ok(f'旧版归档 {archived} 份（不参与现行判定）')

    head = f'=== 提示词本体（{PROMPT_DIR.name}/） ==='
    lines = [head] + rep.to_lines()
    if rep.errors:
        lines += ['', f'❌ {len(rep.errors)} 项硬错误（{len(rep.warns)} 条提示）——'
                      '改提示词文件，不改脚本；旧版一律移进 旧版/']
        return Result(Verdict.FAIL,
                      f'提示词本体：{len(rep.errors)} 处硬错误 ❌'
                      f'（{len(AUTOMATIONS)} 个自动化／现行 {n} 份／旧版 {archived} 份）', lines)
    lines += ['', f'✅ 提示词本体自洽 ✅（{len(rep.warns)} 条提示）',
              '（只验结构性断言：存档是否等于线上运行的那份，脚本读不到）']
    return Result(Verdict.PASS,
                  f'提示词本体：{len(AUTOMATIONS)} 个自动化各 1 份现行、旧版 {archived} 份，'
                  f'命令／引用／抬头 0 问题 ✅', lines)
