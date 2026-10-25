#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周观点速览表：同分裁决、合并行判定、影响列校验。

前两条的由来：2026-10-26 试运行 W43 时，49 号（无人机）与 51 号（挖泥船）
两份同日公告共享同一句套话「优化调整××相关物项出口管制措施」，核心词加成把
两者都抬到 1.0，按行序第一个通吃，于是 51 号被判「错位」、49 号被判「合并且未
注明」——表其实全对，脚本报了两个假警。这类假警的代价是让人不再信脚本。

影响列那条的由来：W42 出现过「中高」「中性偏正」「中（战略级）」，
三档之外自由发挥等于把「影响」写成形容词。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.weeks import _match, impact_issues  # noqa: E402
from pkb.domain import IMPACT_SINCE  # noqa: E402

CARD = '出口管制与国际博弈'
DRONE = '优化调整无人机相关物项出口管制措施（商务部 海关总署 中央军委装备发展部公告2026年第49号）'
DREDGE = '优化调整挖泥船相关物项出口管制措施（商务部 海关总署公告2026年第51号）'


class TestMatch(unittest.TestCase):

    def test_near_identical_titles_pick_own_row(self):
        """同批模板化标题：各归各行，不得互相认领。"""
        rows = [{'line': 1, '领域': '科技与数字化', '政策': DRONE},
                {'line': 2, '领域': '科技与数字化', '政策': DREDGE}]
        in_window = [('2026-10-19', DRONE, CARD), ('2026-10-19', DREDGE, CARD)]
        matched, used, orphan, merged, undeclared = _match(in_window, rows)
        self.assertEqual(len(matched), 2)
        self.assertEqual(orphan, [])
        self.assertEqual(merged, {})
        self.assertEqual(undeclared, [])

    def test_true_merge_needs_the_word(self):
        """真合并：一行覆盖两份同名文件；没写「合并」二字要报出来。"""
        title = '关于加快推进科技兴商的意见'
        rows = [{'line': 1, '领域': '经济与金融', '政策': title}]
        in_window = [('2026-10-19', title + '（国务院）', '消费与商贸'),
                     ('2026-10-19', title + '（商务部等9部门）', '消费与商贸')]
        *_, merged, undeclared = _match(in_window, rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(undeclared), 1)

        rows[0]['政策'] = '【合并 2 项】' + title
        *_, merged2, undeclared2 = _match(in_window, rows)
        self.assertEqual(len(merged2), 1)
        self.assertEqual(undeclared2, [])


class TestImpactColumn(unittest.TestCase):
    """速览表「影响」列：三档、可挂编号、编号须真在第八节。"""

    JUDGES = ('## 八、本周可证伪判断\n\n'
              '| # | 判断 | 指标与阈值 | 数据出处（裁判） | 判定日 |\n'
              '|---|---|---|---|---|\n'
              '| J2026-W43-1 | 甲 | 份数 | 官方统计月报 | 2027-01-20 |\n')

    def _rows(self, *values):
        return [{'line': i + 2, '领域': '产业与能源', '政策': f'政策{i}',
                 '影响': v} for i, v in enumerate(values)]

    def test_三档与挂牌号都通过(self):
        rows = self._rows('高（J2026-W43-1）', '中', '低')
        self.assertEqual(impact_issues(rows, self.JUDGES, IMPACT_SINCE), [])

    def test_复合档位不合格(self):
        rows = self._rows('中高', '中性偏正', '中（战略级）')
        self.assertEqual(len(impact_issues(rows, self.JUDGES, IMPACT_SINCE)), 3)

    def test_空值与叙述式影响不合格(self):
        rows = self._rows('', '影响深远，值得关注')
        self.assertEqual(len(impact_issues(rows, self.JUDGES, IMPACT_SINCE)), 2)

    def test_引用第八节没有的编号不合格(self):
        rows = self._rows('中（J2026-W43-9）')
        issues = impact_issues(rows, self.JUDGES, IMPACT_SINCE)
        self.assertEqual(len(issues), 1)
        self.assertIn('不在第八节', issues[0][2])

    def test_生效周之前不追溯(self):
        # W42 写的是「中高」，按今天的口径重判等于伪造当时的判断
        rows = self._rows('中高')
        self.assertEqual(impact_issues(rows, '', '2026-W42'), [])


if __name__ == '__main__':
    unittest.main()
