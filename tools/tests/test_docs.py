#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""log 卫生判据：新格式条目才受约束，历史条目豁免。

为什么历史豁免也要测：库里 30 多条 `## 2026-10-24` 式旧标题是既成事实，
不能为了让检查好看去改写历史——但也不能因为要放过它们，就连「新条目写错类型」
一起放过。2026-10-26 审计发现：类型白名单被拼进了识别正则，导致类型写错的
条目匹配不上、落进历史分支**静默通过**，那条 bad_type 分支从未触发过。
所以这里专列一条「类型写错要报」。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.docs import _state as S           # noqa: E402
from pkb.checks.docs import hygiene as H          # noqa: E402
from pkb.checks.docs.hygiene import LOG_MAX_LINES   # noqa: E402

OLD = '## 2026-10-24\n\n旧格式条目正文。\n'


def judge(text):
    """跑一次 log 判据，返回 (errors, warnings, oks) 的纯文本列表。"""
    S.rep.oks.clear()
    S.rep.errors.clear()
    S.rep.warns.clear()
    lines, heads = H._log_heads(text)
    entries, first_old = H._new_entries(lines, heads)
    H._judge_new(entries, first_old)
    return ([m for _i, m in S.rep.errors],
            [m for _i, m in S.rep.warns],
            list(S.rep.oks))


class Test新条目合规(unittest.TestCase):
    def test_合规条目只有OK(self):
        errs, _warns, oks = judge('## 2026-10-26 · 决策 · 改了注册表\n\n一句话。\n' + OLD)
        self.assertEqual(errs, [])
        self.assertTrue(any('均合规' in o for o in oks))

    def test_类型写错要报(self):
        """「巡检」不在五类里——必须报错，不能被当成历史条目放过。"""
        errs, _warns, _oks = judge('## 2026-10-26 · 巡检 · 随便写写\n\n正文。\n')
        self.assertTrue(any('类型不在白名单' in e for e in errs), errs)

    def test_五类都合法(self):
        for t in ('决策', '采集', '体检', '观点', '事故'):
            with self.subTest(type=t):
                errs, _w, _o = judge(f'## 2026-10-26 · {t} · 一句话\n\n正文。\n')
                self.assertEqual(errs, [])

    def test_未按日期倒序要报(self):
        text = ('## 2026-10-20 · 决策 · 早的\n\n正文。\n\n'
                '## 2026-10-26 · 决策 · 晚的\n\n正文。\n')
        errs, _w, _o = judge(text)
        self.assertTrue(any('倒序' in e for e in errs), errs)

    def test_新条目排在历史之后要报(self):
        text = OLD + '\n## 2026-10-26 · 决策 · 新条目\n\n正文。\n'
        errs, _w, _o = judge(text)
        self.assertTrue(any('追加到历史条目之后' in e for e in errs), errs)

    def test_单条超80行要报(self):
        body = '\n'.join(f'第 {i} 行' for i in range(LOG_MAX_LINES + 1))
        errs, _w, _o = judge(f'## 2026-10-26 · 决策 · 长条目\n\n{body}\n')
        self.assertTrue(any('超过 80 行' in e for e in errs), errs)


class Test历史豁免(unittest.TestCase):
    def test_旧格式一条都不报错(self):
        errs, _warns, _oks = judge(OLD)
        self.assertEqual(errs, [], '历史条目是既成事实，不能追溯判错')

    def test_没有新条目只提示(self):
        _e, warns, _o = judge(OLD)
        self.assertTrue(any('尚无合规新条目' in w for w in warns))

    def test_带范围的历史标题不算新条目(self):
        """`## 2026-10-05 ~ 2026-10-24 · 决策 · …` 是压缩后的历史条目。"""
        _e, warns, _o = judge('## 2026-10-05 ~ 2026-10-24 · 决策 · 31 项变更\n\n正文。\n')
        self.assertTrue(any('尚无合规新条目' in w for w in warns))


if __name__ == '__main__':
    unittest.main()
