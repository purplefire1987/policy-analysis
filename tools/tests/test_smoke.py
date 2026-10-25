#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""契约冒烟测试：每项检查都必须返回带摘要的 Result。

这是 P1 的回归测试。2026-10-25 彩排抓到的两处「有退出码没摘要」——
check_week_coverage 文件不存在时 return 2 走人、check_signals 参数解析失败时
sys.exit(2) 走人——入口那行就是空白，调用方以为「没输出 = 没问题」。
现在 Result.summary 没有默认值，这几条测试保证将来有人加检查时按契约写。

跑法：python3 -m unittest discover -s tools/tests
"""
import contextlib
import ast
import io
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import Result, Verdict          # noqa: E402
from pkb.checks import REGISTRY               # noqa: E402


class TestResultContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 六项检查各跑一次，两条断言共用结果——重复跑一遍要再花十几秒
        cls.results = {spec.name: spec.module.run(['--all'] if spec.needs_all else [])
                       for spec in REGISTRY}

    def test_每项检查都返回Result且摘要非空(self):
        for name, r in self.results.items():
            with self.subTest(check=name):
                self.assertIsInstance(r, Result)
                self.assertIsInstance(r.verdict, Verdict)
                self.assertTrue(r.summary.strip(), f'{name} 的摘要为空')
                self.assertIn(r.code, (0, 1, 2, 3))
                self.assertIsInstance(r.lines, list)

    def test_摘要不超过入口截断长度(self):
        # 入口按 120 字符显示摘要，太长会在「取那一行」时被截掉关键数字
        for name, r in self.results.items():
            with self.subTest(check=name):
                self.assertLessEqual(len(r.summary), 200, f'{name} 摘要过长')

    def test_非法周号是BAD_INPUT且有摘要(self):
        from pkb.checks import weeks
        r = weeks.run(['--week', 'W43'])
        self.assertIs(r.verdict, Verdict.BAD_INPUT)
        self.assertTrue(r.summary.strip())

    def test_非法日期是BAD_INPUT且有摘要(self):
        from pkb.checks import signals
        r = signals.run(['--since', '昨天'])
        self.assertIs(r.verdict, Verdict.BAD_INPUT)
        self.assertTrue(r.summary.strip())

    def test_不给周号也不给all是BAD_INPUT(self):
        from pkb.checks import weeks
        r = weeks.run([])
        self.assertIs(r.verdict, Verdict.BAD_INPUT)


class TestImportPurity(unittest.TestCase):
    def test_导入检查模块不读盘不打印(self):
        """设计规则 4：pkb/**/*.py 导入时不许有副作用。"""
        import importlib
        for name in ('pkb.core', 'pkb.domain', 'pkb.checks.analysis', 'pkb.checks.docs',
                     'pkb.checks.signals', 'pkb.checks.structure', 'pkb.checks.views',
                     'pkb.checks.weeks', 'pkb.actions.check', 'pkb.actions.fix'):
            with self.subTest(module=name):
                importlib.reload(importlib.import_module(name))
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    importlib.reload(importlib.import_module(name))
                self.assertEqual(buf.getvalue(), '', f'{name} 导入时不该打印')


class TestLayering(unittest.TestCase):
    def test_core不依赖上层(self):
        """依赖方向单向：core 不许 import domain/checks/actions。"""
        root = Path(__file__).resolve().parents[1] / 'pkb' / 'core'
        for p in root.glob('*.py'):
            text = p.read_text(encoding='utf-8')
            for bad in ('pkb.domain', 'pkb.checks', 'pkb.actions', 'from ..domain', 'from ..checks'):
                self.assertNotIn(bad, text, f'{p.name} 反向依赖了 {bad}')

    def test_checks不依赖actions(self):
        root = Path(__file__).resolve().parents[1] / 'pkb' / 'checks'
        for p in root.rglob('*.py'):          # rglob：包内子模块同样受约束
            text = p.read_text(encoding='utf-8')
            self.assertNotIn('pkb.actions', text, f'{p.name} 反向依赖了 pkb.actions')

    def test_checks不直接sys_exit(self):
        """checks 只返回 Result；sys.exit 会让「有退出码没摘要」重新长出来。

        判据必须是**真调用**（行首 sys.exit( ），不能是文本包含——
        signals.py 的注释里写着「原来是 print + sys.exit(2)」，按包含判断会误报。
        2026-10-24 check_docs 因为注释里有 --fix 被误编进修复队列，是同一个坑。
        """
        root = Path(__file__).resolve().parents[1] / 'pkb' / 'checks'
        call = re.compile(r'(?m)^\s*sys\.exit\s*\(')
        for p in root.rglob('*.py'):          # rglob：包内子模块同样受约束
            text = p.read_text(encoding='utf-8')
            self.assertIsNone(call.search(text), f'{p.name} 里出现了 sys.exit 调用')


class TestFunctionSize(unittest.TestCase):
    """可维护性门槛：一个函数超过 50 行，通常意味着它缝了两件事以上。

    2026-10-25 拆分前有 13 个函数超标（最长 120 行），拆完是 0 个。
    这条测试把它钉住——加功能时顺手写长，会在这里被拦下。
    """
    LIMIT = 50

    def test_单函数不超过50行(self):
        root = Path(__file__).resolve().parents[1]
        files = [root / 'run.py'] + sorted((root / 'pkb').rglob('*.py'))
        over = []
        for p in files:
            tree = ast.parse(p.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    n = node.end_lineno - node.lineno
                    if n > self.LIMIT:
                        over.append(f'{p.relative_to(root)}:{node.lineno} '
                                    f'{node.name}() {n} 行')
        self.assertEqual(over, [], '超过 %d 行：%s' % (self.LIMIT, '；'.join(over)))


class TestActionRegistry(unittest.TestCase):
    """动作表与目录一一对应：`run.py` 的 ACTIONS ↔ `pkb/actions/*.py`。

    为什么钉住：这张表此前在三个地方各写一遍——run.py、AGENTS 第十节、专家定义，
    外加 `list.py` 里一个手写元组。加/改一个动作要改四处，漏一处不会报错，只会让
    某份清单安静地少一行（`export` 改名 `link` 就属于这种改动）。
    现在只剩两处，且由这条测试对齐；`check_docs.check_actions` 管文档那两份。
    """

    def test_动作模块与ACTIONS同名同数(self):
        import importlib
        import pkgutil
        from pkb import actions as pkg

        mods = {m.name for m in pkgutil.iter_modules(pkg.__path__)
                if not m.name.startswith('_')}
        entry = importlib.import_module('run')
        self.assertEqual(mods, set(entry.ACTIONS),
                         '目录里有而 ACTIONS 没有（或反之）——两处必须同步')

    def test_内部件不暴露为动作(self):
        """下划线开头的内部件不该在 ACTIONS 里（否则用户能直接调半成品）。"""
        import importlib
        from pkb import actions as pkg

        entry = importlib.import_module('run')
        internal = {p.stem for p in Path(pkg.__file__).parent.glob('_*.py')}
        self.assertEqual(internal & set(entry.ACTIONS), set())


if __name__ == '__main__':
    unittest.main()
