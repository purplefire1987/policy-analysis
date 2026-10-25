#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集健康：区分「跑了但没采到」与「根本没跑」。

为什么单独立一项：此前判断采集是否正常只有两条线索，两条都不牢——
①采集日志的最后一行：漏写一行与「跑了写 0」在页面上没区别，真正的区别是
  「有没有那一行」，而恰好漏写时这个区别就消失了；
②运行状态的灯：它是人工填的，可能与日志互相矛盾（灯 🟢 而日志停在三天前）。
本项把两者交叉核对，结论落到三种状态，措辞不同即处置不同：
  正常         —— 有轮次、有新增
  跑了但 0 条  —— 有轮次、无新增：**不是漏采**，别去查自动化有没有跑
  根本没跑     —— 最近轮次超一个节拍：先查为什么没跑，别当成「今天没政策」

只有采集有逐日台账；体检与周观点以运行状态本页为台账（没有逐日行），
所以它们的节拍漂移由 `check_docs` 的节拍比对兜，不在这里重复。
"""
import argparse
import datetime
import re

from pkb.core import (COLLECT_LOG, STATUS, Result, Verdict,
                      read, md_section_lines, table_rows, parse_date)

ROUND_MARK = re.compile(r'第\s*[0-9零一二三四五六七八九十百]+\s*轮')
NOT_RUN = ('未运行', '未跑', '无产出')
DASH = ('—', '-', '–', '')
ZERO = ('0', '无新增', '无')
LAMP_OK, LAMP_BAD = '🟢', '🔴'
BEAT_DAYS = 1            # 采集按日跑：超过 1 天没有轮次即「该跑没跑」
# 「0 也写 0」的生效日：更早的行用 — 指路 log.md，改写成 0 等于伪造数据，
# 规则从建立起往前适用、不溯及既往。用固定日期而不是「最近 N 天」——
# 滑动窗口会让违规拖两周就自动消失，那等于没有判据。
RULE_SINCE = datetime.date(2026, 10, 24)


def today():
    """可被测试替换：判定依赖「今天」，不能写死在模块里。"""
    return datetime.date.today()


def parse_collect_log(text):
    """采集日志 → 记录列表（按日期倒序）。只认日期能解析的行。"""
    out = []
    for r in table_rows(md_section_lines(text, '运行台账')):
        if len(r) < 6:
            continue
        d = parse_date(r[0])
        if not d:
            continue
        out.append({'date': d, 'round': r[1], 'policy': r[2],
                    'signal': r[4], 'status': r[5],
                    'note': r[6] if len(r) > 6 else ''})
    out.sort(key=lambda x: x['date'], reverse=True)
    return out


def is_round(rec):
    """真正的采集轮次：轮次列是「第 N 轮」且状态不是「未运行」。

    手工补录、结构重构也算写入，但不算自动化跑过——本项问的是后者。
    """
    return (bool(ROUND_MARK.search(rec['round']))
            and not any(k in rec['status'] for k in NOT_RUN))


def lamp_of(text):
    """运行状态「当前状态」表里采集那一行的灯。找不到返回空串。"""
    for r in table_rows(md_section_lines(text, '当前状态')):
        if r and r[0].strip() == '采集':
            return r[-1].strip()
    return ''


def state_of(recs, d0):
    """三分状态：normal / zero / missing，外加诊断所需的中间量。"""
    rounds = [r for r in recs if is_round(r)]
    if not rounds:
        return {'kind': 'none', 'rounds': rounds, 'last': None, 'days': None}
    last = rounds[0]
    days = (d0 - last['date']).days
    if days > BEAT_DAYS:
        kind = 'missing'
    elif last['policy'].strip() in DASH or last['policy'].strip() in ZERO:
        kind = 'zero'
    else:
        kind = 'normal'
    traced = [r for r in recs if r['date'] > last['date']]
    return {'kind': kind, 'rounds': rounds, 'last': last,
            'days': days, 'traced': traced}


def _judge(recs, lamp, d0):
    """三件事一次判完：三分状态、灯交叉核对、「0 也写 0」。

    返回 (st, lamp, errs, warns)。判据只在这里，渲染与摘要不重算。
    """
    st = state_of(recs, d0)
    errs, warns = [], []
    if st['kind'] == 'none':
        return st, lamp, errs, warns

    last, days = st['last'], st['days']
    if st['kind'] == 'missing':
        trail = ('中间有「未运行」留痕，是跑了失败/明确没跑' if st['traced']
                 else '中间连「未运行」都没写，是根本没跑')
        errs.append(f'最近采集轮次 {last["date"]}（{days} 天前），已超 {BEAT_DAYS} 天节拍'
                    f'—— {trail}')
    elif st['kind'] == 'zero':
        warns.append(f'{last["date"]} 跑了但新增 0 条、信号 {last["signal"]} 条'
                     '——这是「没采到」，不是「没跑」，别去重跑自动化')

    if days > BEAT_DAYS and lamp == LAMP_OK:
        errs.append(f'运行状态的采集灯是 {LAMP_OK}，但最近轮次在 {days} 天前'
                    f'——按灯判定表该是 {LAMP_BAD}')
    if days <= BEAT_DAYS and lamp == LAMP_BAD:
        errs.append(f'运行状态的采集灯是 {LAMP_BAD}，但日志 {last["date"]} 有轮次记录'
                    '——灯与记录矛盾，改灯或补日志')

    bad_zero = [r for r in st['rounds']
                if '✅' in r['status'] and r['policy'].strip() in DASH]
    bad_new = [r for r in bad_zero if r['date'] >= RULE_SINCE]
    bad_old = [r for r in bad_zero if r['date'] < RULE_SINCE]
    if bad_new:
        errs.append(f'{len(bad_new)} 行（{RULE_SINCE} 起）状态已入库、新增数却写成 —/空'
                    '（规则：0 也写 0，禁 — 与留空）')
    if bad_old:
        warns.append(f'{len(bad_old)} 行历史记录用 — 指路 log.md（规则生效前），'
                     '不阻断、不要改写成 0（那是伪造）')
    return st, lamp, errs, warns


def _lines(st, lamp, d0, errs, warns):
    """明细：先说今天与最近轮次，再列问题，最后给三分判定表。"""
    last, days = st['last'], st['days']
    out = ['=== 采集健康 ===',
           f'今天：{d0}　最近轮次：{last["date"]}（{days} 天前）　节拍：每日',
           f'最近一条：{last["round"]}｜政策 {last["policy"]}｜信号 {last["signal"]}'
           f'｜{last["status"]}',
           f'运行状态的灯：{lamp or "（未找到采集行）"}',
           '']
    out += [f'✗ {e}' for e in errs]
    out += [f'⚠ {w}' for w in warns]
    if not errs and not warns:
        out.append('✅ 三分状态判定：正常（有轮次、有新增）')
    out += ['', '最近 5 条记录：']
    out += [f'  {r["date"]}｜{r["round"]}｜政策 {r["policy"]}｜信号 {r["signal"]}'
            f'｜{r["status"]}' for r in st['rounds'][:5]]
    out += ['', '三分状态（措辞即处置）：',
            '  正常        → 无需动作',
            '  跑了但 0 条 → 查采集源/额度，不要重跑',
            '  根本没跑    → 查自动化为什么没跑，别当成「今天没政策」']
    return out


def _summary(st, lamp):
    """一句话结论：三分状态必须在这行就能看出来，不然调用方等于没看见。"""
    last, days = st['last'], st['days']
    if st['kind'] == 'zero':
        return (f'采集健康：{last["date"]} 已跑但 0 新增（没采到，非漏跑），'
                f'灯 {lamp or "—"}')
    return (f'采集健康：{last["date"]}（{days} 天前）{last["round"]}，'
            f'政策 {last["policy"]} 条、信号 {last["signal"]} 条，'
            f'灯 {lamp or "—"} 与记录一致')


def run(argv=None):
    """返回 Result；明细在 lines，不打印。"""
    argparse.ArgumentParser(description='采集健康：区分跑了没采到与根本没跑').parse_args(
        list(argv or []))

    log = read(COLLECT_LOG, '')
    if not log:
        return Result(Verdict.BAD_INPUT, f'采集日志不存在：{COLLECT_LOG}',
                      [f'✗ 找不到 {COLLECT_LOG}'])

    d0 = today()
    st, lamp, errs, warns = _judge(parse_collect_log(log), lamp_of(read(STATUS, '')), d0)
    if st['kind'] == 'none':
        return Result(Verdict.FAIL,
                      '采集日志里没有任何采集轮次记录——无从判断采到哪天',
                      ['✗ 运行台账里没有「第 N 轮」行：要么从没跑过，要么跑了没留痕',
                       '   判据：有这一行才算跑过；「今天没政策」不能替代这一行。'])

    lines = _lines(st, lamp, d0, errs, warns)
    if errs:
        return Result(Verdict.FAIL, errs[0], lines)
    return Result(Verdict.PASS, _summary(st, lamp), lines)
