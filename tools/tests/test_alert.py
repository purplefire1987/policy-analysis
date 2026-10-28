#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""告警页：两档分类、页面结构、写盘失败不连带判红、只在全量时写。

为什么单测：告警页的价值全在「该出现的都出现了」。少一条比整页缺失更糟——
人看页面是绿的，就不会再去翻终端。所以分类边界要逐条钉住：
`0 新增` 是「要知道」不是「要处置」，`未回流 0` 不许被当成问题。

**全部打桩，不碰磁盘**：`save` 写不进去必须返回 False 而不是抛异常，
那样体检会因为「告警页没写成」而被判失败，方向就反了（产物不该绊倒判据）。
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import alert, check                  # noqa: E402
from pkb.checks import REGISTRY                       # noqa: E402
from pkb.core import Result, Verdict                  # noqa: E402


def quiet(fn, *a, **kw):
    """吞掉被测函数的打印：这些动物动作本来就是给人看的。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*a, **kw)


class Test分类(unittest.TestCase):
    def test_失败进要处置(self):
        kind, msg = alert.classify('check_x.py', Result(Verdict.FAIL, '坏了', []))
        self.assertEqual(kind, 'hard')
        self.assertIn('坏了', msg)

    def test_没有结论也进要处置(self):
        """BAD_INPUT＝这一项没给结论，不能当成通过。"""
        kind, _m = alert.classify('check_x.py', Result(Verdict.BAD_INPUT, '不适用', []))
        self.assertEqual(kind, 'hard')

    def test_检查自身异常进要处置(self):
        kind, msg = alert.classify('check_x.py', None, 'KeyError: 1')
        self.assertEqual(kind, 'hard')
        self.assertIn('KeyError', msg)

    def test_0新增只是要知道(self):
        """采集 0 新增通常是当天真没政策——判成要处置等于天天告警。"""
        kind, _m = alert.classify('check_health.py',
                                  Result(Verdict.PASS, '采集健康：2026-10-28 已跑但 0 新增', []))
        self.assertEqual(kind, 'soft')

    def test_未回流0不要当成问题(self):
        kind, _m = alert.classify('check_archives.py',
                                  Result(Verdict.PASS, '一手存档 37 份：日期一致 37 · 未回流 0 ✅', []))
        self.assertIsNone(kind, '「未回流 0」是正常值，不该进告警页')

    def test_全绿不进页(self):
        kind, _m = alert.classify('check_x.py', Result(Verdict.PASS, '结构 0 问题 ✅', []))
        self.assertIsNone(kind)


class Test页面(unittest.TestCase):
    def test_两档都在且空档写无(self):
        text = alert.render([], [], '2026-10-28 16:00')
        self.assertIn('## 一、要处置', text)
        self.assertIn('## 二、要知道', text)
        self.assertEqual(text.count('- （无）'), 2)
        self.assertIn('2026-10-28 16:00', text)

    def test_有条目时不写无(self):
        text = alert.render(['甲'], ['乙'], 'ts')
        self.assertEqual(text.count('- （无）'), 0)
        self.assertIn('- 甲', text)
        self.assertIn('- 乙', text)


class Test写盘失败不阻断(unittest.TestCase):
    def test_写不进去返回fail(self):
        with mock.patch.object(alert, 'read', return_value=''), \
                mock.patch.object(alert, 'write', side_effect=OSError('read-only')):
            self.assertEqual(alert.save([], []), 'fail')

    def test_正常时写盘并返回written(self):
        with mock.patch.object(alert, 'read', return_value=''), \
                mock.patch.object(alert, 'write') as w:
            self.assertEqual(alert.save(['甲'], []), 'written')
            self.assertIn('甲', w.call_args[0][1])

    def test_除时间戳外没变就不写(self):
        """幂等：本页每次 check 都会被调一次，无条件写就会每跑一次产一次 diff。"""
        with mock.patch.object(alert, 'read', return_value=''), \
                mock.patch.object(alert, 'write') as w1:
            alert.save(['甲'], [])
            first = w1.call_args[0][1]
        with mock.patch.object(alert, 'read', return_value=first), \
                mock.patch.object(alert, 'write') as w2:
            self.assertEqual(alert.save(['甲'], []), 'same')
            w2.assert_not_called()


class Test只在全量写(unittest.TestCase):
    """`--only` 时结果不全，写出来会把其他问题从页面上抹掉——比不写更坏。"""

    def _run(self, argv, write_mock):
        spec = REGISTRY[0]
        ok = (Result(Verdict.PASS, '过', []), set())
        with mock.patch.object(check, 'write_alert', write_mock), \
                mock.patch.object(check, 'pick_specs', return_value=[spec]), \
                mock.patch.object(check, 'run_one', return_value=ok), \
                mock.patch.object(check, 'run_snapshot'):
            quiet(check.run, argv)

    def test_only时不写(self):
        m = mock.MagicMock()
        self._run(['--only', 'vcs'], m)
        m.assert_not_called()

    def test_全量时写(self):
        m = mock.MagicMock()
        self._run([], m)
        self.assertEqual(m.call_count, 1)

    def test_传进去的是已跑过的结果(self):
        """必须是复用，不是重跑：再跑一遍十项会慢一倍，还可能给出两个结论。"""
        got = []
        m = mock.MagicMock(side_effect=lambda r: got.extend(r))
        self._run([], m)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], REGISTRY[0].name)


if __name__ == '__main__':
    unittest.main()
