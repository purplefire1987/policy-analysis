#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台账结构判据：T- 行必须住在两节之内、列数与表头一致、未闭环项里编号唯一。

为什么测这个：2026-10-26 清理时发现一条记录被粘成了两行共用一行
（`… | ✅ 已关闭 | … || T-20261026-01 | …`），`plan` 只认行首编号，
后半条就静默消失——那条待办连续两天没进过派活清单，谁也没发现。
另有（同一天修的）一行 ✅ 落在第五节之后，同样读不到。
判据只认列数与节位，不认内容，所以每一条都要有反例。

「归档行引用同编号不报」也要测：关闭记录里留一份同编号的行是设计好的归档形态，
不能把「同号出现两次」一律判成重复，否则规则会逼着人删历史。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contextlib                                # noqa: E402
import datetime                                  # noqa: E402
import io                                        # noqa: E402

from pkb.checks.docs import _state as S        # noqa: E402
from pkb.checks.docs import ledger as L        # noqa: E402
from pkb.actions import ledger as A            # noqa: E402

TODAY = datetime.date(2026, 10, 26)

HEAD = ('# 任务台账\n\n## 二、未闭环项\n\n'
        '| 编号 | 首次发现 | 问题 | 类型 | 负责环节 | 状态 | 最近更新 | 关闭依据 |\n'
        '|---|---|---|---|---|---|---|---|\n')


def row(tid, status='🆕 待办'):
    return f'| {tid} | 2026-10-26 | 某问题 | 结构 | 采集 | {status} | 2026-10-26 | 待办 |'


def judge(text):
    """跑一次结构判据，返回 (errors, warnings)；台账路径用临时文件替换。"""
    S.rep.oks.clear()
    S.rep.errors.clear()
    S.rep.warns.clear()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / '任务台账.md'
        p.write_text(text, encoding='utf-8')
        with mock.patch.object(L, 'LEDGER', p):
            L.check_ledger_shape()
    return ([m for _i, m in S.rep.errors], [m for _i, m in S.rep.warns])


class Test结构自洽(unittest.TestCase):
    def test_正常一行不报(self):
        errs, _w = judge(HEAD + row('T-20261026-01') + '\n')
        self.assertEqual(errs, [])
        self.assertTrue(any('自洽' in o for o in S.rep.oks), S.rep.oks)

    def test_两条粘成一行要报(self):
        """行首那条照常读，后半条静默消失——最该拦的形态。"""
        errs, _w = judge(HEAD + row('T-20261026-01') + row('T-20261026-02') + '\n')
        self.assertTrue(any('粘成一行' in e for e in errs), errs)

    def test_放错节要报(self):
        text = HEAD + row('T-20261026-01') + '\n\n## 五、清欠进度\n\n' + row('T-20261026-02') + '\n'
        errs, _w = judge(text)
        self.assertTrue(any('放错节' in e for e in errs), errs)

    def test_编号重复要报(self):
        errs, _w = judge(HEAD + row('T-20261026-01') + '\n' + row('T-20261026-01') + '\n')
        self.assertTrue(any('编号唯一' in e for e in errs), errs)

    def test_归档行引用同编号不报(self):
        """关闭记录本来就留一份同编号的行，跨节重复不算重复。"""
        text = (HEAD + row('T-20261024-05', '✅ 已关闭') + '\n\n## 六、关闭记录\n\n'
                '| 编号 | 首次发现 | 关闭日 | 问题（摘要） | 关闭依据 |\n|---|---|---|---|---|\n'
                '| T-20261024-05 | 2026-10-24 | 2026-10-25 | 某问题 | 已修 |\n')
        errs, _w = judge(text)
        self.assertEqual(errs, [])

    def test_关闭记录列数不对要报(self):
        text = ('## 六、关闭记录\n\n'
                '| 编号 | 首次发现 | 关闭日 | 问题（摘要） | 关闭依据 |\n|---|---|---|---|---|\n'
                '| T-20261024-05 | 2026-10-24 | 2026-10-25 | 某问题 |\n')
        errs, _w = judge(text)
        self.assertTrue(any('应为 5 列' in e for e in errs), errs)

    def test_空台账只提示(self):
        errs, warns = judge('')
        self.assertEqual(errs, [])
        self.assertTrue(any('读不到' in w for w in warns), warns)


if __name__ == '__main__':
    unittest.main()


def ledger_text(rows, arch=None):
    """一份最小台账：只有「未闭环项」与「关闭记录」两节，够判生命周期。"""
    head = ('# 任务台账\n\n## 二、未闭环项\n\n'
            '| 编号 | 首次发现 | 问题 | 类型 | 负责环节 | 状态 | 最近更新 | 关闭依据 |\n'
            '|---|---|---|---|---|---|---|---|\n')
    tail = ('\n\n## 六、关闭记录（归档）\n\n'
            '| 编号 | 首次发现 | 关闭日 | 问题（摘要） | 关闭依据 |\n|---|---|---|---|---|\n'
            + (arch or '| — | — | — | — | — |') + '\n')
    return head + '\n'.join(rows) + tail


def trow(tid, status, days, note='依据。'):
    d = (TODAY - datetime.timedelta(days=days)).isoformat()
    return f'| {tid} | 2026-09-01 | 某问题 | 结构 | 采集 | {status} | {d} | {note} |'


class Test生命周期判定(unittest.TestCase):
    def tri(self, rows):
        return L.triage(ledger_text(rows), TODAY)

    def test_满90天归档_差一天不归档(self):
        r = self.tri([trow('T-1', '✅ 已关闭', 90), trow('T-2', '✅ 已关闭', 89)])
        self.assertEqual([c[0] for _i, c, _w in r['archive']], ['T-1'])

    def test_在办超三天退回_正好三天不退(self):
        r = self.tri([trow('T-1', '🟡 在办', 4), trow('T-2', '🟡 在办', 3)])
        self.assertEqual([c[0] for _i, c, _w in r['stale']], ['T-1'])

    def test_待验超七天提示(self):
        r = self.tri([trow('T-1', '⏳ 待验', 8), trow('T-2', '⏳ 待验', 7)])
        self.assertEqual([c[0] for _i, c, _w in r['overdue']], ['T-1'])

    def test_观察窗口到期才报(self):
        r = self.tri([trow('T-1', '🆕 待办', 0, '观察窗口 **2026-09**：核立法计划'),
                      trow('T-2', '🆕 待办', 0, '观察窗口 **2026-12**：核立法计划')])
        self.assertEqual([c[0] for _i, c, _w in r['observe']], ['T-1'])

    def test_不在未闭环项的行不参与(self):
        """放错节的行由 check_ledger_shape 报，这里不重复判——两处判就要改两处。"""
        text = ledger_text([trow('T-1', '✅ 已关闭', 200)])
        wrong = '## 五、清欠进度\n\n' + trow('T-9', '✅ 已关闭', 300) + '\n\n'
        text = text.replace('## 六、关闭记录（归档）', wrong + '## 六、关闭记录（归档）')
        got = [c[0] for _i, c, _w in L.triage(text, TODAY)['archive']]
        self.assertEqual(got, ['T-1'])


class Test清理动作(unittest.TestCase):
    def run_action(self, text, *args):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '任务台账.md'
            p.write_text(text, encoding='utf-8')
            with mock.patch.object(A, 'LEDGER', p):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = A.run(list(args))
                return code, p.read_text(encoding='utf-8')

    def test_不加apply不写盘(self):
        text = ledger_text([trow('T-20260101-01', '✅ 已关闭', 200)])
        _code, out = self.run_action(text)
        self.assertEqual(out, text, '只看不该动文件')

    def test_归档把行搬进第六节并留汇总(self):
        text = ledger_text([trow('T-20260101-01', '✅ 已关闭', 200)])
        _code, out = self.run_action(text, '--apply')
        sec2, sec6 = out.split('## 六、关闭记录')
        self.assertNotIn('| T-20260101-01 |', sec2.split('> **已归档**')[0])
        self.assertIn('T-20260101-01', sec6, '整行必须进第六节')
        self.assertIn('> **已归档**', sec2, '未闭环项要留一行汇总，否则读者以为丢了')

    def test_退回改状态并写原因(self):
        text = ledger_text([trow('T-20260101-02', '🟡 在办', 5)])
        _code, out = self.run_action(text, '--apply')
        self.assertIn('🆕 待办', out)
        self.assertIn('退回 🆕', out)

    def test_再跑一次是空的(self):
        text = ledger_text([trow('T-20260101-01', '✅ 已关闭', 200)])
        _code, once = self.run_action(text, '--apply')
        _code, twice = self.run_action(once, '--apply')
        self.assertEqual(twice, once, '幂等：没有可清的就不写盘')

    def test_归档后结构判据仍通过(self):
        text = ledger_text([trow('T-20260101-01', '✅ 已关闭', 200)])
        _code, out = self.run_action(text, '--apply')
        S.rep.errors.clear()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '任务台账.md'
            p.write_text(out, encoding='utf-8')
            with mock.patch.object(L, 'LEDGER', p):
                L.check_ledger_shape()
        self.assertEqual([m for _i, m in S.rep.errors], [])
