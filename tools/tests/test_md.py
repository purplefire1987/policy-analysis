#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.md / core.fm 的解析件单测。

这一层最容易「改一处、坏一片」而没人发现：小节切块与 frontmatter 解析撑着
六个检查项，全靠 run.py check 的退出码兜底。这里把口径固定下来。

跑法：python3 -m unittest discover -s tools/tests   或   python3 -m pytest -q tools/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import (extract_sections, table_rows, parse_date, iso_week,  # noqa: E402
                      span, parse_fm, set_fm_field, md_section_lines)


class TestSections(unittest.TestCase):
    def test_正常小节按日期标题切块(self):
        body = '## 政策演进（按时间倒序）\n### 2026-10-24 · 甲政策\n要点 A\n### 2026-10-20 · 乙政策\n要点 B'
        secs, bad = extract_sections(body)
        self.assertEqual([(d, t) for d, t, _, _ in secs],
                         [('2026-10-24', '甲政策'), ('2026-10-20', '乙政策')])
        self.assertEqual(bad, [])
        self.assertIn('要点 A', secs[0][2])

    def test_标题缺日期进入bad而不是被吞掉(self):
        body = '### 2026-10-24 · 甲\nx\n### 没有日期的小节\ny'
        secs, bad = extract_sections(body)
        self.assertEqual(len(secs), 1)
        self.assertEqual(len(bad), 1)
        self.assertIn('没有日期', bad[0])

    def test_二级标题不算小节(self):
        body = '## 一、本周政策速览表\n| a | b |\n### 2026-10-24 · 甲\nx'
        secs, bad = extract_sections(body)
        self.assertEqual(len(secs), 1)
        self.assertEqual(bad, [])


class TestTable(unittest.TestCase):
    def test_跳过表头与分隔行(self):
        lines = ['| 领域 | 政策 |', '|---|---|', '| 金融 | 甲 |', '| 能源 | 乙 |']
        self.assertEqual(table_rows(lines), [['金融', '甲'], ['能源', '乙']])

    def test_分隔行只含短横与冒号时跳过(self):
        self.assertEqual(table_rows(['| --- | :--: |']), [])

    def test_首行被当表头(self):
        self.assertEqual(table_rows(['| 只有一行 |']), [])


class TestDate(unittest.TestCase):
    def test_parse_date_合法与非法(self):
        self.assertEqual(parse_date('2026-10-25').isoformat(), '2026-10-25')
        self.assertIsNone(parse_date('2026/10/25'))
        self.assertIsNone(parse_date(''))
        self.assertIsNone(parse_date(None))

    def test_iso_week(self):
        self.assertEqual(iso_week(parse_date('2026-10-12')), '2026-W42')
        self.assertEqual(iso_week(parse_date('2026-10-18')), '2026-W42')

    def test_span_相同时只写一个(self):
        d = parse_date('2026-10-25')
        self.assertEqual(span(d, d), '2026-10-25')
        self.assertEqual(span('a', 'b'), 'a~b')


class TestFrontmatter(unittest.TestCase):
    def test_行内数组解析成list(self):
        fm, body = parse_fm('---\ntags: [政策, 国际博弈]\n政策数: 3\n---\n正文')
        self.assertEqual(fm['tags'], ['政策', '国际博弈'])
        self.assertEqual(fm['政策数'], '3')      # 数值保持字符串，由调用方转
        self.assertEqual(body, '正文')

    def test_wikilink不被当成数组(self):
        fm, _ = parse_fm('---\n所属政策链: [[政策链-金融]]\n---\n')
        self.assertEqual(fm['所属政策链'], '[[政策链-金融]]')

    def test_多行列表(self):
        fm, _ = parse_fm('---\ntags:\n- 政策\n- 国际博弈\n---\n')
        self.assertEqual(fm['tags'], ['政策', '国际博弈'])

    def test_无frontmatter返回原文(self):
        fm, body = parse_fm('# 标题\n正文')
        self.assertEqual(fm, {})
        self.assertEqual(body, '# 标题\n正文')

    def test_set_fm_field_半角冒号(self):
        # 库里实际用半角；只写全角会让替换静默失效，这条钉子必须留
        out = set_fm_field('---\n政策数: 3\n---\n', '政策数', 4)
        self.assertIn('政策数: 4', out)

    def test_set_fm_field_全角冒号也能改(self):
        out = set_fm_field('---\n政策数：3\n---\n', '政策数', 4)
        self.assertIn('政策数: 4', out)

    def test_md_section_lines按包含匹配(self):
        text = '## 一、总述\na\n## 四、存量补采队列（下节）\nb\n## 五、其它\nc'
        self.assertEqual(md_section_lines(text, '存量补采'), ['b'])


if __name__ == '__main__':
    unittest.main()
