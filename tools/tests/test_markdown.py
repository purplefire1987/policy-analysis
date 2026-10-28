#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出库方向的判据：Markdown → HTML 只认本库真会写的结构。

为什么单测它：转换器出错的表现是「文件生成成功、内容悄悄丢了」——表格变成一串
竖线、双链没剥、列表吃掉了缩进。这类错不会报异常，只会让人交出错的稿子。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import markdown as M          # noqa: E402


def html(text):
    return M.md_to_html(text)


class Test块结构(unittest.TestCase):
    def test_表格保留成table(self):
        got = html('| 甲 | 乙 |\n|---|---|\n| 1 | 2 |\n')
        self.assertIn('<table>', got)
        self.assertIn('<th>甲</th>', got)
        self.assertIn('<td>2</td>', got)

    def test_表头分隔行不被当成数据(self):
        got = html('| 甲 | 乙 |\n|---|---|\n| 1 | 2 |\n')
        self.assertNotIn('<td>---</td>', got)
        self.assertEqual(got.count('<tr>'), 2)

    def test_无序与有序列表(self):
        self.assertIn('<ul><li>甲</li><li>乙</li></ul>', html('- 甲\n- 乙\n'))
        self.assertIn('<ol><li>甲</li></ol>', html('1. 甲\n'))

    def test_引用块与callout(self):
        self.assertIn('class="callout"', html('> [!info] 基本信息\n> - 甲：乙\n'))
        self.assertIn('<blockquote', html('> 普通引用\n'))

    def test_代码块内容被转义(self):
        got = html('```\n<b>x</b>\n```\n')
        self.assertIn('&lt;b&gt;', got)
        self.assertNotIn('<b>x</b>', got)


class Test行内(unittest.TestCase):
    def test_双链带上别名取别名(self):
        self.assertIn('原文存档', html('见 [[2026-01-01_甲部_某文件|原文存档]]。'))

    def test_双链无别名取目标名(self):
        self.assertIn('政策链-能源', html('见 [[政策链-能源]]。'))
        self.assertNotIn('[[', html('见 [[政策链-能源]]。'))

    def test_粗体与行内码(self):
        got = html('**要点** 与 `code`\n')
        self.assertIn('<strong>要点</strong>', got)
        self.assertIn('<code>code</code>', got)

    def test_HTML标签被转义(self):
        self.assertIn('&lt;script&gt;', html('a <script> b\n'))


class Test整篇(unittest.TestCase):
    def test_frontmatter不进正文(self):
        got = M.md_to_html('---\n名称: 能源\n---\n\n正文。\n')
        self.assertNotIn('名称: 能源', got)
        self.assertIn('能源', got)          # 只出现在页首来源行与 title
        self.assertIn('正文。', got)

    def test_自带版式与外链为零(self):
        got = html('正文。\n')
        self.assertIn('<style>', got)
        self.assertNotIn('<link', got, '交出的是单文件，不能有外链样式')


if __name__ == '__main__':
    unittest.main()
