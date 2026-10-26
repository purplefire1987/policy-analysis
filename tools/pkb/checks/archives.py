#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡片 × 一手存档：拿**两份独立落盘物**对一次日期（2026-10-26 增）。

为什么单列：卡片日期错了没人会报——T-20261024-17 里「稀土出口管制」整天记错一年，
是人工翻二手材料才发现的；T-20261026-05 的文号与公布月份对不上，也是靠外部检索。
本项只能做一半：`raw/articles/` 里每份存档自带 `政策日期`，卡片小节标题里也有日期，
两者不同即报。挡的是「改了一边没改另一边」与「落盘时日期解析错」。

**它挡不住「两边一起错」**：存档自己也记错时，两处一致、本项通过。所以通过不等于
日期正确——外部核对仍是台账的事（T-20261024-17／T-20261026-05）。这话必须写在这里，
否则下一个人会把绿灯当成「日期已核过」。

匹配只认两种精确形态：文号完全相同 → 标题逐字包含（≥6 字）。**不做相似度猜测**：
猜错会指向另一条政策，报出来的「不一致」比不报更坏（判据宁窄不错认）。
日期差在 `ARCHIVE_DATE_TOLERANCE` 天以内视为正常（印发与公开发布本来就常相隔几天）。
本项恒 exit 0：它报的是「两份物证不自洽」的线索，改哪边仍要人核。
"""
import argparse
import difflib
import re

from pkb.core import (ARTICLE_DIR, CARD_DIR, SIGNAL_DIR, parse_date, parse_fm, read,
                      Result, Verdict)
from pkb.domain import ARCHIVE_DATE_TOLERANCE, LEVELS

ORIGIN = LEVELS[0]      # 口径只从 domain 取，不写裸字符串

SEC = re.compile(r'^### (\d{4}-\d{2}-\d{2}) · (.+)$', re.M)
NO = re.compile(r'\*\*文号\*\*：\s*([^｜|\n]+)')
HEAD_LINE = re.compile(r'^(\d{4}-\d{2}-\d{2})_(.+)$')
LEVEL = re.compile(r'^存档级别:\s*(\S+)', re.M)
WORD_BAD = ('', '无', '—', '-', '无文号')
MIN_TITLE = 6


def norm(s):
    """去掉标点与空白再比——「（2026修订）」「·」这类差异不该影响匹配。"""
    return re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', s or '')


def card_index():
    """卡片小节清单：[{card, date, no, title, key}]"""
    out = []
    if not CARD_DIR.exists():
        return out
    for p in sorted(CARD_DIR.glob('*.md')):
        card = p.stem.replace('政策卡片-', '')
        text = read(p, '')
        for m in SEC.finditer(text):
            end = text.find('\n### ', m.end())
            chunk = text[m.end():end if end != -1 else len(text)]
            n = NO.search(chunk)
            out.append({'card': card, 'date': parse_date(m.group(1)),
                        'no': norm(n.group(1)) if n else '',
                        'title': m.group(2).strip(), 'key': norm(m.group(2))})
    return out


def archives():
    """一手存档清单：[{file, name_date, date, no, title}]"""
    out = []
    if not ARTICLE_DIR.exists():
        return out
    for p in sorted(ARTICLE_DIR.glob('*.md')):
        head = HEAD_LINE.match(p.stem)
        if not head:
            continue
        text = read(p, '')
        fm, _body = parse_fm(text)
        out.append({'file': p.name, 'name_date': parse_date(head.group(1)),
                    'date': parse_date(str(fm.get('政策日期', ''))),
                    'no': norm(str(fm.get('文号', ''))),
                    'title': p.stem.split('_')[-1]})
    return out


def match(arc, idx):
    """按文号 → 标题包含匹配；命中多条就放弃（宁可漏报，不猜）。"""
    if arc['no'] and arc['no'] not in [norm(x) for x in WORD_BAD]:
        hit = [s for s in idx if s['no'] == arc['no']]
        if len(hit) == 1:
            return hit[0]
    t = norm(arc['title'])
    if len(t) < MIN_TITLE:
        return None
    hit = [s for s in idx if s['key'] and (s['key'] in t or t in s['key'])]
    return hit[0] if len(hit) == 1 else None


def signal_index():
    """信号条目清单：[{date, title, key}]。

    为什么也要扫这里（2026-10-26 晚）：按「信号≠政策」口径转记之后，有些一手存档
    服务于信号而不是卡片——央行《关于人民币汇率的政策立场》就是一份正式发布文本，
    它进了 `raw/articles/`，但对应条目在政策信号页。只认卡片会把它报成「卡片漏了」，
    而它并不缺，只是归属不同。**报错了的判据比不报更坏**（会教人以后绕开它）。
    """
    out = []
    if not SIGNAL_DIR.exists():
        return out
    for p in sorted(SIGNAL_DIR.glob('*.md')):
        for m in SEC.finditer(read(p, '')):
            out.append({'date': parse_date(m.group(1)),
                        'title': m.group(2).strip(), 'key': norm(m.group(2))})
    return out


def scan():
    """返回 (日期一致条数, 问题[(级别, 说明)], 存档数)；纯计算，不打印。"""
    idx, sig, bad, same = card_index(), signal_index(), [], 0
    arcs = archives()
    for arc in arcs:
        if arc['date'] and arc['name_date'] and arc['date'] != arc['name_date']:
            bad.append(f"{arc['file']}：文件名日期 {arc['name_date']} 与 frontmatter "
                       f"政策日期 {arc['date']} 不一致——同一份文件说了两个日子")
        sec = match(arc, idx)
        if not sec:
            # 卡片里没有，再看是不是服务于信号条目：**同日** + 标题高度相近。
            # 为什么允许相似度而不用「逐字包含」：信号标题是编辑句（会加「发布」「首提」
            # 这类动词），文件标题是机关公文名，逐字包含几乎必然落空。限定同日，
            # 一天内的信号条目只有个位数，猜错代价可控；宁可漏匹配（报「没找到」）也不跨日猜。
            t = norm(arc['title'])
            hit = [s for s in sig if s['date'] == arc['date']
                   and difflib.SequenceMatcher(None, s['key'], t).ratio() >= 0.55]
            if len(hit) == 1:
                same += 1
                continue
            bad.append(f"{arc['file']}：按文号与标题都没找到对应卡片小节或信号条目——"
                       f"卡片漏了这条政策，或标题被改过")
            continue
        if not arc['date'] or not sec['date']:
            continue
        gap = abs((arc['date'] - sec['date']).days)
        if gap > ARCHIVE_DATE_TOLERANCE:
            bad.append(f"{arc['title'][:26]}：存档写 {arc['date']}，卡片（{sec['card']}）"
                       f"写 {sec['date']}，差 {gap} 天——至少一边错了，回原文核完改正确的那边")
        else:
            same += 1
    return same, bad, len(arcs)


def misplaced():
    """`raw/articles/` 里不该有「报道」：目录名是一手承诺，级别字段是自我声明。

    为什么要有这一条（2026-10-26）：分家之前 58 份里 26 份不是文件本身，
    而每份 frontmatter 早就写着 `存档级别: 官方报道`——**字段是对的，只是没人读**。
    现在的口径更硬：报道类根本不进 `raw/`（按内容归政策卡片或政策信号），
    所以「`articles` 里出现非原文」就是要报的。光靠 `fetch` 拦不住手工拷进来的那份。

    判据只认「自己声明的级别」，不判断级别本身对不对
    （那是填链接那一步的事，见 `domain/sources.py` 的 `level()`）。
    """
    out = []
    if not ARTICLE_DIR.exists():
        return out
    for p in sorted(ARTICLE_DIR.glob('*.md')):
        m = LEVEL.search(read(p, ''))
        lv = m.group(1).strip() if m else ''
        if lv and lv != ORIGIN:
            out.append(f'articles/{p.name}：自称「{lv}」，不是文件本身——'
                       f'`articles/` 只该放「{ORIGIN}」；报道类归政策卡片或政策信号，不进 raw/')
    return out


def run(argv=None):
    ap = argparse.ArgumentParser(description='卡片与一手存档的日期交叉核对（只报不阻断）')
    ap.parse_args(list(argv or []))
    if not CARD_DIR.exists():
        return Result(Verdict.BAD_INPUT, f'未找到产业卡目录：{CARD_DIR}', [f'✗ {CARD_DIR}'])

    same, bad, n = scan()
    bad += misplaced()
    if not n and not bad:
        msg = '一手存档 0 份（raw/articles 为空或不存在），本项无结论'
        return Result(Verdict.PASS, msg, [msg])
    lines = ['=== 卡片 × 一手存档 ===',
             f'原文 {n} 份：日期一致 {same}，问题 {len(bad)}']
    lines += [f'  · {why}' for why in bad]
    if not bad:
        lines.append('（只核「两份落盘物是否自洽」；两边一起错时本项查不出，外部核对仍在任务台账）')
    mark = '✅' if not bad else '⚠️'
    summary = f'一手存档 {n} 份：日期一致 {same} · 问题 {len(bad)} {mark}'
    return Result(Verdict.PASS, summary, lines)
