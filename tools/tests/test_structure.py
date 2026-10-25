#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构检查的两处易错判据：frontmatter 取原文、断链扫描的过滤规则。

为什么单测断链：它最容易「报一堆假警」——模板占位符 `[[政策链-XXX]]`、
表格里的 `[[页面\\|别名]]`、代码块里的示例，全都长得像断链。
假警一多，真断链就没人看了；反过来过滤太宽，真断链会被吞掉。
所以这里两侧都测：该报的报，该放过的放过。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import structure as S          # noqa: E402

CARD = '''---
名称: 能源
tags: [政策]
---
正文 [[政策卡片-甲]] 与 [[政策卡片-甲|甲卡]] 不算断链。
'''


class TestRawFmText(unittest.TestCase):
    def test_取出原文(self):
        got = S.raw_fm_text(CARD)
        self.assertIn('名称: 能源', got)
        self.assertNotIn('正文', got)

    def test_没有frontmatter返回空(self):
        self.assertEqual(S.raw_fm_text('只有正文\n'), '')


class Test断链过滤(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(S.issues.clear)

    def scan(self, files, names=('政策卡片-甲',)):
        for name, text in files.items():
            (self.root / name).write_text(text, encoding='utf-8')
        S.issues.clear()
        with mock.patch.object(S, 'VAULT', self.root):
            S.check_links(set(names))
        return [msg for _obj, msg in S.issues.get('6-断链', [])]

    def test_真断链要报(self):
        self.assertEqual(len(self.scan({'b.md': '见 [[不存在的页面]]\n'})), 1)

    def test_表格转义竖线不误报(self):
        got = self.scan({'b.md': '| [[政策卡片-甲\\|甲卡]] |\n'})
        self.assertEqual(got, [], '表格里的 \\| 是转义，目标仍是政策卡片-甲')

    def test_模板占位符不误报(self):
        got = self.scan({'t.md': '[[政策链-XXX]] [[页面名]] [[政策卡片-{名}]]\n'})
        self.assertEqual(got, [])

    def test_代码块内不扫描(self):
        got = self.scan({'t.md': '```\n[[示例链接]]\n```\n`[[行内示例]]`\n'})
        self.assertEqual(got, [])

    def test_同一文件多条都报(self):
        got = self.scan({'b.md': '[[甲不存在]] [[乙不存在]]\n'})
        self.assertEqual(len(got), 2)


if __name__ == '__main__':
    unittest.main()
