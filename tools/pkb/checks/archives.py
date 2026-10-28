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
                      card_files, card_parts, card_name,
                      Result, Verdict, write)
from pkb.domain import ARCHIVE_DATE_TOLERANCE, LEVELS, retired

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
    """卡片小节清单：[{card, date, no, title, key, chunk, part}]

    `part` 是小节实际落在哪个文件：序列卡（2026-10-28）的小节在卷里，不在主卡。
    补链时必须写回该小节所在的那个文件——写回主卡等于把链接加到一张没有小节的页上。
    """
    out = []
    for p in card_files(CARD_DIR):
        card = card_name(p)
        for part in card_parts(p):
            text = read(part, '')
            for m in SEC.finditer(text):
                end = text.find('\n### ', m.end())
                chunk = text[m.end():end if end != -1 else len(text)]
                n = NO.search(chunk)
                out.append({'card': card, 'date': parse_date(m.group(1)),
                            'no': norm(n.group(1)) if n else '',
                            'title': m.group(2).strip(), 'key': norm(m.group(2)),
                            'chunk': chunk, 'part': part})
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


def unlinked():
    """一手存档建好了，卡片却没指过去：[{card, title, file}]。

    为什么这算问题（2026-10-28）：`raw/articles/` 的 37 份原文就是「链接断了还查得到」
    的那一份备份，卡片不指过去，这个价值一分没兑现——盘点时只有 1 张卡提到过存档。
    判据只认**唯一匹配**（与 scan 同一套 match），匹配不上或有多候选都不报：
    那属于「该链哪一条还没定」，不是「漏了」。
    """
    idx, out = card_index(), []
    for arc in archives():
        sec = match(arc, idx)
        if sec and arc['file'][:-3] not in sec['chunk']:
            out.append({'card': sec['card'], 'title': sec['title'],
                        'file': arc['file'], 'part': sec['part']})
    return out


def _append_link(chunk, filename):
    """在「政策原文」那一行末追加 [[存档|原文存档]]；没有这一行就不硬插。"""
    stem = filename[:-3]
    for line in chunk.split('\n'):
        if '政策原文' in line and stem not in line:
            new = line.rstrip() + f' ｜ [[{stem}|原文存档]]'
            return chunk.replace(line, new, 1)
    return None


def _sec_chunk(text, title):
    """在一张卡的正文里按小节标题取 chunk；取不到返回 None。"""
    for m in SEC.finditer(text):
        if m.group(2).strip() == title:
            end = text.find('\n### ', m.end())
            return text[m.end():end if end != -1 else len(text)]
    return None


def run_fix():
    """补链（`run.py fix` 的一项）：唯一匹配才改，多候选跳过。返回 (处数, 行)。

    每条都重读一次该卡：前一条已经把文件写过了，拿旧 chunk 去 replace 会落空。
    序列卡的小节在卷里——写回 `item['part']` 指的那个文件，不是主卡。
    """
    n, lines = 0, []
    for item in unlinked():
        p = item['part']
        text = read(p, '')
        chunk = _sec_chunk(text, item['title'])
        if not chunk:
            continue
        new = _append_link(chunk, item['file'])
        if not new:
            continue
        write(p, text.replace(chunk, new, 1))
        n += 1
        lines.append(f"补链：{item['card']} / {item['title'][:22]} ← {item['file'][:34]}")
    return n, lines


def retired_in_place():
    """已终止却还留在卡里的小节：[{card, title, state}]。

    「移入归档」只有一个触发条件（2026-10-28）：政策已终止——不按时间。
    判定不靠日期、不靠人记，靠小节里自己声明的那一行 `> **状态**：已废止（被 … 取代）`；
    这条判据要核的就是**声明有没有被执行**：写了已终止却还躺在卡片目录里，
    说明「该搬的没搬」，而清单（`归档/index.md`）会一直把它算作在用政策。

    不阻断（本项恒 exit 0）：搬是人的动作，改哪一节、留哪一行指针都得人定。
    """
    out = []
    for sec in card_index():
        hit = retired(sec['chunk'])
        if hit:
            out.append({'card': sec['card'], 'title': sec['title'], 'state': hit[0]})
    return out


def run(argv=None):
    ap = argparse.ArgumentParser(description='卡片与一手存档的日期交叉核对（只报不阻断）')
    ap.parse_args(list(argv or []))
    if not CARD_DIR.exists():
        return Result(Verdict.BAD_INPUT, f'未找到产业卡目录：{CARD_DIR}', [f'✗ {CARD_DIR}'])

    same, bad, n = scan()
    bad += misplaced()
    left = unlinked()
    gone = retired_in_place()
    lines = ['=== 卡片 × 一手存档 ===',
             f'原文 {n} 份：日期一致 {same}，问题 {len(bad)}，卡片未引 {len(left)}']
    if not n:
        # 存档目录空着时不能整项「无结论」：待归档是**卡片侧**的事实，与存档无关。
        # 早退会把「已终止没搬」一并吞掉，而那正是这条判据存在的理由。
        lines.append('（raw/articles 为空或不存在——日期核对无结论；待归档照常核）')
    lines += [f'  · {why}' for why in bad]
    lines += [f'  · 未回流：{x["card"]} / {x["title"][:20]} ← {x["file"][:38]}' for x in left]
    lines += [f'  · 待移入归档：{x["card"]} / {x["title"][:24]}（{x["state"]}）'
              for x in gone]
    if not bad and n:
        lines.append('（只核「两份落盘物是否自洽」；两边一起错时本项查不出，外部核对仍在任务台账）')
    mark = '✅' if not bad and not left else '⚠️'
    summary = (f'一手存档 {n} 份：日期一致 {same} · 问题 {len(bad)} · '
               f'未回流 {len(left)} · 待归档 {len(gone)} {mark}')
    return Result(Verdict.PASS, summary, lines)
