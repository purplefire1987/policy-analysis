#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口径单测：黑名单、归档周名单、字段枚举、卡→领域映射。

这些是「改一处就漂」的高危口径。历史上黑名单两份清单漂移过，
归档周豁免两套判据并存过——这里把它们钉住。

跑法：python3 -m unittest discover -s tools/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.domain import (BLACK, BAD_SUBJECT, is_bad, DOMAINS, STAT_DOMAINS,  # noqa: E402
                        IMPACTS, STATUSES, REQUIRED_FIELDS, FIELD_MAP, LEGACY_WEEKS,
                        ANALYSIS_TYPES, ANALYSIS_SPINE, ANALYSIS_WORD_LIMIT)


class TestBlacklist(unittest.TestCase):
    def test_用户明确排除的两家必须在名单里(self):
        self.assertIn('jiemian.com', BLACK)
        self.assertTrue(is_bad('https://www.jiemian.com/article/1.html'))

    def test_聚合页与自媒体命中(self):
        for url in ('https://www.toutiao.com/a1', 'https://mp.weixin.qq.com/s/x',
                    'https://xueqiu.com/1', 'https://guba.eastmoney.com/x'):
            self.assertTrue(is_bad(url), url)

    def test_官网不命中(self):
        for url in ('https://www.ndrc.gov.cn/xxgk/zcfb/tz/202610/t1.html',
                    'https://www.gov.cn/zhengce/content/2026-10/25/content_1.htm'):
            self.assertFalse(is_bad(url), url)

    def test_主体关键词非空(self):
        self.assertIn('界面新闻', BAD_SUBJECT)
        self.assertIn('中华网', BAD_SUBJECT)


class TestLegacy(unittest.TestCase):
    def test_名单只含规则变更前的三周(self):
        self.assertEqual(LEGACY_WEEKS, frozenset({'2026-W39', '2026-W40', '2026-W41'}))

    def test_新周不得进名单(self):
        for wk in ('2026-W42', '2026-W43', '2026-W52'):
            self.assertNotIn(wk, LEGACY_WEEKS)


class TestFields(unittest.TestCase):
    def test_五领域与统计四领域(self):
        self.assertEqual(len(DOMAINS), 5)
        self.assertEqual(set(STAT_DOMAINS), set(DOMAINS) - {'总体规划'})
        self.assertEqual(len(STAT_DOMAINS), 4)

    def test_影响与状态枚举(self):
        self.assertEqual(IMPACTS, frozenset({'高', '中', '低'}))
        self.assertIn('已废止', STATUSES)

    def test_必填字段十四项且不重复(self):
        self.assertEqual(len(REQUIRED_FIELDS), 14)
        self.assertEqual(len(set(REQUIRED_FIELDS)), 14)
        for f in ('名称', '领域', '政策数', '所属政策链', 'tags'):
            self.assertIn(f, REQUIRED_FIELDS)


class TestChainMap(unittest.TestCase):
    def test_每张卡都有映射(self):
        self.assertEqual(len(FIELD_MAP), 33)

    def test_映射值必须是合法领域(self):
        # 这条钉子抓过一个真实 bug：顶层规划卡曾映射成「顶层规划」，而 DOMAINS 里是「总体规划」
        for card, domain in FIELD_MAP.items():
            self.assertIn(domain, DOMAINS, f'{card} → {domain} 不是合法领域')


class TestAnalysis(unittest.TestCase):
    def test_八节骨架(self):
        self.assertEqual(len(ANALYSIS_SPINE), 8)
        self.assertTrue(ANALYSIS_SPINE[3].endswith('、'))   # 第四节按类型定名，只校验前缀

    def test_类型与字数上限(self):
        self.assertEqual(ANALYSIS_WORD_LIMIT, 8000)
        self.assertIn('专题评估', ANALYSIS_TYPES)


if __name__ == '__main__':
    unittest.main()
