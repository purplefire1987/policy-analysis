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

COLS = ('| 编号 | 首次发现 | 问题 | 类型 | 负责环节 | 状态 | 最近更新 | 关闭依据与下一步 |\n'
        '|---|---|---|---|---|---|---|---|\n')

# 两张表都要在（2026-10-28 起「负责人」是表名而不是一列），所以最小台账也得先立两张空表。
HEAD = ('# 任务台账\n\n## 二、未闭环项\n\n'
        '### 2a 机器在办（负责人＝机器）\n\n' + COLS +
        '\n### 2b 等你拍板（负责人＝用户）\n\n' + COLS)


def row(tid, status='🆕 待办'):
    """一行未闭环项。接在 HEAD 后面＝落在「等你拍板」那张表里（结构判据不看归属）。"""
    return (f'| {tid} | 2026-10-26 | 某问题 | 结构 | 采集 | {status} '
            f'| 2026-10-26 | 待办 |')


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


def ledger_text(rows, arch=None, user_rows=()):
    """一份最小台账：两张表齐全，加「关闭记录」一节，够判生命周期。

    行落在哪张表由调用方说清楚（`rows` 进机器表、`user_rows` 进等你拍板表）——
    归属正是这一版要判的东西，测试夹具不该含糊。
    """
    body = ('# 任务台账\n\n## 二、未闭环项\n\n'
            '### 2a 机器在办（负责人＝机器）\n\n' + COLS + '\n'.join(rows) + '\n\n'
            '### 2b 等你拍板（负责人＝用户）\n\n' + COLS + '\n'.join(user_rows) + '\n')
    tail = ('\n## 六、关闭记录（归档）\n\n'
            '| 编号 | 首次发现 | 关闭日 | 问题（摘要） | 关闭依据 |\n|---|---|---|---|---|\n'
            + (arch or '| — | — | — | — | — |') + '\n')
    return body + tail


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


def values(text):
    """跑一次取值判据，返回 (errors, oks)。"""
    S.rep.oks.clear()
    S.rep.errors.clear()
    S.rep.warns.clear()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / '任务台账.md'
        p.write_text(text, encoding='utf-8')
        with mock.patch.object(L, 'LEDGER', p):
            L.check_ledger_values()
    return [m for _i, m in S.rep.errors], list(S.rep.oks)


class Test取值合规(unittest.TestCase):
    """类型与负责环节写错不会报错，只会让那一行不再被读——所以每条都要有反例。"""

    def test_正常取值不报(self):
        errs, oks = values(ledger_text([trow('T-1', '🆕 待办', 1)]))
        self.assertEqual(errs, [])
        self.assertTrue(any('取值合规' in o for o in oks), oks)

    def test_类型写错要报出行号与取值表(self):
        bad = '| T-2 | 2026-09-01 | 某问题 | 结构问题 | 采集 | 🆕 待办 | 2026-10-26 | 依据。 |'
        text = ledger_text([bad])
        errs, _o = values(text)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn('类型', errs[0])
        self.assertIn('结构问题', errs[0])
        line = text.split('\n').index(bad) + 1     # 行号按夹具现算，钉死数字会被改布局绊倒
        self.assertIn(f'第 {line} 行', errs[0])

    def test_负责环节写错要说明后果(self):
        bad = '| T-3 | 2026-09-01 | 某问题 | 结构 | 采集入库 | 🆕 待办 | 2026-10-26 | 依据。 |'
        errs, _o = values(ledger_text([bad]))
        self.assertEqual(len(errs), 1, errs)
        self.assertIn('负责环节', errs[0])
        self.assertIn('不再被读', errs[0])

    def test_两列都错各报一条(self):
        bad = '| T-4 | 2026-09-01 | 某问题 | 结构错 | 采集入库 | 🆕 待办 | 2026-10-26 | 依据。 |'
        errs, _o = values(ledger_text([bad]))
        self.assertEqual(len(errs), 2, errs)

    def test_关闭记录五列不参与(self):
        arch = '| T-9 | 2026-08-01 | 2026-08-02 | 某问题 | 依据。 |'
        errs, _o = values(ledger_text([trow('T-1', '🆕 待办', 1)], arch))
        self.assertEqual(errs, [])

    def test_空台账只提示(self):
        errs, _o = values('')
        self.assertEqual(errs, [])


QUEUE_HEAD = ('# 任务台账\n\n## 四、存量补采队列（信号页断档 > 14 天）\n\n'
              '| 页 | 首次空白日 | 已补至 | 剩余天数 | 最近领取 | 状态 |\n'
              '|---|---|---|---|---|---|\n')


def task_text(*queues):
    return QUEUE_HEAD + '\n'.join(queues) + '\n'


def report_text(*sections):
    return ('# 知识库体检报告\n\n## 二、历次检查记录（只追加）\n\n' + '\n'.join(sections)
            + '\n\n### 下一轮（2026-10-26 22:00）应核对的事项\n\n占位不是一次体检。\n')


def release(report, ledger):
    """跑一次释放留痕判据，返回 (errors, warns, oks)。"""
    S.rep.oks.clear()
    S.rep.errors.clear()
    S.rep.warns.clear()
    with tempfile.TemporaryDirectory() as d:
        rp = Path(d) / '体检报告.md'
        tp = Path(d) / '任务台账.md'
        rp.write_text(report, encoding='utf-8')
        tp.write_text(ledger, encoding='utf-8')
        with mock.patch.object(L, 'CHECK_REPORT', rp), mock.patch.object(L, 'LEDGER', tp):
            L.check_release_logged()
    return ([m for _i, m in S.rep.errors], [m for _i, m in S.rep.warns], list(S.rep.oks))


class Test释放留痕(unittest.TestCase):
    """体检报告自己写着「每节末尾要写本次释放的页／批次」，此前没有任何判据。"""

    Q = ('| 国防军事 | 2026-08-08 | 2026-08-21 | 66 | 2026-10-25 | 补采中 |\n'
         '| 科技创新 | 2026-09-30 | — | 27 | — | 待领 |')

    def test_写了释放且台账已记领取(self):
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n| **本期释放** | 存量补采「国防军事」页 |')
        errs, warns, oks = release(rep, task_text(self.Q))
        self.assertEqual((errs, warns), ([], []))
        self.assertTrue(any('国防军事' in o for o in oks), oks)

    def test_没写释放要报(self):
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n本次各项全绿。')
        errs, _w, _o = release(rep, task_text(self.Q))
        self.assertEqual(len(errs), 1, errs)
        self.assertIn('释放', errs[0])

    def test_写了释放但台账没记领取要报(self):
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n| **本期释放** | 「科技创新」页 |')
        errs, _w, _o = release(rep, task_text(self.Q))
        self.assertTrue(any('说了没记' in e for e in errs), errs)

    def test_领取日早于体检日也算没记(self):
        q = '| 国防军事 | 2026-08-08 | 2026-08-21 | 66 | 2026-10-20 | 补采中 |'
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n| **本期释放** | 「国防军事」页 |')
        errs, _w, _o = release(rep, task_text(q))
        self.assertTrue(any('说了没记' in e for e in errs), errs)

    def test_整节提到三个页名不算三次释放(self):
        """10-24 那节先列三页纳入规则、再说释放最旧的那页——只认宾语位置。"""
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n'
                          '- 三页纳入规则：国防军事／区域经济／科技创新，本期释放最旧的国防军事页。')
        errs, warns, _o = release(rep, task_text(self.Q + '\n| 区域经济 | 2026-09-21 | 2026-09-24 | 32 | — | 待领 |'))
        self.assertEqual((errs, warns), ([], []), (errs, warns))

    def test_写本期不释放但有未领页要提示(self):
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n本期不释放（队列无待领页）。')
        errs, warns, _o = release(rep, task_text(self.Q))
        self.assertEqual(errs, [])
        self.assertTrue(any('不释放' in w and '科技创新' in w for w in warns), warns)

    def test_写本期不释放且队列已清零通过(self):
        q = '| 国防军事 | 2026-08-08 | 2026-08-21 | 0 | 2026-10-25 | ✅ |'
        rep = report_text('### 2026-10-24 23:09 — 第四次\n\n本期不释放。')
        errs, warns, oks = release(rep, task_text(q))
        self.assertEqual((errs, warns), ([], []))
        self.assertTrue(any('不释放' in o for o in oks), oks)

    def test_占位标题不算最新一节(self):
        rep = ('# 知识库体检报告\n\n## 二、历次检查记录\n\n'
               '### 下一轮（2026-10-30）应核对的事项\n\n本期不释放。\n')
        _e, warns, _o = release(rep, task_text(self.Q))
        self.assertTrue(any('读不到' in w for w in warns), warns)



class Test两张表(unittest.TestCase):
    """「负责人」不是一列，是两张表（2026-10-28 改）。

    为什么测：一列可以填错而无人知——那一行从此被当成机器的事埋着。表名写错的形态
    更糟：**那张表整个不存在**，行要么落进另一张表、要么无处可去，`plan` 的【1b】空着，
    看着像「没有等你拍板的事」。
    """

    def test_缺一张表要报(self):
        text = ('# 任务台账\n\n## 二、未闭环项\n\n'
                '### 2a 机器在办（负责人＝机器）\n\n' + COLS + row('T-1') + '\n')
        errs, _w = judge(text)
        self.assertTrue(any('负责人＝用户' in e for e in errs), errs)

    def test_表名没写负责人要报(self):
        text = ('# 任务台账\n\n## 二、未闭环项\n\n'
                '### 机器在办\n\n' + COLS + row('T-1') + '\n\n'
                '### 2b 等你拍板（负责人＝用户）\n\n' + COLS)
        errs, _w = judge(text)
        self.assertTrue(any('没写「负责人' in e for e in errs), errs)

    def test_两张表都在就不报(self):
        errs, _w = judge(HEAD + row('T-1') + '\n')
        self.assertEqual(errs, [])


class Test表头契约(unittest.TestCase):
    """表头必须与 `domain/ledger.LEDGER_COLS` 逐字一致。

    列序是三个模块（plan、checks、run.py ledger）的下标契约。表头改了代码没跟上，
    读出来的就是相邻列——不报错，只是读错。所以表头本身也得被校验，而且**两张表各校一次**。
    """

    def test_表头少一列要报(self):
        text = ('# 任务台账\n\n## 二、未闭环项\n\n'
                '### 2a 机器在办（负责人＝机器）\n\n'
                '| 编号 | 首次发现 | 问题 | 类型 | 负责环节 | 状态 | 最近更新 | 关闭依据 |\n'
                '|---|---|---|---|---|---|---|---|\n'
                '| T-1 | 2026-10-26 | 某问题 | 结构 | 采集 | 🆕 待办 | 2026-10-26 | 待办 |\n\n'
                '### 2b 等你拍板（负责人＝用户）\n\n' + COLS)
        errs, _w = judge(text)
        self.assertTrue(any('表头' in e for e in errs), errs)

    def test_表头与常量一致不报(self):
        errs, _w = judge(HEAD + row('T-20261028-09') + '\n')
        self.assertEqual(errs, [])
