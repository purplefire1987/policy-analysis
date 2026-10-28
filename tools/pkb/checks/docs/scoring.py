#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评估口径页 ↔ `pkb/domain/scoring.py`：只对**数值与名单**，不对措辞。

为什么值得一项检查：
    评分口径最怕的不是定错，是**两处各说一套**——页面写「每维 1/6」、代码里权重
    改了，或者扣分表把「撒谎」从 2 降到 1，谁都发现不了，直到下一次评估算出一个
    没人能复现的数。判据只认数：分值、权重合计、门槛线、六维与助手六维的名单。
    「为什么撒谎最重」这类理由不核——核它只会逼人把话说短。

为什么不按文件名发现：与其余检查同一约定，入口在 `docs/__init__.py` 里显式调用，
顺序即报告顺序。
"""
import re

from pkb.domain import scoring as S

from ._state import err, ok, errors

DOC = '评估口径'


def _table(text, keyword):
    """取「## …keyword…」这一节下的第一张表：切成格子，去掉表头与分隔行。"""
    lines = text.split('\n')
    start = next((i for i, l in enumerate(lines)
                  if l.startswith('## ') and keyword in l), None)
    if start is None:
        return []
    rows = []
    for line in lines[start + 1:]:
        if line.startswith('## '):
            break
        if not line.strip().startswith('|'):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if not any(cells) or set(''.join(cells)) <= set('-: '):
            continue                       # 空行与 |---|---| 分隔行
        rows.append(cells)
    return rows[1:]


def _dims(text):
    """六维：名字、顺序、权重合计，以及「分从哪取」必须是可跑的命令。"""
    rows = _table(text, '二、六个维度')
    if len(rows) != len(S.DIMENSIONS):
        err(DOC, f'六维表 {len(rows)} 行，代码里 {len(S.DIMENSIONS)} 个维度——少一行就有一维不上分')
        return
    total = 0.0
    for i, (name, row) in enumerate(zip(S.DIMENSIONS, rows), 1):
        if not row[0].startswith(name):
            err(DOC, f'六维表第 {i} 行是「{row[0]}」，代码里是「{name}」')
            continue
        if 'run.py' not in row[3]:
            err(DOC, f'「{name}」的「分从哪取」没给可复跑命令——没命令的读数等于没核')
        try:
            num, _, den = row[1].partition('/')
            total += float(num) / float(den or 1)
        except ValueError:
            err(DOC, f'「{name}」的权重「{row[1]}」读不出数')
    if abs(total - 1.0) > 1e-9:
        err(DOC, f'六维权重合计 {total:.3f}，应为 1.000——等权即每维 1/6，改一维要同时改六维')


def _defects(text):
    """四类文档问题：类别必须一一对应，分值必须逐字相同。"""
    got = {}
    for row in _table(text, '三、扣分'):
        if row[0] not in S.DOC_DEFECTS:
            err(DOC, f'扣分表出现代码里没有的类别「{row[0]}」——加类别要同时改 scoring.py')
            continue
        try:
            got[row[0]] = (float(row[2]), float(row[3]))
        except (ValueError, IndexError):
            err(DOC, f'「{row[0]}」的每处扣分／封顶读不出数')
    for name, pair in S.DOC_DEFECTS.items():
        if name not in got:
            err(DOC, f'扣分表缺「{name}」——它在代码里仍生效，页面上不写，读者会以为不扣')
        elif got[name] != pair:
            err(DOC, f'「{name}」分值不一致：页面 {got[name]}，代码 {pair}')


def _gates(text):
    """门槛线与助手六维：一个阈值、一份名单。"""
    m = re.search(r'≥\s*(\d+)', text)
    if not m or int(m.group(1)) != S.PASS_LINE:
        seen = m.group(0) if m else '没写'
        err(DOC, f'门槛线对不上：页面写「{seen}」，代码是 ≥{S.PASS_LINE}')
    names = [r[0] for r in _table(text, '五、助手')]
    if names != list(S.ASSISTANT_DIMENSIONS):
        err(DOC, f'助手六维对不上：页面 {names}，代码 {list(S.ASSISTANT_DIMENSIONS)}')


def check_rubric(docs):
    """三组断言都过才报绿；任一不过即 exit 1（改文档不改代码，除非理由也一起改）。"""
    text = docs.get(DOC, '')
    if not text:
        err(DOC, '页面不存在或未纳入 _load_docs——评分口径没有判据看着，等于没有')
        return
    before = len(errors)
    _dims(text)
    _defects(text)
    _gates(text)
    if len(errors) == before:
        ok(f'{DOC}：六维权重合计 1、四类扣分与代码一致、'
           f'门槛线 ≥{S.PASS_LINE}、助手六维 {len(S.ASSISTANT_DIMENSIONS)} 项')
