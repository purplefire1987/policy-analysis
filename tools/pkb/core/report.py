#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输出与摘要契约。

两种输出模式，各管一处：
* 立即打印（ok/err/warn/info/section）适合流水线式脚本；
* 收集式（Reporter）适合按类别汇总判定的校验器。

摘要契约也在这里实现一次：每个 check 结束前输出一行 `▸摘要:`，
`run.py check` 只抓这一行。
"""
from dataclasses import dataclass, field
from enum import Enum

# ── 输出：四个前缀，全库一致 ─────────────────────────────────────────
def ok(msg):
    print(f'  OK   {msg}')


def err(msg):
    print(f'  ✗    {msg}')


def warn(msg):
    print(f'  !    {msg}')


def info(msg):
    print(f'       {msg}')


def section(title):
    print(f'\n【{title}】')


def banner(title):
    """动作输出的整屏横幅（`\n====` / 标题 / `====`）。

    为什么在共用层：`check`／`fix`／`list` 三个动作原本各写一份一模一样的
    四行函数——改宽度要改三处，漏一处就两种宽度并存。
    """
    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)


# 摘要行契约：每个 check 脚本结束前输出一行 `▸摘要: …`，
# `run.py check` 只抓这一行（抓不到才退回正则）。
# 为什么要有契约：2026-10-25 前入口靠「第一行含覆盖率/OK 等词」猜摘要，
# 结果 check_views 抓到的是小节标题「=== 观点覆盖率 ===」、周覆盖抓到表头，
# 最关键的数字在入口输出里根本看不见——省 token 省成了信息黑洞。
SUMMARY_MARK = '▸摘要:'


def summary(msg):
    """本脚本的一句话结论。入口只认这一行。"""
    print(f'{SUMMARY_MARK} {msg}')


# ── 判定：退出码从裸 int 变成有语义的枚举 ──────────────────────────
class Verdict(Enum):
    """一次检查的结论类型。

    为什么不用 int：2026-10-25 前 0/1/2 三种语义挤在一个 int 里，
    check_week_coverage 用 2 表示「文件不存在」、run.py 用 2 表示「没有脚本认领参数」，
    同一个 2 两种含义，体检提示词只能额外写一段解释「exit 2 有两种可能」。
    """
    PASS = 0        # 通过
    FAIL = 1        # 有问题，必须处置
    BAD_INPUT = 2   # 参数/输入缺失，结论不成立
    SKIP = 3        # 按规则豁免（归档周等），不计入

    @property
    def code(self):
        return self.value


@dataclass
class Result:
    """一次检查的完整产出：结论 + 一行摘要 + 明细。

    summary 没有默认值——不填就构造失败，于是「有退出码没摘要」从设计上写不出来。
    明细放 lines，由调用层决定打不打（--only／--full），checks 自己不打印。
    """
    verdict: Verdict
    summary: str
    lines: list = field(default_factory=list)

    @property
    def code(self):
        return self.verdict.code


# ── 收集式输出：先记账、末尾统一打印 ────────────────────────────────
class Reporter:
    """给「先收集、最后统一输出」的校验脚本用（check_docs / check_analysis 等）。

    与上面的 ok/err/warn（立即打印）是两种输出模式，各管一处：
    立即打印适合流水线式脚本，收集式适合按类别汇总判定的校验器。
    """

    def __init__(self):
        self.oks, self.warns, self.errors = [], [], []

    def ok(self, msg):
        self.oks.append(msg)

    def warn(self, item, msg):
        self.warns.append((item, msg))

    def err(self, item, msg):
        self.errors.append((item, msg))

    def has_err_on(self, item):
        return any(e[0] == item for e in self.errors)

    def to_lines(self, quiet=False):
        """渲染成行列表（不打印）——checks 把它塞进 Result.lines，由 action 决定打印。"""
        out = []
        if not quiet:
            out += [f'  OK  {m}' for m in self.oks]
        out += [f'  ✗  [{i}] {m}' for i, m in self.errors]
        out += [f'  ·  [{i}] {m}' for i, m in self.warns]
        return out
