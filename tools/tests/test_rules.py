#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口径单测：黑名单、归档周名单、字段枚举、卡→领域映射。

这些是「改一处就漂」的高危口径。历史上黑名单两份清单漂移过，
归档周豁免两套判据并存过——这里把它们钉住。

跑法：python3 -m unittest discover -s tools/tests
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks.docs import _state as S            # noqa: E402
from pkb.checks.docs import consistency as C      # noqa: E402
from pkb.checks.docs import declared as D         # noqa: E402
from pkb.checks.docs import hygiene as H          # noqa: E402
from pkb.core import TEMPLATE_DIR                 # noqa: E402
from pkb.domain import (BLACK, BAD_SUBJECT, is_bad, DOMAINS, STAT_DOMAINS,  # noqa: E402
                        IMPACTS, STATUSES, REQUIRED_FIELDS, FIELD_MAP, LEGACY_WEEKS,
                        IMPACT_SINCE, ANALYSIS_TYPES, ANALYSIS_SPINE,
                        ANALYSIS_WORD_LIMIT, STANCES, STANCE_MIN)

CARD_TEMPLATE = TEMPLATE_DIR / '政策卡片模板.md'


class TestBlacklist(unittest.TestCase):
    def test_用户明确排除的两家必须在名单里(self):
        self.assertIn('jiemian.com', BLACK)
        self.assertTrue(is_bad('https://www.jiemian.com/article/1.html'))

    def test_聚合页与自媒体命中(self):
        for url in ('https://www.toutiao.com/a1', 'https://mp.weixin.qq.com/s/x',
                    'https://xueqiu.com/1', 'https://guba.eastmoney.com/x'):
            self.assertTrue(is_bad(url), url)

    def test_官网不命中(self):
        for url in ('https://www.ndrc.gov.cn/xxgk/zcfb/tz/202610/t1.html',
                    'https://www.gov.cn/zhengce/content/2026-10/25/content_1.htm'):
            self.assertFalse(is_bad(url), url)

    def test_主体关键词非空(self):
        self.assertIn('界面新闻', BAD_SUBJECT)
        self.assertIn('中华网', BAD_SUBJECT)


class TestLegacy(unittest.TestCase):
    def test_名单只含规则变更前的三周(self):
        self.assertEqual(LEGACY_WEEKS, frozenset({'2026-W39', '2026-W40', '2026-W41'}))

    def test_新周不得进名单(self):
        for wk in ('2026-W42', '2026-W43', '2026-W52'):
            self.assertNotIn(wk, LEGACY_WEEKS)

    def test_影响列生效周是固定时点(self):
        # 固定时点，不是滑动窗口：滑动窗口会让旧篇随时间自动合格。
        # 2026-10-28 撤掉判断编号后这一条仍要守——三档本身还在判。
        self.assertEqual(IMPACT_SINCE, '2026-W43')


class Test必备节(unittest.TestCase):
    """必备节只剩第二节（2026-10-28 撤掉第八节这条线）。

    保留这条断言的理由：**撤线不等于放宽结构**。第八节不再是新篇的必需品，
    但「第二节在不在」仍要拦；且 `check_week_sections` 仍按模板逐节比对，
    少写任何一节都会被那一项抓住。
    """
    OLD = '## 二、本周政策信号\n## 七、下周关注\n'

    def test_缺第二节要报(self):
        from pkb.checks.weeks import _missing_head
        self.assertEqual(_missing_head('## 七、下周关注\n', '2026-W50'), '二、本周政策信号')

    def test_第八节不再是必需品(self):
        from pkb.checks.weeks import _missing_head
        self.assertIsNone(_missing_head(self.OLD, '2026-W50'))

    def test_有第八节也不报(self):
        from pkb.checks.weeks import _missing_head
        text = '## 二、本周政策信号\n## 八、本周可证伪判断\n'
        self.assertIsNone(_missing_head(text, '2026-W50'))

    def test_缺第二节优先报(self):
        from pkb.checks.weeks import _missing_head
        self.assertEqual(_missing_head('## 八、x', '2026-W50'), '二、本周政策信号')


class TestFields(unittest.TestCase):
    def test_五领域与统计四领域(self):
        self.assertEqual(len(DOMAINS), 5)
        self.assertEqual(set(STAT_DOMAINS), set(DOMAINS) - {'总体规划'})
        self.assertEqual(len(STAT_DOMAINS), 4)

    def test_影响与状态枚举(self):
        self.assertEqual(IMPACTS, frozenset({'高', '中', '低'}))
        self.assertIn('已废止', STATUSES)

    def test_必填字段十四项且不重复(self):
        self.assertEqual(len(REQUIRED_FIELDS), 14)
        self.assertEqual(len(set(REQUIRED_FIELDS)), 14)
        for f in ('名称', '领域', '政策数', '所属政策链', 'tags'):
            self.assertIn(f, REQUIRED_FIELDS)


class TestChainMap(unittest.TestCase):
    def test_每张卡都有映射(self):
        self.assertEqual(len(FIELD_MAP), 33)

    def test_映射值必须是合法领域(self):
        # 这条钉子抓过一个真实 bug：顶层规划卡曾映射成「顶层规划」，而 DOMAINS 里是「总体规划」
        for card, domain in FIELD_MAP.items():
            self.assertIn(domain, DOMAINS, f'{card} → {domain} 不是合法领域')


class TestAnalysis(unittest.TestCase):
    def test_八节骨架(self):
        self.assertEqual(len(ANALYSIS_SPINE), 8)
        self.assertTrue(ANALYSIS_SPINE[3].endswith('、'))   # 第四节按类型定名，只校验前缀

    def test_类型与字数上限(self):
        self.assertEqual(ANALYSIS_WORD_LIMIT, 8000)
        self.assertIn('专题评估', ANALYSIS_TYPES)


class TestDomainGuard(unittest.TestCase):
    """口径单源扫描器（设计规则三的执行者）自测。

    扫描器本身如果永远报绿，就等于没有——所以这里钉三条：
    词典确实覆盖了名单、字段名不被误当口径、docstring 里的举例不算违规。
    """

    def test_词典覆盖黑名单与归档周(self):
        from pkb.checks.docs.literals import guarded_literals
        guard = guarded_literals()
        for k in BLACK:
            self.assertEqual(guard.get(k), 'BLACK', f'{k} 未被扫描覆盖')
        for wk in LEGACY_WEEKS:
            self.assertEqual(guard.get(wk), 'LEGACY_WEEKS', f'{wk} 未被扫描覆盖')

    def test_字段名不进词典(self):
        # 字段名是「读数据的键」，不是口径；进词典会逼所有人写 fm.get(KEY['领域'])
        from pkb.checks.docs.literals import guarded_literals
        guard = guarded_literals()
        for f in REQUIRED_FIELDS:
            self.assertNotIn(f, guard, f'字段名 {f} 不该当地雷')

    def test_只认代码常量不认注释与整句(self):
        import tempfile
        import textwrap
        from pkb.checks.docs.literals import code_strings
        src = textwrap.dedent('''
            """说明：'jiemian.com' 不许硬编码。"""
            # 注释里的 '2026-W40' 也不算违规
            A = 'jiemian.com'
            B = f'应为 2026-W40'
        ''')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sample.py'
            p.write_text(src, encoding='utf-8')
            vals = [v for _, v in code_strings(p)]
        self.assertIn('jiemian.com', vals)                 # 裸常量：命中
        self.assertNotIn('2026-W40', vals)                 # 只在整句里出现：不算抄口径
        self.assertFalse([v for v in vals if '不许硬编码' in v], 'docstring 被当成代码了')


if __name__ == '__main__':
    unittest.main()


def _const_check(agents):
    """跑一次结构常量判据，返回 (errors, oks)。"""
    S.rep.errors.clear()
    S.rep.warns.clear()
    S.rep.oks.clear()
    C.check_structure_numbers({'AGENTS': agents})
    return [m for _i, m in S.rep.errors], list(S.rep.oks)


class Test结构常量(unittest.TestCase):
    """「结构常量」是全库唯一被允许写死数字的一句，写错必须报。

    2026-10-26 审计发现它写着「7 节」而周观点早已八节——**没人拿它跟模板比**。
    判据写好后又发现第一版正则没穿过 `**结构常量**（…）`，四项比对一条都没跑，
    却打印「一致」：**判据静默失效比文档写错更糟**。所以这里连「取不到就报错」一起测。
    """

    def test_节数写错要报(self):
        # 2026-10-28 起周观点是七节，八节（带「可证伪判断」的那版）已撤
        errs, _o = _const_check('- **结构常量**（33 张产业卡、15 条索引链、八节、七字段）')
        self.assertTrue(any('周观点' in e and '节' in e for e in errs), errs)

    def test_卡数写错要报(self):
        errs, _o = _const_check('- **结构常量**（32 张产业卡、15 条索引链、八节、七字段）')
        self.assertTrue(any('张产业卡' in e for e in errs), errs)

    def test_句子被删要报而不是放过(self):
        errs, _o = _const_check('这句话没了')
        self.assertTrue(any('无法校验' in e for e in errs), errs)

    def test_正确写法不报且给出实测值(self):
        errs, oks = _const_check('- **结构常量**（33 张产业卡、15 条索引链、七节、七字段）')
        self.assertEqual(errs, [])
        self.assertTrue(any('张产业卡 33' in o for o in oks), oks)


class Test结构数字扫全文档(unittest.TestCase):
    """同一个结构数字散在多份文档里，只校验 AGENTS 那一句等于其余各处无人看管。

    2026-10-26 实测：AGENTS、index、政策速览、专家定义四份共 20 余处写法，
    旧实现只比对 AGENTS 的「结构常量」那一句。这里钉住三条：
    ① 非 AGENTS 的文档写错也要报，且**报出文件与行号**（不然知道错不知改哪儿）；
    ② 台账/报告里的历史数字不许被当成错（那是记录，改了就是篡改）；
    ③ 一处也扫不到时要报判据失效，不能打「通过」。
    """

    def _run(self, docs):
        S.rep.errors.clear()
        S.rep.warns.clear()
        S.rep.oks.clear()
        C.check_structure_numbers(docs)
        return [m for _i, m in S.rep.errors], list(S.rep.oks)

    def test_别的文档写错要报出文件与行号(self):
        errs, _o = self._run({'AGENTS': '- **结构常量**（33 张产业卡、15 条索引链、八节、七字段）',
                              'index': '第一行\n共 31 张产业卡，一产业一卡。\n'})
        hit = [e for e in errs if '张产业卡' in e and '31' in e]
        self.assertTrue(hit, errs)
        self.assertIn('第 2 行', hit[0])

    def test_受控词与字段也一起比(self):
        """字段数写错的典型：2026-10-27 由八字段并为七字段，旧写法此后就是错的。"""
        errs, _o = self._run({'AGENTS': '见 30 个受控词与八字段\n'})
        self.assertTrue(any('个受控词' in e for e in errs), errs)
        self.assertTrue(any('个信号字段' in e for e in errs), errs)

    def test_历史快照不进扫描范围(self):
        """体检报告里「138 张卡」是当时的记录，不该被要求改成现在的数。"""
        errs, _o = self._run({'AGENTS': '33 张产业卡\n',
                              '体检报告': '停在 2026-10-18，写着 138 张卡／60 个词\n'})
        self.assertFalse([e for e in errs if '138' in e], errs)

    def test_一处都扫不到要报判据失效(self):
        errs, _o = self._run({'AGENTS': '没有任何数字。\n'})
        self.assertTrue(any('判据失效' in e for e in errs), errs)


class Test时刻与log类型(unittest.TestCase):
    """两条 2026-10-29 新增的判据：四个任务的时刻、log 类型白名单。

    它们存在的理由相同——把「同一件事写两处」收成一处之后，剩下那一份必须有人看着，
    否则「收口」只是把两份副本改成一份无人校验的抄件。
    """

    def _run(self, fn, docs):
        S.rep.errors.clear()
        S.rep.warns.clear()
        S.rep.oks.clear()
        fn(docs)
        return [m for _i, m in S.rep.errors], list(S.rep.oks)

    def test_时刻分家要报(self):
        ag = '## 一、产出物与频率\n\n| 产出物 | 频率 | 落点 | 生产者 |\n|---|---|---|---|\n' \
             '| 产业卡 | 每日 **09:00** | a | 采集自动化 |\n'
        st = '## 一、当前状态\n\n| 任务 | 自动化 | 节拍 | 最近运行 |\n|---|---|---|---|\n' \
             '| 采集 | d1ca26c1 | 每日 09:30 | 2026-10-28 09:00 |\n'
        errs, _o = self._run(D.check_times, {'AGENTS': ag, '运行状态': st})
        self.assertTrue(any('09:30' in e for e in errs), errs)
        self.assertTrue(any('09:00' in e for e in errs), errs)

    def test_时刻一致不报(self):
        ag = '## 一、产出物与频率\n\n| 产出物 | 频率 | 落点 | 生产者 |\n|---|---|---|---|\n' \
             '| 体检报告 | 每 2 天 **22:00** | a | 体检自动化 |\n'
        st = '## 一、当前状态\n\n| 任务 | 自动化 | 节拍 | 最近运行 |\n|---|---|---|---|\n' \
             '| 体检 | 96885a01 | **每 2 天 22:00** | 2026-10-28 22:05 |\n'
        errs, oks = self._run(D.check_times, {'AGENTS': ag, '运行状态': st})
        self.assertFalse(errs, errs)
        self.assertTrue(any('时刻一致' in o for o in oks), oks)

    def test_只取节拍列不取最近运行(self):
        """最近运行那一栏写着 22:05，不该被当成节拍——否则每次运行都报分家。"""
        ag = '## 一、产出物与频率\n\n| 产出物 | 频率 | 落点 | 生产者 |\n|---|---|---|---|\n' \
             '| 体检报告 | 每 2 天 **22:00** | a | 体检自动化 |\n'
        st = '## 一、当前状态\n\n| 任务 | 自动化 | 节拍 | 最近运行 |\n|---|---|---|---|\n' \
             '| 体检 | 96885a01 | 每 2 天 22:00 | 2026-10-28 22:05 |\n'
        errs, _o = self._run(D.check_times, {'AGENTS': ag, '运行状态': st})
        self.assertFalse(errs, errs)

    def test_log类型写错要报(self):
        errs, _o = self._run(H.check_types_declared,
                             {'AGENTS': '类型限 `决策／采集／体检／观点` 四种'})
        self.assertTrue(any('事故' in e or '同步' in e for e in errs), errs)

    def test_log类型对得上不报(self):
        errs, oks = self._run(H.check_types_declared,
                              {'AGENTS': '类型限 `决策／采集／体检／观点／事故` 五种'})
        self.assertFalse(errs, errs)
        self.assertTrue(any('log 类型' in o for o in oks), oks)

    def test_找不到那串要报判据失效(self):
        errs, _o = self._run(H.check_types_declared, {'AGENTS': '没有那句话\n'})
        self.assertTrue(any('判据' in e or '类型' in e for e in errs), errs)


class Test立场类别同步(unittest.TestCase):
    """「至少覆盖 3 类主体（官方解读／市场主体／产业方／学术界／国际视角／舆论）」这条口径
    2026-10-29 起只写在 `templates/政策卡片模板.md`（AGENTS 第六节的七要素表已删，
    改为指向模板）。**名字从模板现读、不在代码里存第二份**——它会加长，两份不同步时谁都不报错。"""

    def test_与卡片模板同集合(self):
        text = CARD_TEMPLATE.read_text(encoding='utf-8')
        m = re.search(r'至少覆盖 (\d+) 类主体\*{0,2}（(.+?)）', text)
        self.assertTrue(m, '模板里找不到「至少覆盖 N 类主体（…）」——判据失效，须同步本测试')
        self.assertEqual(int(m.group(1)), STANCE_MIN)
        self.assertEqual(set(m.group(2).split('／')), set(STANCES))

    def test_没有空值或重复(self):
        self.assertEqual(len(set(STANCES)), len(STANCES))
        self.assertFalse([x for x in STANCES if not x.strip()])
