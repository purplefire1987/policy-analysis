#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包入口形态：链接？副本？链错地方？

为什么必须用测试钉住：这条链路的失败模式是**看起来正常**——实体副本能被 import、
指向别处的链接也能被 import，`ls` 一下甚至更"像"样。所以形态只能由代码判。
取代「副本＋哈希清单」之后，判据从「内容是否一致」变成「形态是否正确」：
内容一致是抄得及时，形态正确才是没有第二份。
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # noqa: E402  让 tools/ 可导入

from pkb.core import expert, TOOLS          # noqa: E402
from pkb.actions import link                # noqa: E402


def fake_tree(root):
    """一棵最小的源树：run.py 存在即可（形态判定不看内容）。"""
    (root / 'pkb' / 'core').mkdir(parents=True, exist_ok=True)
    (root / 'run.py').write_text('print("可用动作")\n', encoding='utf-8')
    (root / 'pkb' / 'core' / 'a.py').write_text('A = 1\n', encoding='utf-8')
    return root


def quiet(fn, *a, **kw):
    """吞掉打印，返回 (结果, 文本)。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


class TestState(unittest.TestCase):
    def test_不存在(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            self.assertEqual(expert.state(dest, target=TOOLS), expert.MISSING)

    def test_实体目录是副本(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.mkdir()
            self.assertEqual(expert.state(dest, target=TOOLS), expert.COPY)

    def test_指向本体是链接(self):
        with tempfile.TemporaryDirectory() as d:
            src = fake_tree(Path(d) / 'tools')
            dest = Path(d) / 'scripts'
            dest.symlink_to(src)
            self.assertEqual(expert.state(dest, target=src), expert.LINK)
            self.assertEqual(Path(expert.link_target(dest)), src.resolve())

    def test_指向别处是链错(self):
        """指向别处比副本更危险：它长得像正确答案。"""
        with tempfile.TemporaryDirectory() as d:
            other = fake_tree(Path(d) / 'other')
            dest = Path(d) / 'scripts'
            dest.symlink_to(other)
            self.assertEqual(expert.state(dest, target=TOOLS), expert.ALIEN)

    def test_悬空链接也是链错(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.symlink_to(Path(d) / 'nowhere')
            self.assertEqual(expert.state(dest, target=TOOLS), expert.ALIEN)


class TestDrift(unittest.TestCase):
    def _copy(self, d):
        src = fake_tree(Path(d) / 'tools')
        dest = Path(d) / 'scripts'
        dest.mkdir()
        (dest / 'run.py').write_text('print("可用动作")\n', encoding='utf-8')
        (dest / 'pkb' / 'core').mkdir(parents=True)
        (dest / 'pkb' / 'core' / 'a.py').write_text('A = 2\n', encoding='utf-8')  # 改过
        (dest / 'leftover.py').write_text('X = 1\n', encoding='utf-8')           # 包内多
        return src, dest

    def test_三类差异都能报出来(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = self._copy(d)
            kinds = dict(expert.drift(dest, src=src))
            self.assertEqual(kinds.get('pkb/core/a.py'), '改过')
            self.assertEqual(kinds.get('leftover.py'), '包内多')
            self.assertEqual(kinds.get('pkb/core/missing.py'), None)  # 没有这个文件就不该编

    def test_缺文件也算差异(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = self._copy(d)
            (src / 'pkb' / 'core' / 'b.py').write_text('B = 1\n', encoding='utf-8')
            self.assertEqual(dict(expert.drift(dest, src=src)).get('pkb/core/b.py'), '包内缺')

    def test_不存在时返回空(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(expert.drift(Path(d) / 'nope', src=TOOLS), [])


class TestEnsure(unittest.TestCase):
    def test_副本有改动时拒绝删除(self):
        """删除别人的改动是「自动编造」的近亲——必须显式 --force。"""
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.mkdir()
            (dest / 'run.py').write_text('print("改过的那份")\n', encoding='utf-8')
            code, out = quiet(link._ensure, dest, False)
            self.assertEqual(code, 1)
            self.assertIn('--force', out)
            self.assertTrue((dest / 'run.py').exists(), '拒绝时必须原样留着')

    def test_force_后变成链接且入口能跑(self):
        """链接建成不算完：真跑一次 <链接>/run.py，证明它确实能启动。"""
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.mkdir()
            (dest / 'junk.py').write_text('X = 1\n', encoding='utf-8')
            code, out = quiet(link._ensure, dest, True)
            self.assertEqual(code, 0, out)
            self.assertTrue(dest.is_symlink())
            self.assertEqual(dest.resolve(), TOOLS.resolve())
            self.assertIn('入口自检', out)

    def test_已是链接时幂等(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.symlink_to(TOOLS)
            code, out = quiet(link._ensure, dest, False)
            self.assertEqual(code, 0)
            self.assertIn('无需改动', out)

    def test_check_模式不写盘(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'scripts'
            dest.mkdir()
            code, out = quiet(link._report, dest)
            self.assertEqual(code, 1)
            self.assertIn('实体副本', out)
            self.assertTrue(dest.is_dir())

    def test_check_模式对缺失返回1(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = quiet(link._report, Path(d) / 'scripts')
            self.assertEqual(code, 1)
            self.assertIn('不存在', out)


if __name__ == '__main__':
    unittest.main()
