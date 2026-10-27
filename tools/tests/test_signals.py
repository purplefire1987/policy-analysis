#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信号检查的窗口与分档：坏参数必须抛错，不能静默空跑。

为什么单测：`window_of` 原来在参数坏掉时 print + sys.exit(2)，入口那行就是空白，
调用方会以为「窗口核过了」。现在它抛 ValueError，由 run() 统一转成带摘要的
BAD_INPUT——这条路径不测，很容易退回去。
另测断档四档的边界值，因为「>30 天=长期空白」是台账点名的依据。
"""
import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import signals                  # noqa: E402


class TestParseWeek(unittest.TestCase):
    def test_合法周号(self):
        mon, sun = signals.parse_week('2026-W43')
        self.assertEqual(mon, datetime.date(2026, 10, 19))
        self.assertEqual(sun, datetime.date(2026, 10, 25))

    def test_前后空白可容忍(self):
        self.assertIsNotNone(signals.parse_week(' 2026-W43 '))

    def test_格式不对返回None(self):
        for bad in ('W43', '2026-43', '2026W43', '', '2026-Wxx'):
            with self.subTest(bad=bad):
                self.assertIsNone(signals.parse_week(bad))

    def test_周号越界返回None(self):
        """W99 格式对但周不存在——不能当成合法周去算日期。"""
        self.assertIsNone(signals.parse_week('2026-W99'))
        self.assertIsNone(signals.parse_week('2026-W00'))


class TestWindowOf(unittest.TestCase):
    def test_不带窗口参数返回None(self):
        self.assertIsNone(signals.window_of(SimpleNamespace(week=None, since=None)))

    def test_坏周号抛ValueError(self):
        with self.assertRaises(ValueError):
            signals.window_of(SimpleNamespace(week='W43', since=None))

    def test_坏日期抛ValueError(self):
        with self.assertRaises(ValueError):
            signals.window_of(SimpleNamespace(week=None, since='昨天'))

    def test_带时间的日期允许(self):
        """提示词里传「窗口起点」会写成 `2026-10-24 09:00`，取日期部分即可。"""
        start, _end, label = signals.window_of(
            SimpleNamespace(week=None, since='2026-10-24 09:00'))
        self.assertEqual(start, datetime.date(2026, 10, 24))
        self.assertIn('2026-10-24', label)


class Test断档分档(unittest.TestCase):
    def test_边界值归属(self):
        cases = [(0, '≤7 天'), (7, '≤7 天'), (8, '8~14 天'), (14, '8~14 天'),
                 (15, '15~30 天'), (30, '15~30 天'), (31, '>30 天或空')]
        for gap, want in cases:
            with self.subTest(gap=gap):
                self.assertEqual(signals._gap_tag(gap)[0], want)

    def test_长期空白单独标注(self):
        """>30 天要能被点名成「长期空白页」，不能和半月级混在一起。"""
        self.assertIn('空白', signals._gap_tag(45)[1])


class Test信号字段判据(unittest.TestCase):
    """「政策走向」是枚举、「关联政策」是必填——两者都要能被抓出来。

    为什么这里必须真有测试：2026-10-27 把八字段并为七字段时，改的是**判据**本身。
    如果只验证「119 条全过」，那么判据写坏了（比如永远找不到字段、永远返回空列表）
    也会显示 100% —— 那是「判据静默失效」，比数据缺失更难发现。
    所以每条都构造**故意写错的样本**，确认它报得出来。
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.old = signals.SIGNAL_DIR
        signals.SIGNAL_DIR = self.dir

    def tearDown(self):
        signals.SIGNAL_DIR = self.old
        self.tmp.cleanup()

    def _page(self, assoc='政策甲（2026-01-01）｜一手源 [原文](http://x)｜链：[[政策链-甲]]',
              direction='继续——原话未变'):
        body = ('# 政策信号汇总：测试\n\n## 新闻列表（按时间倒序）\n\n'
                '### 2026-10-20 · 某场发布会\n\n'
                '- **信号主题**：一句话\n'
                '- **来源**：[新华社（2026-10-20）](http://x)\n'
                '- **核心信号**：某表态\n'
                '- **变化字眼**：**首次**\n'
                '- **参会/相关方**：某人（某职）\n')
        if assoc is not None:
            body += f'- **关联政策**：{assoc}\n'
        if direction is not None:
            body += f'- **政策走向**：{direction}\n'
        (self.dir / '政策信号-测试.md').write_text(body, encoding='utf-8')
        return signals.load_pages()

    def test_三档取值都合法(self):
        for v in ('继续', '调整', '终结', '**调整**——换了表述'):
            with self.subTest(v=v):
                r = signals.report_all(self._page(direction=v))
                self.assertEqual(r.verdict, signals.Verdict.PASS, r.summary)

    def test_走向写成中性要报错(self):
        r = signals.report_all(self._page(direction='中性——影响有限'))
        self.assertEqual(r.verdict, signals.Verdict.FAIL)
        self.assertIn('走向取值非法', r.summary)
        self.assertTrue(any('只能取' in l for l in r.lines), r.lines)

    def test_关联政策为空要报错(self):
        r = signals.report_all(self._page(assoc=''))
        self.assertEqual(r.verdict, signals.Verdict.FAIL)
        self.assertIn('关联政策为空', r.summary)

    def test_尚无对应政策是合法取值不是空(self):
        """政策空白点价值最高，不能因为没写出政策名就判它空。"""
        r = signals.report_all(self._page(assoc='尚无对应政策（文件未出台）｜链：[[政策链-甲]]'))
        self.assertEqual(r.verdict, signals.Verdict.PASS, r.summary)

    def test_缺字段只降完整率不阻断(self):
        """缺字段是额度问题，慢慢补；取值错是判据失效，当场报。两者不能混。"""
        pages = self._page(assoc=None, direction=None)
        r = signals.report_all(pages)
        self.assertEqual(r.verdict, signals.Verdict.PASS)
        self.assertIn('0/1', r.summary)


if __name__ == '__main__':
    unittest.main()
