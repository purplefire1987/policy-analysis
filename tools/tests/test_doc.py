#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入库转换：任何格式 → TXT，且失败时要说清**为什么**。

为什么单测：入库的终点只有 TXT 一种格式（2026-10-28），所以这里失手等于
「政策没进库」。而失手之后最要紧的不是重试，是知道该做什么——
扫描件要去 OCR、缺库要去装、文件坏了要重下，三种处置完全不同。

`to_text` 因此返回 `(文本, 原因)` 而不是空串：**空串是把四种情况压成一句废话。**
"""
import sys
import unittest
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import doc      # noqa: E402

BASE = Path(__file__).resolve().parents[2] / '.cache' / 'test-doc'


def workdir():
    """每次一个独立目录，不清理。

    不用 tempfile：本机沙箱拦删除时 `gettempdir()` 会抛，
    连「建了能删」这一步都过不去，测试于是报环境错而不是代码错。
    """
    d = BASE / uuid.uuid4().hex[:10]
    d.mkdir(parents=True, exist_ok=True)
    return d


class Test纯文本(unittest.TestCase):
    """`.txt` 本来就是 TXT——此前转换表里没有它，于是被写成「未能转为文本」。"""

    def setUp(self):
        self.d = workdir()

    def test_utf8直接读(self):
        p = self.d / 'a.txt'
        p.write_text('政策清单\n第一条', encoding='utf-8')
        text, why = doc.to_text(p)
        self.assertEqual(why, '')
        self.assertIn('第一条', text)

    def test_gbk也能读(self):
        """部委的清单附件常是 GBK，只试 utf-8 会读成空。"""
        p = self.d / 'b.txt'
        p.write_bytes('出口管制清单'.encode('gb18030'))
        text, why = doc.to_text(p)
        self.assertEqual(why, '')
        self.assertIn('出口管制', text)

    def test_md也算纯文本(self):
        p = self.d / 'c.md'
        p.write_text('# 标题', encoding='utf-8')
        self.assertEqual(doc.to_text(p), ('# 标题', ''))


class Test失败要说清原因(unittest.TestCase):
    def setUp(self):
        self.d = workdir()

    def test_没有扩展名(self):
        p = self.d / 'noext'
        p.write_bytes(b'x')
        text, why = doc.to_text(p)
        self.assertEqual(text, '')
        self.assertIn('扩展名', why)

    def test_不认识的格式指出扩展名(self):
        p = self.d / 'a.xyz'
        p.write_bytes(b'x')
        text, why = doc.to_text(p)
        self.assertEqual(text, '')
        self.assertIn('xyz', why)

    def test_坏docx说打不开(self):
        """原因不能是「转换失败」——那和「缺库」「扫描件」分不开。"""
        p = self.d / 'bad.docx'
        p.write_bytes(b'not a zip')
        text, why = doc.to_text(p)
        self.assertEqual(text, '')
        self.assertIn('打不开', why)

    def test_空docx说没有文字(self):
        p = self.d / 'empty.docx'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('word/document.xml',
                       '<w:document><w:body><w:p><w:pPr/></w:p></w:body></w:document>')
        text, why = doc.to_text(p)
        self.assertEqual(text, '')
        self.assertIn('没有文字', why)

    def test_成功时原因是空串(self):
        """调用方靠「原因为空」判断成功，所以成功必须回空串而不是 None。"""
        p = self.d / 'ok.txt'
        p.write_text('正文', encoding='utf-8')
        self.assertEqual(doc.to_text(p)[1], '')


class Test返回值契约(unittest.TestCase):
    def test_永远返回二元组(self):
        p = workdir() / 'x.unknownext'
        p.write_bytes(b'')
        got = doc.to_text(p)
        self.assertIsInstance(got, tuple)
        self.assertEqual(len(got), 2)


class Test表格与网页(unittest.TestCase):
    """清单类附件多半是表格——**摊成散文就没法核**。

    阈值、编码、名单这类「边界」信息，价值全在「哪一列对应哪一行」，
    所以表格必须还原成 `| 单元格 | 单元格 |`，不能把行号列号都丢掉。
    """

    def setUp(self):
        self.d = workdir()

    def _xlsx(self, sheet, shared=''):
        p = self.d / 'list.xlsx'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('xl/sharedStrings.xml', f'<sst>{shared}</sst>')
            z.writestr('xl/worksheets/sheet1.xml', f'<worksheet>{sheet}</worksheet>')
        return p

    def test_xlsx共享字符串与数值(self):
        p = self._xlsx(
            '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
            '<row><c><v>2026</v></c><c t="s"><v>2</v></c></row>',
            '<si><t>品类</t></si><si><t>限额</t></si><si><t>稀土</t></si>')
        text, why = doc.to_text(p)
        self.assertEqual(why, '')
        self.assertIn('| 品类 | 限额 |', text)
        self.assertIn('| 2026 | 稀土 |', text)

    def test_富文本不能只取第一个t(self):
        """共享字符串是富文本时会被拆成多个 `<t>`，只取第一个就丢半句。"""
        p = self._xlsx('<row><c t="s"><v>0</v></c></row>',
                       '<si><t>稀土</t><t>出口管制</t></si>')
        self.assertIn('稀土出口管制', doc.to_text(p)[0])

    def test_空xlsx说没有值(self):
        p = self._xlsx('<row></row>')
        text, why = doc.to_text(p)
        self.assertEqual(text, '')
        self.assertIn('没有值', why)

    def test_html表格与实体(self):
        p = self.d / 'a.html'
        p.write_text('<html><body><script>var x=1</script>'
                     '<p>名单 &amp; 条件</p>'
                     '<table><tr><td>甲</td><td>乙</td></tr></table>'
                     '</body></html>', encoding='utf-8')
        text, why = doc.to_text(p)
        self.assertEqual(why, '')
        self.assertIn('名单 & 条件', text)
        self.assertIn('| 甲 | 乙 |', text)
        self.assertNotIn('var x', text)      # 脚本不是正文

    def test_xls另存才算得清(self):
        """`.xls` 是 BIFF 二进制，标准库解不了——要说「没有转换器」，
        而不是让它看起来像「转换失败」，那样人会反复重试同一个文件。"""
        self.assertTrue(doc.unsupported('xls'))
        self.assertFalse(doc.unsupported('xlsx'))


if __name__ == '__main__':
    unittest.main()
