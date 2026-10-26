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

from pkb.checks import judgments as J              # noqa: E402
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


class Test裁判来源(unittest.TestCase):
    """「裁判只能取手册第三节列过的」这句话此前没有判据。

    查第一条真数据就不对：台账写「财政部预算公开」，手册里叫「预算与决算公开」——
    名字不在名单里，等于那条判断在制度上「无裁判可用」，而台账看着完全正常。
    所以这里三条：不在名单要报、与第八节不一致要报、名单读不出来也要报（不能静默）。
    """

    HANDBOOK = """## 三、独立裁判清单

| 裁判 | 能裁定什么 | 为什么可信 | 取数处 |
|---|---|---|---|
| 海关月度数据 | 贸易流 | 行政统计 | 海关统计平台 |
| 预算与决算公开 | 有没有钱 | 法定公开 | 财政部预算司 |
| **时间＋预登记账本** | 判断本身对错 | 不需要人评理 | 第八节 → 第七节 |
"""

    def _row(self, ref, jid='J2026-W43-1'):
        return [jid, '判断原文', '阈值', ref, '2026-11-20', '⏳ 待判', '']

    def test_名单从手册表格读_星号要去掉(self):
        allowed = J.allowed_referees(self.HANDBOOK)
        self.assertEqual(allowed, ['海关月度数据', '预算与决算公开', '时间＋预登记账本'])
        self.assertIn('时间＋预登记账本', allowed)

    def test_括号里是取数处_不参与比对(self):
        self.assertEqual(J.referee_name('预算与决算公开（财政部预算司）'), '预算与决算公开')
        self.assertEqual(J.referee_name('海关月度数据(8 位 HS 编码)'), '海关月度数据')
        self.assertEqual(J.referee_name(''), '')

    def test_名单内不报错(self):
        allowed = J.allowed_referees(self.HANDBOOK)
        errs = J.check_referees([self._row('海关月度数据（海关统计平台）')], allowed, {})
        self.assertEqual(errs, [])

    def test_不在名单要报_并给最接近的(self):
        allowed = J.allowed_referees(self.HANDBOOK)
        errs = J.check_referees([self._row('财政部预算公开')], allowed, {})
        self.assertTrue(any('不在手册第三节名单内' in e for e in errs), errs)
        self.assertTrue(any('预算与决算公开' in e for e in errs), errs)

    def test_裁判空着要报(self):
        allowed = J.allowed_referees(self.HANDBOOK)
        errs = J.check_referees([self._row('')], allowed, {})
        self.assertTrue(any('裁判列是空的' in e for e in errs), errs)

    def test_与第八节不一致要报(self):
        """台账写着「原样抄进下表，改一个字就对不上」——那就让脚本去看。"""
        allowed = J.allowed_referees(self.HANDBOOK)
        weeks = {'J2026-W43-1': ('周观点-2026-W43.md', '海关月度数据（海关统计平台）')}
        errs = J.check_referees([self._row('海关月度数据（海关总署）')], allowed, weeks)
        self.assertTrue(any('与 周观点-2026-W43.md 第八节不一致' in e for e in errs), errs)

    def test_名单读不出来不能静默放过(self):
        """手册改名/表被删时不报错就糟了：那等于校验悄悄消失，而报告仍写「通过」。"""
        errs = J.check_referees([self._row('海关月度数据')], [], {})
        self.assertTrue(any('判据失效' in e for e in errs), errs)


if __name__ == '__main__':
    unittest.main()
