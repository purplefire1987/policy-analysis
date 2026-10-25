#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析报告的字数口径：去 frontmatter、引用清单不计、双链只算显示文字。

为什么单测：篇幅是硬门槛（≤8000 字），而字数怎么算直接决定过不过。
口径一旦漂移（比如把引用清单算进去、或把 [[页面|显示]] 整个算成字），
同一个报告会在两次运行里给出不同结论——那时「不通过」就变成了噪音。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.analysis import body_for_count      # noqa: E402

FM = '''---
类型: 分析报告
标题: 某某专题
---
'''


class Test字数口径(unittest.TestCase):
    def test_frontmatter不计入(self):
        text = FM + '正文三个字\n'
        self.assertEqual(body_for_count(text), 5, '「正文三个字」＝5 个汉字，frontmatter 不计')

    def test_引用清单之后不计(self):
        text = FM + '正文\n\n## 八、引用清单\n这段不算\n'
        self.assertEqual(body_for_count(text), 2)

    def test_双链只算显示文字(self):
        text = FM + '见 [[政策卡片-能源|能源卡]] 与 [[政策卡片-金融]]\n'
        # 「见」「能源卡」「与」「政策卡片-金融」——双链的目标名若原样出现在显示文字里只算一次
        self.assertLess(body_for_count(text), 25)
        self.assertGreater(body_for_count(text), 0)

    def test_表格与引用块照常计入(self):
        """分析报告的字数口径不豁免表格（周观点才豁免）。"""
        text = FM + '| 甲 | 乙 |\n|---|---|\n| 丙 | 丁 |\n'
        self.assertGreater(body_for_count(text), 0)

    def test_空文件为零(self):
        self.assertEqual(body_for_count(FM), 0)


if __name__ == '__main__':
    unittest.main()
