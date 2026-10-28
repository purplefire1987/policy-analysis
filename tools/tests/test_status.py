#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`status` 的灯：只读「当前状态」一节，四档都认，取不到不崩。

为什么测这个（2026-10-28 晚）：加第四个自动化时给运行状态补了「归档索引」行
（灯填 `—`）、又在「运行记录」里写了一句「2 条提示＝采集健康🟡」，
`status` 当场 StopIteration 全崩。两个原因叠在一起：

1. `lights()` 全文扫 `|` 行，把运行记录当成了状态表——那张表的灯在正文里，不在格子里；
2. 用 `next(...)` 取灯，取不到就抛异常，把整条命令带下去。

`status` 是 AGENTS 三条命令之一、也是自动化开工第一条，它一崩就什么都读不到。
所以这三条各配一个反例：分节、四档、格式坏。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.actions import status as S      # noqa: E402

HEAD = ('# 运行状态\n\n## 一、当前状态（每次运行覆盖）\n\n'
        '| 任务 | 自动化 | 节拍 | 最近运行 | 退出码 | 本轮产出 | 遗留 | 灯 |\n'
        '|---|---|---|---|---|---|---|---|\n')

TAIL = ('\n## 二、运行记录（倒序追加）\n\n'
        '| 时间 | 任务 | 结果 | 退出码 | 产出／遗留 |\n'
        '|---|---|---|---|---|\n'
        '| 2026-10-28 | 体检（第六次） | ✅ | 0 | check 全绿（2 条提示＝采集健康🟡） |\n')


class TestLights(unittest.TestCase):
    def _lights(self, body):
        d = Path(tempfile.mkdtemp())
        p = d / '运行状态.md'
        p.write_text(body, encoding='utf-8')
        with mock.patch.object(S, 'STATUS', p):
            return S.lights()

    def test_只读当前状态一节_流水的灯不算(self):
        """运行记录里那句「采集健康🟡」不该出现在结果里。

        反例就是这次的事故：全文扫时期望 2 行、实得 3 行，第三行还取不到灯。
        """
        body = (HEAD +
                '| 采集 | d1ca26c1 | 每日 09:00 | 2026-10-28 | 0 | 政策 0 条 | 无 | 🟡 |\n'
                '| 体检 | 96885a01 | 每 2 天 22:00 | 2026-10-28 | 0 | 体检报告 | 无 | 🟢 |\n' +
                TAIL)
        self.assertEqual(self._lights(body), ['采集 🟡', '体检 🟢'])

    def test_未到首跑时间的破折号是合法灯(self):
        """新建任务用 `—` 表示「还没到首跑」——运行状态 §一 的判定表这么定的，
        代码必须认，否则第四个自动化一上线就让 status 崩。"""
        body = HEAD + '| 归档索引 | da7f747a | 周日 21:00 | — | — | 未运行 | 无 | — |\n'
        self.assertEqual(self._lights(body), ['归档索引 —'])

    def test_灯没填不崩只标出来(self):
        """格式坏要看得见，但不能一错全黑：`（灯未填）` 是提示，不是异常。"""
        body = HEAD + '| 采集 | d1ca26c1 | 每日 09:00 | 2026-10-28 | 0 | 政策 0 条 | 无 | 忘了 |\n'
        self.assertEqual(self._lights(body), ['采集 （灯未填）'])

    def test_没有本页时给空表(self):
        with mock.patch.object(S, 'STATUS', Path('/nonexistent/运行状态.md')):
            self.assertEqual(S.lights(), [])


if __name__ == '__main__':
    unittest.main()
