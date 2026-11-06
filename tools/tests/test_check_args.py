#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`check --only` 的范围选择：多个片段要能一起选，有一个错就别跑。

为什么单测这条：`--only` 决定「这次结论覆盖哪些范围」，选错了比跑挂了更危险——
挂了你至少知道没查到，而少跑几项照样 exit 0，报告里那句「已检查」就是假的。
所以这里钉两件事：多选按注册顺序、有一个片段匹配不到就整体拒绝。
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions.check import parse_args, pick_specs      # noqa: E402
from pkb.checks import REGISTRY                          # noqa: E402


def names(specs):
    return [s.name for s in specs]


class TestOnly(unittest.TestCase):
    def test_不给only就是全部(self):
        self.assertEqual(len(pick_specs(None)), len(REGISTRY))

    def test_单个片段与旧行为一致(self):
        self.assertEqual(names(pick_specs('docs')), ['check_docs.py'])

    def test_逗号分隔多选(self):
        got = names(pick_specs('signals,docs'))
        self.assertEqual(got, ['check_docs.py', 'check_signals.py'],
                         '顺序按注册表，不按参数顺序——报告编号才稳定')

    def test_空格也能分隔(self):
        self.assertEqual(names(pick_specs('docs health')),
                         ['check_docs.py', 'check_health.py'])

    def test_有一个匹配不到就整体不跑(self):
        """部分匹配照跑，会让人以为核过的范围比实际大。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertIsNone(pick_specs('docs,nosuch'))
        self.assertIn('nosuch', buf.getvalue())

    def test_重复片段不重复跑(self):
        self.assertEqual(names(pick_specs('docs,docs')), ['check_docs.py'])

    def test_parse_only与full互不干扰(self):
        only, full, rest = parse_args(['--only', 'docs,signals', '--full', '--since', '2026-11-01'])
        self.assertEqual((only, full, rest), ('docs,signals', True, ['--since', '2026-11-01']))


if __name__ == '__main__':
    unittest.main()
