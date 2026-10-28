#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`core/stamp.py`：覆盖式页面「只有时间戳变了」的判定。

为什么值得单测：这条判据一坏，症状是**静默的**——多出一次「只有时间变了」的
提交，看上去像正常更新。定时任务挂上之后，一年的提交历史里会多出五十多条噪音，
而没有任何一项检查会报。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core.stamp import strip, unchanged      # noqa: E402


class TestStamp(unittest.TestCase):
    def test_只有时间戳变算没变(self):
        old = '# 告警\n\n> 生成时间：2026-10-29 00:52\n\n- A\n'
        new = '# 告警\n\n> 生成时间：2026-10-29 09:10\n\n- A\n'
        self.assertTrue(unchanged(old, new, '生成时间：'))

    def test_内容变了就是变了(self):
        old = '> 生成时间：2026-10-29 00:52\n\n- A\n'
        new = '> 生成时间：2026-10-29 00:52\n\n- A\n- B\n'
        self.assertFalse(unchanged(old, new, '生成时间：'))

    def test_旧文件为空时必须写(self):
        self.assertFalse(unchanged('', '> 生成时间：x\n', '生成时间：'))

    def test_前缀按字面匹配不当地正则(self):
        """前缀里有 `.`／`(` 时不转义就会误伤——`内容生成于：` 里没有，但下一个人会写。"""
        old = '> 生成于(草稿)：A\n正文一\n'
        new = '> 生成于(草稿)：B\n正文二\n'
        self.assertFalse(unchanged(old, new, '生成于(草稿)：'))

    def test_只抹指定前缀别的行不动(self):
        old = '> 生成时间：A\n> 内容生成于：A\n正文\n'
        new = '> 生成时间：B\n> 内容生成于：A\n正文\n'
        self.assertTrue(unchanged(old, new, '生成时间：'))
        self.assertFalse(unchanged(old, new, '内容生成于：'))

    def test_strip_不碰行内出现该词的行(self):
        """正文里提到「生成时间：」不算时间戳行——只抹行首带 `> ` 的那一行。"""
        text = '- 说明：本页有「生成时间：」一行\n'
        self.assertEqual(strip(text, '生成时间：'), text)


if __name__ == '__main__':
    unittest.main()
