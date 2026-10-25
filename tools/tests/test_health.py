#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集健康的判据测试：三分状态必须互斥且措辞不同。

为什么单独测这一项：它的价值全在「区分」——「跑了但 0 条」与「根本没跑」
如果给同一个结论，那这项检查就退回成「看最后一行日期」，等于没做。
测试用假的日志与状态页，不碰真库。
"""
import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import health          # noqa: E402
from pkb.core import Verdict           # noqa: E402

TODAY = datetime.date(2026, 10, 25)

HEAD = """## 运行台账（按日期倒序）

| 日期 | 轮次 | 新增政策 | 写入位置 | 政策信号 | 状态 | 备注 |
|---|---|---|---|---|---|---|
"""

STATUS_TPL = """## 一、当前状态（每次运行覆盖）

| 任务 | 自动化 | 节拍 | 最近运行 | 退出码 | 本轮产出 | 遗留 | 灯 |
|---|---|---|---|---|---|---|---|
| 采集 | d1 | 每日 09:00 | {when} | 0 | 2 条 | 无 | {lamp} |
"""


def log(*rows):
    return HEAD + ''.join(
        f'| {d} | {rnd} | {pol} | 位置 | {sig} | {st} | 备注 |\n'
        for d, rnd, pol, sig, st in rows)


def run_with(log_text, lamp='🟡', today=TODAY):
    """把 read() 换成按路径返回假文本，today() 固定。"""
    def fake_read(p, default=None):
        s = str(p)
        return log_text if s.endswith('采集日志.md') else STATUS_TPL.format(when='x', lamp=lamp)

    with mock.patch.object(health, 'read', side_effect=fake_read), \
         mock.patch.object(health, 'today', return_value=today):
        return health.run([])


class Test三分状态(unittest.TestCase):
    def test_正常有新增(self):
        r = run_with(log(('2026-10-25', '第三十四轮', '1', '2', '✅ 已入库')))
        self.assertIs(r.verdict, Verdict.PASS)
        self.assertIn('采集健康', r.summary)
        self.assertNotIn('没采到', r.summary)

    def test_跑了但0条不算漏跑(self):
        r = run_with(log(('2026-10-25', '第三十四轮', '0', '0', '✅ 已入库')))
        self.assertIs(r.verdict, Verdict.PASS)
        self.assertIn('没采到', r.summary)
        self.assertNotIn('根本没跑', r.summary)

    def test_根本没跑(self):
        r = run_with(log(('2026-10-22', '第三十二轮', '5', '3', '✅ 已入库'))
                     )
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertIn('3 天前', r.summary)
        self.assertIn('根本没跑', r.summary)

    def test_中间有未运行留痕要说明是跑了失败(self):
        text = log(('2026-10-22', '第三十二轮', '5', '3', '✅ 已入库'),
                   ('2026-10-23', '—', '—', '—', '❌ 未运行/无产出'))
        r = run_with(text)
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertIn('留痕', r.summary)


class Test灯交叉核对(unittest.TestCase):
    def test_没跑却点绿灯是矛盾(self):
        r = run_with(log(('2026-10-20', '第三十轮', '2', '1', '✅ 已入库')), lamp='🟢')
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertTrue(any('灯' in e for e in [r.summary] + r.lines))

    def test_有记录却点红灯是矛盾(self):
        r = run_with(log(('2026-10-25', '第三十四轮', '1', '2', '✅ 已入库')), lamp='🔴')
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertIn('矛盾', r.summary)


class Test日志完整性(unittest.TestCase):
    def test_日志不存在是BAD_INPUT(self):
        with mock.patch.object(health, 'read', return_value=''):
            r = health.run([])
        self.assertIs(r.verdict, Verdict.BAD_INPUT)
        self.assertTrue(r.summary.strip())

    def test_没有任何轮次行要报错(self):
        text = log(('2026-10-21', '结构重构', '0', '0', '✅ 完成'))
        r = run_with(text)
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertIn('没有任何采集轮次', r.summary)

    def test_汉字轮次能识别(self):
        text = log(('2026-10-25', '第三十四轮', '1', '2', '✅ 已入库'))
        self.assertEqual(len(health.parse_collect_log(text)), 1)
        self.assertTrue(health.is_round({'round': '第三十四轮', 'status': '✅ 已入库'}))

    def test_规则生效后写破折号要报错(self):
        text = log(('2026-10-24', '第三十三轮', '—', '2', '✅ 已入库'))
        r = run_with(text)
        self.assertIs(r.verdict, Verdict.FAIL)
        self.assertIn('0 也写 0', r.summary)

    def test_规则生效前写破折号只提示不阻断(self):
        text = log(('2026-10-19', '第二十九轮', '—', '—', '✅ 已入库'),
                   ('2026-10-25', '第三十四轮', '1', '2', '✅ 已入库'))
        r = run_with(text)
        self.assertIs(r.verdict, Verdict.PASS)
        self.assertTrue(any('历史' in ln for ln in r.lines))


if __name__ == '__main__':
    unittest.main()
