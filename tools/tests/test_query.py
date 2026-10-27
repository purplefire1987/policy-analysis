#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`run.py query` 的单测。

这一项的判据只有一条：**给出的行号真能读到那句话**。行号错一格比查不到更糟——
读者按它去 Read，会读到相邻小节，然后以为库里就是这么写的。

跑法：python3 -m unittest discover -s tools/tests   或   python3 -m pytest -q tools/tests
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import query  # noqa: E402

CARD_A = """# 政策卡片：金融

## 政策演进（按时间倒序，最新第一）

### 2026-10-20 · 甲号文件

- **发文机关**：中国人民银行
- **核心要点**：设立互换便利。
- **政策原文**：[原文](https://example.gov.cn/a.htm)

### 2026-09-01 · 乙号文件

- **发文机关**：财政部
- **核心要点**：发行特别国债。
"""

SIGNAL_A = """# 政策信号汇总：金融

## 新闻列表（按时间倒序）

### 2026-10-22 · 央行发布会

- **信号主题**：提到互换便利的后续安排
"""

CHAIN_A = """# 政策链：金融强国

## 关联卡片

- [[政策卡片-金融]]
"""


class TestQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cards, self.sigs, self.chains = root / '卡片', root / '信号', root / '链'
        for d in (self.cards, self.sigs, self.chains):
            d.mkdir()
        (self.cards / '政策卡片-金融.md').write_text(CARD_A, encoding='utf-8')
        (self.sigs / '政策信号-金融.md').write_text(SIGNAL_A, encoding='utf-8')
        (self.chains / '政策链-金融强国.md').write_text(CHAIN_A, encoding='utf-8')
        self._old = (query.CARD_DIR, query.SIGNAL_DIR, query.CHAIN_DIR)
        query.CARD_DIR, query.SIGNAL_DIR, query.CHAIN_DIR = self.cards, self.sigs, self.chains

    def tearDown(self):
        query.CARD_DIR, query.SIGNAL_DIR, query.CHAIN_DIR = self._old
        self.tmp.cleanup()

    def call(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = query.run(list(argv))
        return code, buf.getvalue()

    def test_关键词命中行号能读到原句(self):
        code, out = self.call('财政部')
        self.assertEqual(code, 0)
        self.assertIn('2026-09-01 · 乙号文件', out)
        # 行号必须真落在那句话上——这是本动作唯一不能错的判据
        hit = [l for l in out.split('\n') if '命中行' in l][0]
        lineno = int(hit.split('命中行 ')[1].split(',')[0])
        line = (self.cards / '政策卡片-金融.md').read_text(encoding='utf-8').split('\n')[lineno - 1]
        self.assertIn('财政部', line)

    def test_标题行本身不算命中(self):
        _, out = self.call('乙号文件')
        self.assertIn('0 处', out)

    def test_链过滤只出该链的卡且不含信号(self):
        _, out = self.call('--chain', '金融强国')
        self.assertIn('2026-10-20 · 甲号文件', out)
        self.assertIn('2026-09-01 · 乙号文件', out)
        self.assertNotIn('【信号】', out)

    def test_时间窗过滤(self):
        _, out = self.call('--since', '2026-10-01')
        self.assertIn('甲号文件', out)
        self.assertNotIn('乙号文件', out)

    def test_不存在的链明说而不是静默(self):
        _, out = self.call('--chain', '不存在的链')
        self.assertIn('没有这条链', out)

    def test_查不到要明说0处(self):
        _, out = self.call('绝不出现的词')
        self.assertIn('0 处', out)

    def test_没有条件时打帮助并说明无结论(self):
        code, out = self.call()
        self.assertEqual(code, 0)
        self.assertIn('未给检索条件', out)


if __name__ == '__main__':
    unittest.main()
