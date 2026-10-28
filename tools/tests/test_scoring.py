#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评估口径判据：自己也得被实测过一次。

为什么单列：这一项是新写的，**从建立起就没报过错**——判据不实测等于没写
（`--fix` 的正则写全角冒号、三年没修成过也不报错，是同一个坑）。
所以每条断言都留一个「把它改坏，必须报」的用例：权重不平、缺一维、分值不等、
门槛线被改、助手名单少一项。全是纯文本，不落盘、不读真库，空库 CI 照样跑。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.docs import _state as S            # noqa: E402
from pkb.checks.docs import scoring as SC         # noqa: E402

DIMS = ('内容获取与结构化', '格式转换', '编辑与版式',
        '安全合规与审计', '自动化与 AI 增强', '归档与生命周期')
ASSIST = ('模块化', '知识库', '自动化', '归口', '可维护', '复用与可测')


def page(weights=None, defects=None, gate='90', assist=ASSIST, drop=None):
    """拼一份最小合规页；每个参数都是「改坏一处」的开关。"""
    weights = weights or ['1/6'] * len(DIMS)
    rows = [f'| {d} | {w} | 判什么 | `run.py check` | 锚点 |'
            for d, w in zip(DIMS, weights) if d != drop]
    head = ('## 二、六个维度（各占 1/6）\n\n'
            '| 维度 | 权重 | 判什么 | 分从哪取（可复跑） | 锚点 |\n|---|---|---|---|---|\n')
    ded = defects or {'撒谎': (2.0, 8.0), '自相矛盾': (1.0, 5.0),
                      '过期': (1.0, 5.0), '重复': (0.5, 3.0)}
    drows = [f'| {k} | 判据 | {p} | {c} |' for k, (p, c) in ded.items()]
    dhead = ('## 三、扣分：文档四类问题\n\n'
             '| 类别 | 判据 | 每处扣 | 单次封顶 |\n|---|---|---|---|\n')
    ghead = f'## 四、门槛\n\n| 门槛 | 判据 | 不过 |\n|---|---|---|\n| 每一维 ≥{gate} | 见上 | 未达标 |\n'
    ahead = ('## 五、助手自身的六维（10 分制）\n\n'
             '| 维度 | 判什么 |\n|---|---|\n')
    arows = [f'| {a} | 判什么 |' for a in assist if a != drop]
    return '# 评估口径\n\n' + head + '\n'.join(rows) + '\n\n' + dhead + '\n'.join(drows) \
        + '\n\n' + ghead + '\n' + ahead + '\n'.join(arows) + '\n'


def judge(text):
    S.rep.oks.clear()
    S.rep.errors.clear()
    S.rep.warns.clear()
    SC.check_rubric({'评估口径': text})
    return [m for _i, m in S.rep.errors]


class Test合规页(unittest.TestCase):
    def test_合规页无错误(self):
        self.assertEqual(judge(page()), [])


class Test改坏必须报(unittest.TestCase):
    def test_权重不平要报(self):
        w = ['1/5'] + ['1/6'] * 5
        self.assertTrue(any('权重合计' in e for e in judge(page(weights=w))))

    def test_缺一维要报(self):
        self.assertTrue(any('六维表' in e for e in judge(page(drop='归档与生命周期'))))

    def test_缺一类扣分要报(self):
        d = {'撒谎': (2.0, 8.0)}          # 只剩一类：其余三类必须被点名
        errs = judge(page(defects=d))
        self.assertTrue(any('缺「重复」' in e for e in errs))

    def test_分值不一致要报(self):
        d = {'撒谎': (1.0, 8.0), '自相矛盾': (1.0, 5.0),
             '过期': (1.0, 5.0), '重复': (0.5, 3.0)}
        self.assertTrue(any('撒谎」分值不一致' in e for e in judge(page(defects=d))))

    def test_门槛线被改要报(self):
        self.assertTrue(any('门槛线' in e for e in judge(page(gate='85'))))

    def test_助手名单少一项要报(self):
        errs = judge(page(assist=ASSIST[:5]))
        self.assertTrue(any('助手六维' in e for e in errs))

    def test_页面缺失要报(self):
        errs = judge('')
        self.assertTrue(any('不存在' in e for e in errs))
