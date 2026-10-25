#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判断台账：编号可回原文、到期才结算。

为什么这些用例：判断是跨周对象，卡片引用它、下期复盘它。台账一旦和第八节脱钩，
就会变成「另写一遍判断」——那时它比没有更糟：读者会以为它在核对，其实在自说自话。
所以最要紧的两条是「编号必须在第八节里找得到」和「同一编号只许一行」。

跑法：python3 -m unittest discover -s tools/tests
"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.judgments import audit, ledger_rows, overdue  # noqa: E402

WEEK = """## 八、本周可证伪判断

| # | 判断（含方向、比较对象、阈值） | 指标与阈值 | 数据出处（裁判） | 判定日 |
|---|---|---|---|---|
| J2026-W43-1 | 稀土出口均价环比升超 10% | +10% | 海关总署月度数据 | 2026-11-20 |
| J2026-W43-2 | 失业率不高于 5.2% | 5.2% | 统计局月度数据 | 2026-11-15 |
"""


def row(jid, due='2026-11-20', state='⏳ 待判', basis='—'):
    """按台账的列序造一行：编号｜判断｜指标｜裁判｜判定日｜状态｜结算依据。"""
    return [jid, '判断原文', '阈值', '裁判', due, state, basis]


class TestLedgerParse(unittest.TestCase):
    def test_只认台账那一节(self):
        text = ('## 二、取值约定\n\n| 字段 | 取值 |\n|---|---|\n| 状态 | 四值 |\n\n'
                '## 四、台账\n\n| 编号 | 判断 | 指标与阈值 | 裁判 | 判定日 | 状态 | 结算依据 |\n'
                '|---|---|---|---|---|---|---|\n'
                '| J2026-W43-1 | 判断原文 | 阈值 | 裁判 | 2026-11-20 | ⏳ 待判 | — |\n')
        rows = ledger_rows(text)
        self.assertEqual(len(rows), 1, '取值说明表不该被当成台账行')
        self.assertEqual(rows[0][0], 'J2026-W43-1')

    def test_空台账不算错(self):
        text = ('## 四、台账\n\n| 编号 | 判断 | 指标与阈值 | 裁判 | 判定日 | 状态 | 结算依据 |\n'
                '|---|---|---|---|---|---|---|\n')
        self.assertEqual(ledger_rows(text), [])


class TestAudit(unittest.TestCase):
    def _run(self, rows):
        return audit(rows, lambda jid: WEEK if jid.startswith('J2026-W43') else None)

    def test_对得上就无错(self):
        errors, items = self._run([row('J2026-W43-1'), row('J2026-W43-2')])
        self.assertEqual(errors, [])
        self.assertEqual(len(items), 2)

    def test_第八节没有这个号就是编造(self):
        errors, _ = self._run([row('J2026-W43-9')])
        self.assertTrue(any('第八节里不存在' in e for e in errors), errors)

    def test_同一编号只许一行(self):
        errors, items = self._run([row('J2026-W43-1'), row('J2026-W43-1', state='✅ 成立')])
        self.assertTrue(any('重复登记' in e for e in errors), errors)
        self.assertEqual(len(items), 1, '重号只算一条，不是两条')

    def test_状态越界判错(self):
        errors, _ = self._run([row('J2026-W43-1', state='基本成立')])
        self.assertTrue(any('状态' in e for e in errors), errors)

    def test_判定日必须可解析(self):
        errors, _ = self._run([row('J2026-W43-1', due='后续观察')])
        self.assertTrue(any('判定日' in e for e in errors), errors)

    def test_列数不足不静默跳过(self):
        errors, _ = self._run([['J2026-W43-1', '判断原文']])
        self.assertTrue(any('列' in e for e in errors), errors)

    def test_没有对应周观点文件(self):
        errors, _ = self._run([row('J2026-W44-1')])
        self.assertTrue(any('找不到' in e for e in errors), errors)


class TestOverdue(unittest.TestCase):
    def test_到期未结算才点名(self):
        _, items = audit([row('J2026-W43-1', due='2026-11-01'),
                          row('J2026-W43-2', due='2026-12-01')],
                         lambda jid: WEEK)
        self.assertEqual(overdue(items, datetime.date(2026, 11, 20)), ['J2026-W43-1'])

    def test_已结算的不再点名(self):
        _, items = audit([row('J2026-W43-1', due='2026-11-01', state='✅ 成立',
                              basis='2026-11-18 海关数据 +8%')], lambda jid: WEEK)
        self.assertEqual(overdue(items, datetime.date(2026, 11, 20)), [])

    def test_判定日当天不算过期(self):
        _, items = audit([row('J2026-W43-1', due='2026-11-20')], lambda jid: WEEK)
        self.assertEqual(overdue(items, datetime.date(2026, 11, 20)), [])


if __name__ == '__main__':
    unittest.main()
