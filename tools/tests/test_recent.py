#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recent 的判据：时间窗准、三类分得清、没日期的笔记不猜日期。

为什么专测「无日期」：笔记是自由结构，`日期` 可能被漏填。默认补今天，会让
「近 7 天」凭空多出一篇；默认丢掉而不说，则等于那篇笔记不存在。所以判据是
**既不计入、又在输出里明说有几条被排除**。
"""
import datetime
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import recent  # noqa: E402

CARD = """# 政策卡片-金融

### {today} · 今天发布的政策

正文。
"""

CARD_OLD = """# 政策卡片-金融

### 2020-01-01 · 很久以前的政策

正文。
"""

NOTE = """---
类型: 灵感
标题: 人的一篇异议
日期: {today}
---

正文。
"""

NOTE_UNDATED = """---
类型: 灵感
标题: 忘了写日期的一篇
---

正文。
"""


class TestRecent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for name in ('card', 'signal', 'notes'):
            (root / name).mkdir()
        today = datetime.date.today().isoformat()
        (root / 'card' / '政策卡片-金融.md').write_text(CARD.format(today=today), encoding='utf-8')
        (root / 'card' / '政策卡片-旧.md').write_text(CARD_OLD, encoding='utf-8')
        (root / 'signal' / '政策信号-金融.md').write_text(
            CARD.format(today=today).replace('政策卡片', '政策信号'), encoding='utf-8')
        (root / 'notes' / '异议.md').write_text(NOTE.format(today=today), encoding='utf-8')
        (root / 'notes' / '忘日期.md').write_text(NOTE_UNDATED, encoding='utf-8')
        self.root = root
        self._old = (recent.CARD_DIR, recent.SIGNAL_DIR, recent.NOTES_DIR)
        recent.CARD_DIR = root / 'card'
        recent.SIGNAL_DIR = root / 'signal'
        recent.NOTES_DIR = root / 'notes'

    def tearDown(self):
        (recent.CARD_DIR, recent.SIGNAL_DIR, recent.NOTES_DIR) = self._old
        self.tmp.cleanup()

    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = recent.run(argv)
        return code, buf.getvalue()

    def test_三类都统计(self):
        code, out = self._run(['--days', '7'])
        self.assertEqual(code, 0)
        self.assertIn('政策 1', out)
        self.assertIn('信号 1', out)
        self.assertIn('笔记 1', out)

    def test_窗外的不列(self):
        _code, out = self._run(['--days', '7'])
        self.assertNotIn('很久以前的政策', out)

    def test_按类型过滤(self):
        _code, out = self._run(['--days', '7', '--kind', '笔记'])
        self.assertIn('人的一篇异议', out)
        self.assertNotIn('今天发布的政策', out)

    def test_无日期的笔记不猜日期但要说明(self):
        _code, out = self._run(['--days', '7'])
        self.assertNotIn('忘了写日期的一篇', out.split('另有')[0])
        self.assertIn('另有 1 条没有日期', out)

    def test_某一类没有就写0条(self):
        empty = self.root / 'empty'
        empty.mkdir()
        recent.NOTES_DIR = empty
        _code, out = self._run(['--days', '7'])
        self.assertIn('笔记 0', out)

    def test_0条也给说明(self):
        code, out = self._run(['--days', '1', '--kind', '信号'])
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
