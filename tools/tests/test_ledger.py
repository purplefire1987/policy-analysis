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

from pkb.checks.docs import _state as S        # noqa: E402
from pkb.checks.docs import ledger as L        # noqa: E402

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
