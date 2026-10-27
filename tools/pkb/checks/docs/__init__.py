#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档一致性校验：核对 AGENTS / README / 专家定义 是否还与系统实际相符，并检查 log.md 卫生。

为什么需要它：
    规则只写一处（AGENTS.md），但执行副本散在库外——README、专家包定义、三个自动化
    提示词。库内脚本查不到它们，改一处漏一处也不会报错。历史上因此出过：专家定义
    节名写错、README 写了已废弃的目录路径、体检提示词漏跑新脚本。
    本检查把「会撒谎的文档」当成待检对象，每 2 天体检时跑一次。

判据来源（单一）：
    AGENTS.md 是唯一规则来源。其余文档与它不一致，一律报错——不反过来改 AGENTS。
    脚本数量、模板数量这类「易变且无校验价值」的数字，三处都不许写死。

边界（2026-10-26 审计补记）：
    它只查**结构化断言**（节拍、节名与模板、黑名单、动作表集合、结构数字、引用有效性、
    专家包形态）。**叙述性描述查不出来**——「脚本会自动发现」「raw 只读」这类句子
    改没改，只能人读。别把这份检查当成文档漂移的完整防线。

不提供自动修复：「以哪份为准」是人的判断（改 AGENTS 还是改 README，后果不同）。

为什么拆成包（2026-10-26）：原来一个 626 行文件装 15 个检查，改任何一项都要碰
同一个文件。现在按「被核对的对象」分组，每组一个子模块：
    declared.py     文档声明（节拍、周观点节名、分析报告节名）
    consistency.py  库内容交叉核对（黑名单、删页、结构数字、脚本数量、专家引用）
    ledger.py       入口与台账（动作表、直调脚本、台账读数）
    expert_pkg.py   专家包入口形态
    hygiene.py      log.md 卫生
    dnsource.py     来源域名
    literals.py     口径单源扫描
执行顺序即报告顺序，体检提示词与历史报告都对着这个顺序看，**不要重排**。
"""
import argparse

from pkb.core import (AGENTS, INDEX, README, STATUS, EXPERT_MD, EXPERT_DIR, EXPERT_SKILL,
                      OVERVIEW_DIR, read, Result, Verdict)

from . import consistency, declared, dnsource, expert_pkg, hygiene, ledger, literals
from ._state import rep

EXPERT = EXPERT_MD


def _load_docs():
    """被交叉核对的那几份文档，一次读齐。缺哪份就传空串，由各检查自己判。

    **只放真被读的键**：`index` 曾在这里读进来却没有任何检查用它，而它让
    「本检查核对 AGENTS／index／README…」这句话听起来是真的（2026-10-26 核出并删）。
    加键之前先确有一个检查会读它——否则读盘只是把「已核对」演给读者看。
    10-26 又加回 index／政策速览／SKILL：`check_structure_numbers` 现在要扫它们里面的
    结构数字（同一个数在规则类文档里共有 9 处），读进来是真被消费的。
    """
    return {
        'AGENTS': read(AGENTS, ''),
        'index': read(INDEX, ''),
        '政策速览': read(OVERVIEW_DIR / '政策速览.md', ''),
        'README': read(README, ''),
        '专家定义': read(EXPERT, ''),
        '专家包README': read(EXPERT_DIR / 'README.md', ''),
        'SKILL': read(EXPERT_SKILL / 'SKILL.md', ''),
        '运行状态': read(STATUS, ''),
    }


def _conclude(quiet):
    """结论：错误数与提示数只在这里成型，避免两处各算一遍。"""
    lines = [] if quiet else ['=== 文档一致性与 log 校验 ===']
    lines += rep.to_lines(quiet=quiet)
    if rep.errors:
        lines += ['', f'❌ {len(rep.errors)} 项硬错误（{len(rep.warns)} 条提示）']
        return Result(Verdict.FAIL,
                      f'文档一致性：{len(rep.errors)} 项硬错误、{len(rep.warns)} 条提示 ❌（改文档不改脚本）',
                      lines)
    lines += ['', f'✅ 文档一致 ✅（{len(rep.warns)} 条提示）']
    return Result(Verdict.PASS,
                  f'文档一致性：0 硬错误、{len(rep.warns)} 条提示 ✅（来源域名 0 命中）', lines)


def run(argv=None):
    ap = argparse.ArgumentParser(description='文档一致性与 log 卫生校验')
    ap.add_argument('--quiet', action='store_true', help='只报问题')
    args = ap.parse_args(list(argv or []))
    if not AGENTS.exists() or not INDEX.exists():
        return Result(Verdict.BAD_INPUT, '路径错误：未找到 AGENTS.md 或 index.md',
                      ['路径错误：未找到 AGENTS.md 或 index.md'])

    # 模块级 reporter 复用，多次调用前必须清空，否则第二次跑会重复上一轮的结论。
    # 用 .clear() 而不是重建：子模块持有的 errors/oks 是同一 list 的别名。
    rep.oks.clear()
    rep.errors.clear()
    rep.warns.clear()

    docs = _load_docs()
    declared.check_interval(docs)
    declared.check_week_sections(docs)
    declared.check_analysis_sections(docs)
    consistency.check_blacklist(docs)
    literals.check_domain_literals()
    consistency.check_deleted_refs(docs)
    consistency.check_structure_numbers(docs)
    consistency.check_no_hardcoded_count(docs)
    consistency.check_expert_refs(docs)
    ledger.check_no_direct_calls()
    ledger.check_ledger_shape()
    ledger.check_ledger_values()
    ledger.check_ledger_numbers()
    ledger.check_ledger_hygiene()
    ledger.check_release_logged()
    expert_pkg.check_expert_scripts()
    hygiene.check_log()
    dnsource.check_sources()

    return _conclude(args.quiet)
