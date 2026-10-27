#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trace 的判据：给一条政策，四类旁证都要真的连出来，且不替人下结论。

核心断言只有一句：**输出里每一处位置都能回读到原文**。行号错了、卡名错了、
存档漏了，读者按它去翻就会翻空——那比不给更糟。
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import trace  # noqa: E402

CARD = """---
类型: 产业卡
名称: 消费与商贸
---

## 政策列表

### 2026-09-13 · 关于促进房车消费的若干措施（国办函〔2026〕82号）

- 要点：放宽房车报废年限，部署营地建设。

### 2026-08-01 · 另一条无关政策

- 要点：与本条无关。
"""

CHAIN = """# 政策链-促消费

## 关联卡片

- [[政策卡片-消费与商贸]]
- [[政策卡片-文旅体育]]
"""

SIGNAL = """# 政策信号-改善民生

### 2026-09-20 · 房车营地建设提速

- **关联政策**：关于促进房车消费的若干措施（2026-09-13）｜文号 国办函〔2026〕82号
"""

ARTICLE = """---
类型: 一手存档
政策日期: 2026-09-13
文号: 国办函〔2026〕82号
---

正文。
"""


class TestTrace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for name in ('card', 'chain', 'signal', 'article'):
            (root / name).mkdir()
        (root / 'card' / '政策卡片-消费与商贸.md').write_text(CARD, encoding='utf-8')
        (root / 'chain' / '政策链-促消费.md').write_text(CHAIN, encoding='utf-8')
        (root / 'signal' / '政策信号-改善民生.md').write_text(SIGNAL, encoding='utf-8')
        (root / 'article' / '2026-09-13_国办函82号_促进房车消费.md').write_text(
            ARTICLE, encoding='utf-8')
        self.root = root
        self._old = (trace.CARD_DIR, trace.CHAIN_DIR, trace.SIGNAL_DIR, trace.ARTICLE_DIR)
        trace.CARD_DIR, trace.CHAIN_DIR = root / 'card', root / 'chain'
        trace.SIGNAL_DIR, trace.ARTICLE_DIR = root / 'signal', root / 'article'

    def tearDown(self):
        (trace.CARD_DIR, trace.CHAIN_DIR, trace.SIGNAL_DIR, trace.ARTICLE_DIR) = self._old
        self.tmp.cleanup()

    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = trace.run(argv)
        return code, buf.getvalue()

    def test_按标题片段能牵出四类旁证(self):
        code, out = self._run(['促进房车消费'])
        self.assertEqual(code, 0)
        self.assertIn('卡：消费与商贸', out)
        self.assertIn('链：促消费', out)
        self.assertIn('信号：1 条', out)
        self.assertIn('raw/articles/2026-09-13', out)

    def test_按文号也能找到同一条政策(self):
        code, out = self._run(['国办函〔2026〕82号'])
        self.assertEqual(code, 0)
        self.assertIn('关于促进房车消费的若干措施', out)

    def test_只连不判定_不下结论(self):
        _code, out = self._run(['促进房车消费'])
        for word in ('影响：', '建议', '判断为'):
            self.assertNotIn(word, out)

    def test_查不到要给最相近而不是静默(self):
        code, out = self._run(['充电桩补贴'])
        self.assertEqual(code, 0)
        self.assertIn('没找到', out)
        # 要么给最相近的标题，要么给下一步怎么办——总之不许只留一个空结果
        self.assertTrue('最相近' in out or '换一个词' in out, out)

    def test_行号能回读到标题(self):
        code, out = self._run(['促进房车消费'])
        self.assertEqual(code, 0)
        line = [l for l in out.splitlines() if '政策卡片-消费与商贸.md:' in l][0]
        start = int(line.split(':')[1].split('-')[0])
        text = (self.root / 'card' / '政策卡片-消费与商贸.md').read_text(encoding='utf-8')
        self.assertIn('关于促进房车消费的若干措施', text.split('\n')[start - 1])


if __name__ == '__main__':
    unittest.main()
