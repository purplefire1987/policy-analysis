#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一手源抓取：切小节、抽正文、认附件、分级、幂等。

这几条都是**踩过坑才有的判据**，不是为覆盖率写的：
* 切小节切错，链接会串到上一条政策头上，存档写着 A 的标题、内容是 B 的原文；
* 编码判错，部委站整页乱码，而乱码不报错，看起来只是「没有正文」；
* 附件扩展名从路径取不到（商务部是 `?fileName=`），于是「附件转文本」永远跳过；
* 不幂等，每天跑一遍就多一份副本——`raw/` 是要被引用的一手区，重影比缺失更难查。
"""
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import fetch as fetch_mod          # noqa: E402
from pkb.core import web                            # noqa: E402
from pkb.domain import sources                      # noqa: E402

CARD = '''## 政策演进（按时间倒序，最新第一）

### 2026-10-16 · 城镇供热"温暖工程"三年行动方案
**发文机关**：住房城乡建设部办公厅 ｜ **文号**：建办城函〔2026〕239号 ｜ [政策原文](https://www.mohurd.gov.cn/a.htm)
- **生效日期**：2026-10-16
**核心要点**（3~5 条）
- 到 2028 年完成改造

### 2026-10-09 · 对稀土相关物项实施出口管制
**发文机关**：商务部 ｜ **文号**：公告2026年第61号 ｜ 政策原文（待补）
- **生效日期**：2026-10-09
'''

HTML = ('<html><head><meta charset="utf-8"><title>某通知</title></head><body>'
        '<div id="nav">首页 政策 公开 服务 互动 数据 专题</div>'
        '<div id="UCAP-CONTENT"><p>' + '这是一段正文，用来验证抽取只取容器内的内容。' * 15 +
        '</p><p><a href="./P020261016.docx">附件：行动方案.docx</a></p></div>'
        '<div id="footer">版权所有 京ICP备00000000号</div></body></html>')


def entry(url='https://www.mohurd.gov.cn/a.htm'):
    return {'date': '2026-10-16', 'title': '城镇供热"温暖工程"三年行动方案',
            'card': '政策卡片-产业与能源', 'url': url,
            'org': '住房城乡建设部办公厅', 'no': '建办城函〔2026〕239号',
            'level': sources.level(url), 'why': sources.why(url)}


class TestBlocks(unittest.TestCase):
    def test_只在标题处切断(self):
        got = fetch_mod.blocks(CARD)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0][0], '2026-10-16')
        # `**核心要点**` 是本小节的内容，不能被当成下一节的开头
        self.assertIn('核心要点', got[0][2])

    def test_末节不吞后面的内容(self):
        text = CARD + '\n## 关联政策\n\n- 别的什么\n'
        got = fetch_mod.blocks(text)
        self.assertEqual(len(got), 2)
        self.assertNotIn('别的什么', got[-1][2])


class TestEntry(unittest.TestCase):
    def test_取到链接机关文号(self):
        e = fetch_mod.entry_of(Path('政策卡片-产业与能源.md'), *fetch_mod.blocks(CARD)[0])
        self.assertEqual(e['url'], 'https://www.mohurd.gov.cn/a.htm')
        self.assertEqual(e['org'], '住房城乡建设部办公厅')
        self.assertEqual(e['no'], '建办城函〔2026〕239号')
        self.assertEqual(e['level'], '原文')

    def test_待补视为无链接(self):
        e = fetch_mod.entry_of(Path('x.md'), *fetch_mod.blocks(CARD)[1])
        self.assertEqual(e['url'], '')


class TestLevel(unittest.TestCase):
    def test_三级(self):
        self.assertEqual(sources.level('https://www.mofcom.gov.cn/a.html'), '原文')
        self.assertEqual(sources.level('https://www.gov.cn/zhengce/a.htm'), '原文')
        self.assertEqual(sources.level('https://www.news.cn/politics/a.htm'), '官方报道')
        self.assertEqual(sources.level('https://news.qq.com/a.htm'), '非一手')
        self.assertEqual(sources.level(''), '非一手')

    def test_黑名单一律非一手(self):
        self.assertEqual(sources.level('https://www.jiemian.com/article/1.html'), '非一手')
        self.assertEqual(sources.level('https://xueqiu.com/1'), '非一手')


class TestNaming(unittest.TestCase):
    def test_文件名四段(self):
        self.assertEqual(fetch_mod.fname(entry()),
                         '2026-10-16_住房城乡建设部办公厅_建办城函〔2026〕239号_城镇供热"温暖工程"三年行动方案.md')

    def test_文号去掉解释性括号(self):
        self.assertEqual(fetch_mod.clean_no('商务部 海关总署公告2026年第52号（附清单）'),
                         '2026年第52号')
        self.assertEqual(fetch_mod.clean_no('建办城函〔2026〕239号'), '建办城函〔2026〕239号')

    def test_非法字符不进文件名(self):
        e = dict(entry(), title='关于A/B: C?的<通知>')
        self.assertNotIn('/', fetch_mod.fname(e))


class TestWeb(unittest.TestCase):
    def test_GBK页不乱码(self):
        body = '<html><head><meta charset="gb2312"></head><body><p>政策</p></body></html>'
        self.assertIn('政策', web.decode(body.encode('gb18030')))

    def test_只取正文容器(self):
        lines = web.body_lines(HTML)
        joined = '\n'.join(lines)
        self.assertIn('这是一段正文', joined)
        self.assertNotIn('京ICP', joined)          # 页脚不算正文
        self.assertNotIn('首页 政策', joined)       # 导航不算正文

    def test_附件扩展名从查询参数取(self):
        url = 'https://x.mofcom.gov.cn/download?fileUrl=abc&fileName=P0202.docx'
        self.assertEqual(web.suffix(url), 'docx')
        self.assertEqual(web.suffix('https://x.gov.cn/a/b.PDF'), 'pdf')
        self.assertEqual(web.suffix('https://x.gov.cn/a'), '')

    def test_栏目页判为无具体文件(self):
        self.assertTrue(web.is_listing('https://www.mohurd.gov.cn/gongkai/zc/wjk/'))
        self.assertTrue(web.is_listing('https://www.ndrc.gov.cn'))
        self.assertFalse(web.is_listing('https://www.gov.cn/zhengce/content_1.htm'))

    def test_乱码正文判为非文本(self):
        """实物：`decode(errors='ignore')` 把二进制解成一串「看着像字」的东西，
        长度过 600 字门槛，存档于是写「正文完整性: 完整」。判据必须拦住它。"""
        # ① NUL 字节：网页正文不可能有，零误判
        self.assertTrue(web.looks_binary('\x00\x00\x00 正文正文'))
        # ② 解错编码得到的其它文字（西里尔／叙利亚文一类），占比高
        garbage = ''.join(chr(c) for c in range(0x0700, 0x0740)) * 6
        self.assertTrue(web.looks_binary(garbage))

    def test_正常正文不误判(self):
        body = ('工业和信息化部等八部门印发《产业基础能力提升"十五五"规划》。规划提出，'
                '到2030年，产业基础薄弱环节取得实质性突破，重点领域基础产品和技术'
                '供给能力明显增强，产业链供应链韧性和安全水平显著提升。')
        self.assertFalse(web.looks_binary(body))
        # 英文页、数字表也不能误判
        self.assertFalse(web.looks_binary('Note: the tariff rate is 12.5% (2026). See Annex A-3, p.17.'))
        # 清单类附件转成的表格正文：ASCII 标点占大半，更不能判成乱码
        self.assertFalse(web.looks_binary('| 序号 | 编码 | 数量 |\n|---|---|---|\n| 1 | 8501.10 | 12 |'))


class TestArchive(unittest.TestCase):
    """端到端：写一份、再跑一次必须是「已存档跳过」。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.art = self.tmp / 'raw' / 'articles'
        self.art.mkdir(parents=True)
        self.args = {'dry': False, 'keep': False}
        self.stats = {'new': 0, 'skip': 0, 'nofirst': 0, 'fail': 0, 'chars': 0,
                      'seen': self.stored()}
        self.calls = []

    def stored(self):
        """读的是临时库，不是真库——否则测试会随真实存档增长而变化。"""
        with mock.patch.object(fetch_mod, 'ARTICLE_DIR', self.art):
            return fetch_mod.stored_urls()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake(self, url, timeout=25, insecure=False):
        self.calls.append(url)
        return 200, HTML.encode('utf-8'), False

    def run_once(self, e=None):
        with mock.patch.object(web, 'fetch', self.fake), \
                mock.patch.object(fetch_mod, 'ARTICLE_DIR', self.art):
            tag, note = fetch_mod.attempt(e or entry(), 1, self.args, self.stats, str(self.tmp))
        return tag, note

    def test_写出存档且字段齐备(self):
        tag, note = self.run_once()
        self.assertEqual(tag, 'new', note)
        f = next(self.art.glob('*.md'))
        text = f.read_text(encoding='utf-8')
        self.assertIn('原文链接: https://www.mohurd.gov.cn/a.htm', text)
        self.assertIn('存档级别: 原文', text)
        self.assertIn('## 附件原文', text)          # 附件名在页内，应该被下载转文本
        self.assertTrue(f.name.startswith('2026-10-16_'), f.name)

    def test_第二次跑不再抓也不重写(self):
        self.run_once()
        self.stats['seen'] = self.stored()          # 相当于下一轮重跑（重新读库）
        n = len(self.calls)
        tag, _ = self.run_once()
        self.assertEqual(tag, 'skip')
        self.assertEqual(len(self.calls), n, '已存档的条目不该再发请求')

    def test_非一手不发请求(self):
        tag, note = self.run_once(entry('https://news.qq.com/a/20261016.shtml'))
        self.assertEqual(tag, 'nofirst')
        self.assertEqual(self.calls, [])
        self.assertIn('非发文机关', note)

    def test_占位链接不重试(self):
        tag, note = self.run_once(entry('https://www.gov.cn/zhengce/content_70xxx.htm'))
        self.assertEqual(tag, 'nofirst')
        self.assertIn('占位符', note)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
