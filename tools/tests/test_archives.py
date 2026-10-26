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


def run(cards=None, arcs=None, reps=None):
    """搭一个最小库跑一次；cards 是 {文件名: 内容}，arcs/reps 是 [(内容, 文件名)]。

    **三个目录都要 mock**（2026-10-26）：`run()` 还要读 `raw/reports/` 判断
    「级别与目录是否一致」，漏 mock 就会去读真实库——测试于是变成「看今天库里几份」，
    本地绿、CI 空库红，或者反过来。
    """
    with tempfile.TemporaryDirectory() as d:
        cd, ad, rd = Path(d) / '卡片', Path(d) / '存档', Path(d) / '报道'
        cd.mkdir()
        for name, text in (cards or {}).items():
            (cd / name).write_text(text, encoding='utf-8')
        for base, items in ((ad, arcs), (rd, reps)):
            base.mkdir()
            for text, name in (items or []):
                (base / name).write_text(text, encoding='utf-8')
        with mock.patch.object(A, 'CARD_DIR', cd), \
                mock.patch.object(A, 'ARTICLE_DIR', ad), \
                mock.patch.object(A, 'REPORT_DIR', rd):
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
        self.assertTrue(any('没找到对应卡片小节' in x for x in r.lines), r.lines)

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
        self.assertTrue(any('没找到对应卡片小节' in x for x in r.lines), r.lines)

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
    """`articles` 只放原文、`reports` 只放报道——判「自称的级别」与「所在目录」是否一致。

    为什么要有：分目录之前 58 份里 26 份不是文件本身，而每份 frontmatter 都写着
    `存档级别: 官方报道`。字段是对的，只是没人读。光加目录不加判据，下一个人
    照样能把记者稿塞回 `articles`。这两条钉住「塞回去会报」。
    """

    def test_报道放进了原文目录要报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('问题 0', r.summary)

        text, name = archive('2026-10-09', '某会议报道', no='无')
        text = text.replace('文号: 无', '文号: 无\n存档级别: 官方报道')
        r2 = run({'政策卡片-消费.md': card('2026-10-09', '某会议报道', no='无')},
                 [(text, name)])
        self.assertTrue([x for x in r2.lines if '只该放' in x],
                        '报道放进 articles/ 必须点名「只该放」')

    def test_原文放进了报道目录要报(self):
        text, name = archive('2026-10-09', '关于促进房车消费的若干措施')
        text = text.replace('文号: 商发〔2026〕1号', '文号: 商发〔2026〕1号\n存档级别: 原文')
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                reps=[(text, name)])
        self.assertTrue([x for x in r.lines if '只该放' in x],
                        '原文放进 reports/ 必须点名「只该放」')
        self.assertIn('报道区 1', r.summary)

    def test_没有级别字段不报(self):
        r = run({'政策卡片-消费.md': card('2026-10-09', '关于促进房车消费的若干措施')},
                [archive('2026-10-09', '关于促进房车消费的若干措施')])
        self.assertIn('问题 0', r.summary)

    def test_摘要写出报道区份数(self):
        text, name = archive('2026-10-09', '某会议报道', no='无')
        text = text.replace('文号: 无', '文号: 无\n存档级别: 官方报道')
        r = run({'政策卡片-消费.md': card('2026-10-09', '某会议报道', no='无')},
                reps=[(text, name)])
        self.assertIn('报道区 1', r.summary)
