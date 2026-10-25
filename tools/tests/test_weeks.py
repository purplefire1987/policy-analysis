#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周观点速览表匹配：同分裁决与合并行判定。

为什么要这两条：2026-10-26 试运行 W43 时，49 号（无人机）与 51 号（挖泥船）
两份同日公告共享同一句套话「优化调整××相关物项出口管制措施」，核心词加成把
两者都抬到 1.0，按行序第一个通吃，于是 51 号被判「错位」、49 号被判「合并且未
注明」——表其实全对，脚本报了两个假警。这类假警的代价是让人不再信脚本。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.weeks import _match  # noqa: E402

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


if __name__ == '__main__':
    unittest.main()
