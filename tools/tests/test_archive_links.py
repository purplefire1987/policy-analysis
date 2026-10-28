#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存档回流的判据：什么时候补链、什么时候必须放手。

「有存档而卡片没链」是本项要报的；但补链必须只认唯一匹配——猜错会把卡片指向
另一条政策的原文，那比不链更坏（表现为「点进去是另一份文件」）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import archives as A          # noqa: E402

ARC = '2026-10-01_甲部_甲发〔2026〕1号_某政策.md'
LINE = '**发文机关**：甲部 ｜ **文号**：甲发〔2026〕1号 ｜ [政策原文](https://example.gov.cn/a)'


class Test补链(unittest.TestCase):
    def test_有政策原文就追加(self):
        got = A._append_link(LINE + '\n\n正文\n', ARC)
        self.assertIn('[[2026-10-01_甲部_甲发〔2026〕1号_某政策|原文存档]]', got)
        self.assertIn('政策原文](https://example.gov.cn/a)', got)

    def test_没有政策原文就不硬插(self):
        self.assertIsNone(A._append_link('**发文机关**：甲部\n\n正文\n', ARC))

    def test_已链过不重复(self):
        once = A._append_link(LINE + '\n', ARC)
        self.assertIsNone(A._append_link(once, ARC), '幂等：跑两次不该挂两条')


class Test匹配只认唯一(unittest.TestCase):
    def rows(self, *titles):
        return [{'no': '', 'key': A.norm(t), 'title': t} for t in titles]

    def test_多候选放弃(self):
        """标题互相包含且都命中时不能挑一个——那是猜。"""
        arc = {'no': '', 'title': '关于促进养老服务业发展的若干意见'}
        idx = self.rows('关于促进养老服务业发展的若干意见',
                        '关于促进养老服务业发展的若干意见（试行）')
        self.assertIsNone(A.match(arc, idx))

    def test_文号全等优先于标题(self):
        arc = {'no': A.norm('甲发〔2026〕1号'), 'title': '别的标题'}
        idx = [{'no': A.norm('甲发〔2026〕1号'), 'key': '甲', 'title': '甲'},
               {'no': A.norm('甲发〔2026〕2号'), 'key': '乙', 'title': '乙'}]
        self.assertEqual(A.match(arc, idx)['title'], '甲')


if __name__ == '__main__':
    unittest.main()
