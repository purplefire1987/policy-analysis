#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""观点覆盖三分类：`（待补全）` 必须算未覆盖。

为什么单测这一条：覆盖率是体检里唯一会被人为「解释」掉的指标。
把 (b) 占位算成已覆盖，整页就是绿的，而实际一个字都没写——这比不报更危险。
classify() 是三档的唯一判据，故直接钉住它。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.views import classify            # noqa: E402

A = '**各方观点**\n| 来源 | 立场 | 观点 |\n|---|---|---|\n| 券商 | 看多 | 增持 |\n**观点辨析**\n一致。\n'
B = '**各方观点**\n（待补全）\n**观点辨析**\n（待补全）\n'
C = '**核心要点**\n只有要点，没有观点标题。\n'


class Test三分归位(unittest.TestCase):
    def test_两标题加正文算完整(self):
        self.assertEqual(classify(A), 'a')

    def test_占位算未覆盖(self):
        self.assertEqual(classify(B), 'b', '（待补全）必须计为未覆盖，否则覆盖率达标本是假的')

    def test_缺标题算无观点(self):
        self.assertEqual(classify(C), 'c')

    def test_只有一方面标题也算无观点(self):
        """两个标题缺一即 (c)——采集提示词要求两个标题都写，少一个就是没写。"""
        self.assertEqual(classify('**各方观点**\n有内容\n'), 'c')

    def test_有正文但含待补全仍是b(self):
        mixed = '**各方观点**\n| 来源 | 观点 |\n|---|---|\n| A | B |\n（待补全）\n**观点辨析**\n待补全\n'
        self.assertEqual(classify(mixed), 'b', '只要还留着待补全，就不能算完整')


class Test待补全只看观点两节(unittest.TestCase):
    """「（待补全）」出现在文号栏，不算观点待补全（2026-10-28 踩过的坑）。

    为什么测：判据原本是「整节 grep（待补全）」。当天补文号时给 16 个小节填了
    「（待补全）」，覆盖率立刻从 83.4% 掉到 74.5%——看起来像补录倒退 14 条，
    实际是判据把另一个栏位的占位符也认成了观点欠账。
    """

    def test_文号待补全不影响观点判定(self):
        with_blank_docnum = ('**发文机关**：甲部 ｜ **文号**：（待补全） ｜ [政策原文](u)\n\n'
                             '**各方观点**\n| A | B |\n**观点辨析**\n已辨析。\n')
        self.assertEqual(classify(with_blank_docnum), 'a',
                         '文号（待补全）与观点欠账是两件事，不能一起算')

    def test_观点节内待补全仍算b(self):
        doc = '**各方观点**\n（待补全）\n**观点辨析**\n已写。\n**影响判断**\n'
        self.assertEqual(classify(doc), 'b')


if __name__ == '__main__':
    unittest.main()
