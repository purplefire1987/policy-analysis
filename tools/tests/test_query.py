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

NOTE_A = """---
类型: 灵感
标题: 房车营地是个新基建切口
日期: 2026-10-25
---

正文：营地、驿站、服务区水电补给，都算延伸。
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
        self.notes = root / '笔记'
        for d in (self.cards, self.sigs, self.chains, self.notes):
            d.mkdir()
        (self.cards / '政策卡片-金融.md').write_text(CARD_A, encoding='utf-8')
        (self.sigs / '政策信号-金融.md').write_text(SIGNAL_A, encoding='utf-8')
        (self.chains / '政策链-金融强国.md').write_text(CHAIN_A, encoding='utf-8')
        (self.notes / '房车营地.md').write_text(NOTE_A, encoding='utf-8')
        self._old = (query.CARD_DIR, query.SIGNAL_DIR, query.CHAIN_DIR, query.NOTES_DIR)
        query.CARD_DIR, query.SIGNAL_DIR = self.cards, self.sigs
        query.CHAIN_DIR, query.NOTES_DIR = self.chains, self.notes

    def tearDown(self):
        query.CARD_DIR, query.SIGNAL_DIR, query.CHAIN_DIR, query.NOTES_DIR = self._old
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

    def test_笔记默认不进检索(self):
        _, out = self.call('房车')
        self.assertIn('0 处', out)

    def test_加notes才查人的笔记且标出类型(self):
        code, out = self.call('房车', '--notes')
        self.assertEqual(code, 0)
        self.assertIn('【笔记】', out)
        self.assertIn('房车营地是个新基建切口', out)

    def test_没有条件时打帮助并说明无结论(self):
        code, out = self.call()
        self.assertEqual(code, 0)
        self.assertIn('未给检索条件', out)


if __name__ == '__main__':
    unittest.main()


class Test关键词兜底(unittest.TestCase):
    """`query` 是关键词字段的第一个消费端：读者用的词常与政策用的词不一样。

    查「旅居车」不命中，因为库里写「房车」——卡片关键词正是存这种别名的地方。
    纯函数，不碰文件，所以直接把映射传进去。
    """

    MAP = {'房车与旅居': ['旅居车', '房车'], '养老': ['银发经济', '养老服务']}

    def test_别名命中(self):
        got = query.kw_cards('旅居车', self.MAP)
        self.assertEqual([c for c, _k in got], ['房车与旅居'])

    def test_上位词包含即命中(self):
        got = query.kw_cards('银发', self.MAP)
        self.assertIn('养老', [c for c, _k in got])

    def test_单字不猜(self):
        self.assertEqual(query.kw_cards('车', self.MAP), [],
                         '一个字几乎人人命中，宁可不给')
