#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡片 × 一手存档：两份独立落盘物的日期必须自洽。

为什么测：卡片日期错了没人会报（T-20261024-17 整天差一年）。本项能挡的是
「改了一边没改另一边」与「落盘时解析错」，挡不住「两边一起错」——后者只能外部核，
所以每条测试都顺带钉住「不谎报范围」这句话。

匹配只认文号与标题包含，不做相似度猜测：猜错会指向另一条政策，报出来的
「不一致」比不报更坏。模糊匹配的反例必须留着。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import archives as A        # noqa: E402
from pkb.core import Verdict                # noqa: E402

CARD_HEAD = '---\n类型: 政策卡片\n---\n\n## 政策演进（按时间倒序，最新第一）\n\n'


def card(date, title, no='商发〔2026〕1号'):
    return CARD_HEAD + f'### {date} · {title}\n\n**发文机关**：商务部 ｜ **文号**：{no} ｜ [政策原文](https://x)\n'


def archive(date, title, no='商发〔2026〕1号', file_date=None):
    fd = file_date or date
    return (f'---\n类型: 一手存档\n政策日期: {date}\n文号: {no}\n---\n\n# {title}\n',
            f'{fd}_商务部_{title}.md')


def run(cards=None, arcs=None, sigs=None):
    """搭一个最小库跑一次；cards 是 {文件名: 内容}，arcs / sigs 是 [(内容, 文件名)]。

    **三个目录都要 mock**（2026-10-26 晚）：`run()` 除了卡片与存档，还要读
    `wiki/政策信号/`（一手存档也可能服务于信号条目，如央行汇率立场文件）。
    漏 mock 就会去读真实库——测试于是变成「看今天库里几份」，本地绿、CI 空库红。
    """
    with tempfile.TemporaryDirectory() as d:
        cd, ad, sd = Path(d) / '卡片', Path(d) / '存档', Path(d) / '信号'
        cd.mkdir()
        for name, text in (cards or {}).items():
            (cd / name).write_text(text, encoding='utf-8')
        for base, items in ((ad, arcs), (sd, sigs)):
            base.mkdir()
            for text, name in (items or []):
                (base / name).write_text(text, encoding='utf-8')
        with mock.patch.object(A, 'CARD_DIR', cd), \
                mock.patch.object(A, 'ARTICLE_DIR', ad), \
                mock.patch.object(A, 'SIGNAL_DIR', sd):
            return A.run([])


class Test日期核对(unittest.TestCase):
    def test_日期一致不报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertIn('问题 0', r.summary)

    def test_差超过容差要报并写出两边日期(self):
        r = run({'政策卡片-消费.md': card('2026-09-01', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('问题 1', r.summary)
        line = [x for x in r.lines if '差' in x][0]
        self.assertIn('2026-10-09', line)
        self.assertIn('2026-09-01', line)

    def test_容差之内不报(self):
        """印发与公开发布间隔几天是常事，不该天天报警。"""
        r = run({'政策卡片-消费.md': card('2026-10-05', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertIn('问题 0', r.summary)

    def test_文件名日期与frontmatter不一致要报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施', file_date='2026-10-08')])
        self.assertTrue(any('两个日子' in x for x in r.lines), r.lines)

    def test_找不到对应小节要报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '完全不相干的另一份文件名称', no='商发〔2026〕9号')])
        self.assertTrue(any('没找到对应卡片小节或信号条目' in x for x in r.lines), r.lines)

    def test_按文号匹配不依赖标题(self):
        """标题被改过但文号还在——仍然该认出来，并只报日期差。"""
        r = run({'政策卡片-消费.md': card('2026-10-09', '房车消费措施（原名已被改）')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('问题 0', r.summary)

    def test_文号命中多条且标题也不唯一时放弃(self):
        """同一个文号挂了两条小节、标题又对不上——不许猜是哪条，报「找不到」。"""
        two = card('2026-10-09', '甲政策名称足够长') + '\n' + card('2026-10-10', '乙政策名称足够长')
        r = run({'政策卡片-消费.md': two},
                [archive('2026-10-09', '完全不相干的另一份文件名称', no='商发〔2026〕9号')])
        self.assertTrue(any('没找到对应卡片小节或信号条目' in x for x in r.lines), r.lines)

    def test_空存档目录不给结论(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')}, [])
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertIn('0 份', r.summary)

    def test_通过时写明查不到什么(self):
        """绿灯不许被读成「日期已核过」——这句话必须在输出里。"""
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertTrue(any('两边一起错' in x for x in r.lines), r.lines)


class Test目录归属(unittest.TestCase):
    """`raw/articles/` 只放文件本身——判「自称的级别」够不够格进这个目录。

    为什么要有：分家之前 58 份里 26 份不是文件本身，而每份 frontmatter 都写着
    `存档级别: 官方报道`。字段是对的，只是没人读。现在的口径更硬：报道类根本不进
    `raw/`（按内容归政策卡片或政策信号），所以「自称不是原文却躺在 articles」就该报。
    """

    def test_报道放进了原文目录要报(self):
        text, name = archive('2026-10-09', '某会议报道', no='无')
        text = text.replace('文号: 无', '文号: 无\n存档级别: 官方报道')
        r = run({'政策卡片-消费.md': card('2026-10-09', '某会议报道', no='无')},
                [(text, name)])
        self.assertTrue([x for x in r.lines if '只该放' in x],
                        '报道放进 articles/ 必须点名「只该放」')

    def test_非一手也报(self):
        text, name = archive('2026-10-09', '某门户转述', no='无')
        text = text.replace('文号: 无', '文号: 无\n存档级别: 非一手')
        r = run({'政策卡片-消费.md': card('2026-10-09', '某门户转述', no='无')},
                [(text, name)])
        self.assertTrue([x for x in r.lines if '只该放' in x])

    def test_没有级别字段不报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('问题 0', r.summary)

    def test_摘要只写原文份数(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('一手存档 1 份', r.summary)
        self.assertNotIn('报道区', r.summary)


class Test已终止待移归档(unittest.TestCase):
    """归档的触发条件只有「政策已终止」（2026-10-28），而声明不等于已执行。

    写了 `> **状态**：已废止（被 … 取代）` 却不搬，`归档/index.md` 会一直把这条
    算作在用政策——清单是对的，卡片是错的，两边都没人报。所以要有一条判据
    核「声明有没有被执行」，而不是只生成清单。
    """

    def test_已终止仍在卡里要报(self):
        body = card('2026-09-01', '旧版出口许可管理办法').replace(
            '\n\n**发文机关**',
            '\n\n> **状态**：已废止（被 2026-10-01《新办法》取代）\n\n**发文机关**', 1)
        r = run({'政策卡片-出口管制与国际博弈.md': body})
        self.assertIn('待归档 1', r.summary)
        self.assertTrue(any('待移入归档' in x for x in r.lines), r.lines)

    def test_正常小节不报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')})
        self.assertIn('待归档 0', r.summary)

    def test_只认状态行不认正文提法(self):
        """正文里说「本文件废止了 X」是**内容**，不是这条政策自身已终止。

        判据认的是引用块里的 `**状态**：`，宽松到扫全文就会把「废止旧政策」
        的每一节都报成待归档——**会误伤正确写法的规则比不扫更糟**。
        """
        body = card('2026-10-09', '关于促进房车消费的若干措施').replace(
            '\n\n**发文机关**',
            '\n\n本办法自公布之日起施行，同时废止 2019 年发布的旧办法。\n\n**发文机关**', 1)
        r = run({'政策卡片-消费.md': body})
        self.assertIn('待归档 0', r.summary)


class Test存档可服务信号(unittest.TestCase):
    """一手存档不一定对应政策卡片：按「信号≠政策」口径转记后，有些文件服务于信号条目。

    2026-10-26 实证：央行《关于人民币汇率的政策立场》是一手文本、进了 `raw/articles/`，
    但条目在政策信号页。只认卡片就会把它报成「卡片漏了」，而它并不缺。
    """

    def test_同日且标题相近视为已归属(self):
        body = ('---\n类型: 政策信号汇总\n---\n\n'
                '### 2026-10-08 · 中国人民银行发布《关于人民币汇率的政策立场》：首次系统阐述\n')
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-08', '中国人民银行关于人民币汇率的政策立场', no='无')],
                sigs=[(body, '政策信号-金融强国.md')])
        self.assertIn('问题 0', r.summary)

    def test_跨日不认(self):
        """同日才算——跨日靠相似度猜，等于把两条不相干的事绑在一起。"""
        body = ('---\n类型: 政策信号汇总\n---\n\n'
                '### 2026-10-07 · 中国人民银行关于人民币汇率的政策立场\n')
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-08', '中国人民银行关于人民币汇率的政策立场', no='无')],
                sigs=[(body, '政策信号-金融强国.md')])
        self.assertTrue(any('没找到对应卡片小节或信号条目' in x for x in r.lines))
