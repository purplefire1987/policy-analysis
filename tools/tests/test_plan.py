#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""派活清单里的「检索：」提示。

为什么测：这行是 2026-10-26 新加的，目的是把「不知道从哪找」这一步省掉。
它必须只是**从卡片已有字段整理出的检索式**——机关来自小节里的「发文机关」，
标题主干是机械去噪。一旦它开始生成判断、或开始编造机关名，就从提示变成了伪造。
所以测试同时钉两条：去噪规则本身，以及「只有一行、不含观点句」。
"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import plan as P        # noqa: E402


def item(title, org=''):
    return {'card': '消费与商贸', 'date': '2026-10-09', 'title': title,
            'state': 'c', 'kind': '无标题', 'org': org}


class Test检索提示(unittest.TestCase):
    def test_带机关与标题主干(self):
        line = P.search_hint(item('关于加快推进科技兴商的意见', '商务部'))
        self.assertTrue(line.startswith('     检索：商务部 '), line)
        self.assertIn('加快推进科技兴商', line)
        self.assertNotIn('关于加快', line)
        self.assertNotIn('的意见', line)

    def test_去书名号与引号(self):
        line = P.search_hint(item('《"十五五"规划纲要》', '国务院'))
        self.assertNotIn('《', line)
        self.assertNotIn('"', line)

    def test_没有发文机关时不出现双空格(self):
        line = P.search_hint(item('关于某事的通知', ''))
        self.assertIn('检索：某事', line)
        self.assertNotIn('： ', line)

    def test_短名带等N部门(self):
        chunk = '**发文机关**：商务部、中央网信办、工业和信息化部 ｜ **文号**：无'
        self.assertEqual(P.short_org(chunk), '商务部等 3 部门')

    def test_括注不进检索式(self):
        chunk = '**发文机关**：国务院（国家发展改革委、商务部编制） ｜ **文号**：国发〔2026〕1号'
        self.assertEqual(P.short_org(chunk), '国务院')

    def test_取不到机关返回空串而不是猜(self):
        self.assertEqual(P.short_org('**文号**：无'), '')

    def test_只有一行且不含观点内容(self):
        line = P.search_hint(item('关于开展人工智能应用服务商培育专项行动的通知', '工业和信息化部办公厅'))
        self.assertNotIn('\n', line)
        self.assertLessEqual(len(line), 60, line)


class Test领活闸门(unittest.TestCase):
    """闸门自 2026-10-28 起按「距上次领取天数」判，不再读体检运行日。

    改的理由：挂在体检节拍上，等于让补采节奏被体检频率绑架——想降体检频率就拖慢
    存量清零，想加快补采就得每 2 天写三页。闸门要防的只是「领了不补」。
    """

    def test_从未领过能领(self):
        self.assertTrue(P.claim_ok(None))

    def test_距上次领取满闸门天数就能领(self):
        self.assertTrue(P.claim_ok(P.TODAY - datetime.timedelta(days=P.GATE_DAYS)))

    def test_差一天不能领(self):
        self.assertFalse(P.claim_ok(P.TODAY - datetime.timedelta(days=P.GATE_DAYS - 1)))

    def test_今天领过不能领(self):
        self.assertFalse(P.claim_ok(P.TODAY))


LEDGER_DOC = """## 二、未闭环项

| 编号 | 首次发现 | 问题 | 类型 | 负责环节 | 解法 | 状态 | 最近更新 | 关闭依据与下一步 |
|---|---|---|---|---|---|---|---|---|
| T-1 | 2026-10-01 | 甲 | 结构 | 采集 | 机器 | 🆕 待办 | 2026-10-01 | 待办 |
| T-2 | 2026-10-01 | 乙 | 机制 | 体检 | 用户 | 🆕 待办 | 2026-10-01 | 待办 |
| T-3 | 2026-10-01 | 丙 | 结构 | 采集 | 机器 | ✅ 已关闭 | 2026-10-01 | 已修 |
| T-4 | 2026-10-01 | 丁 | 结构 | 体检 | 机器 | 🆕 待办 | 2026-10-01 | 待办 |
"""


class Test台账分堆(unittest.TestCase):
    """「解法」把待办分成两堆：机器自己会做的，与等用户拍板的（2026-10-28 增）。

    为什么测：用户读台账真正要问的是「这条要不要我动手」，而不是「账在谁名下」。
    混在一起的代价是那些等拍板的行看起来像「没做完」，被反复派给采集。
    """

    def setUp(self):
        self._old = P.read
        P.read = lambda *_a, **_k: LEDGER_DOC

    def tearDown(self):
        P.read = self._old

    def test_机器解法的进采集清单(self):
        todo, _mine = P._todo()
        self.assertEqual([t['id'] for t in todo],
                         ['T-1'], '只抽 采集＋机器；体检的不派给采集，已关闭的不派')

    def test_用户解法的单列不混进采集清单(self):
        todo, mine = P._todo()
        self.assertEqual([t['id'] for t in mine], ['T-2'])
        self.assertNotIn('T-2', [t['id'] for t in todo])

    def test_已关闭的不进任何一堆(self):
        todo, mine = P._todo()
        self.assertNotIn('T-3', [t['id'] for t in todo + mine])
