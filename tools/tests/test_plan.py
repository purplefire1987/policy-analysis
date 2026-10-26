#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""派活清单里的「检索：」提示。

为什么测：这行是 2026-10-26 新加的，目的是把「不知道从哪找」这一步省掉。
它必须只是**从卡片已有字段整理出的检索式**——机关来自小节里的「发文机关」，
标题主干是机械去噪。一旦它开始生成判断、或开始编造机关名，就从提示变成了伪造。
所以测试同时钉两条：去噪规则本身，以及「只有一行、不含观点句」。
"""
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
