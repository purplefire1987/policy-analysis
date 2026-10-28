#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构检查的两处易错判据：frontmatter 取原文、断链扫描的过滤规则。

为什么单测断链：它最容易「报一堆假警」——模板占位符 `[[政策链-XXX]]`、
表格里的 `[[页面\\|别名]]`、代码块里的示例，全都长得像断链。
假警一多，真断链就没人看了；反过来过滤太宽，真断链会被吞掉。
所以这里两侧都测：该报的报，该放过的放过。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import structure as S          # noqa: E402

CARD = '''---
名称: 能源
tags: [政策]
---
正文 [[政策卡片-甲]] 与 [[政策卡片-甲|甲卡]] 不算断链。
'''


class TestRawFmText(unittest.TestCase):
    def test_取出原文(self):
        got = S.raw_fm_text(CARD)
        self.assertIn('名称: 能源', got)
        self.assertNotIn('正文', got)

    def test_没有frontmatter返回空(self):
        self.assertEqual(S.raw_fm_text('只有正文\n'), '')


class Test断链过滤(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(S.issues.clear)

    def scan(self, files, names=('政策卡片-甲',)):
        for name, text in files.items():
            (self.root / name).write_text(text, encoding='utf-8')
        S.issues.clear()
        with mock.patch.object(S, 'VAULT', self.root):
            S.check_links(set(names))
        return [msg for _obj, msg in S.issues.get('6-断链', [])]

    def test_真断链要报(self):
        self.assertEqual(len(self.scan({'b.md': '见 [[不存在的页面]]\n'})), 1)

    def test_表格转义竖线不误报(self):
        got = self.scan({'b.md': '| [[政策卡片-甲\\|甲卡]] |\n'})
        self.assertEqual(got, [], '表格里的 \\| 是转义，目标仍是政策卡片-甲')

    def test_模板占位符不误报(self):
        got = self.scan({'t.md': '[[政策链-XXX]] [[页面名]] [[政策卡片-{名}]]\n'})
        self.assertEqual(got, [])

    def test_代码块内不扫描(self):
        got = self.scan({'t.md': '```\n[[示例链接]]\n```\n`[[行内示例]]`\n'})
        self.assertEqual(got, [])

    def test_同一文件多条都报(self):
        got = self.scan({'b.md': '[[甲不存在]] [[乙不存在]]\n'})
        self.assertEqual(len(got), 2)


if __name__ == '__main__':
    unittest.main()


class Test关键词(unittest.TestCase):
    """关键词是「只写不读」的典型：在必填表里，没有任何代码看它的值。

    实际盘点 33 张卡：18 行内数组、11 块式、4 张行内数组里混着 Markdown 列表号。
    三种写法一种脏值，而校验一条都没有——所以判据只认形态，不判选得准不准
    （选词是判断，脚本判了就是逼人凑数）。
    """

    def _kw(self, doc):
        fm, _b = S.parse_fm(doc)
        S.issues.clear()
        S.warns.clear()
        S._check_keywords('测试卡', fm, doc)
        return list(S.issues['1-frontmatter']), list(S.warns['1-frontmatter'])

    def test_行内数组不报(self):
        errs, warns = self._kw('---\n关键词: [甲, 乙, 丙]\n---\n')
        self.assertEqual((errs, warns), ([], []))

    def test_混进列表号的要报(self):
        errs, _w = self._kw('---\n关键词: [- 文化遗产, 旅游强国, 文旅融合]\n---\n')
        self.assertTrue(any('Markdown 列表号' in m for _o, m in errs), errs)

    def test_块式写法要报(self):
        errs, _w = self._kw('---\n关键词:\n  - 甲\n  - 乙\n  - 丙\n---\n')
        self.assertTrue(any('块式' in m for _o, m in errs), errs)

    def test_重复要报(self):
        errs, _w = self._kw('---\n关键词: [甲, 甲, 乙]\n---\n')
        self.assertTrue(any('重复' in m for _o, m in errs), errs)

    def test_太少只提示不阻断(self):
        errs, warns = self._kw('---\n关键词: [甲, 乙]\n---\n')
        self.assertEqual(errs, [])
        self.assertTrue(any('3 个' in m or '只有' in m for _o, m in warns), warns)


GOOD = '''---
关键词: [甲, 乙, 丙]
所属政策链: "[[政策链-能源]]"
---

# 能源

> [!info] 基本信息
> - 产业分类：能源
> - 最新政策：某政策（2026-10-01）
> - 所属政策链：[[政策链-能源]]
> - 发文机关：甲部、乙部
> - 关键词：甲、乙、丙

## 政策演进

### 2026-10-01 · 某政策

**发文机关**：甲部 ｜ **文号**：甲发〔2026〕1号 ｜ [政策原文](https://example.gov.cn/a)

- **生效日期**：2026-10-01

**核心要点**

1. 甲。

**变化性字眼**

- **首次**：相对某文件。

**与旧政策的关系**

新增。

**各方观点**

| 来源主体 | 立场属性 | 核心观点摘要 | 来源链接 |
|---|---|---|---|
| 甲 | 官方解读 | 略 | https://example.gov.cn |

**观点辨析**

略。

**影响判断**

- 影响对象：甲
- 影响程度：中
- 一句话判断：略。
'''


class Test模板合规(unittest.TestCase):
    """基本信息五项与每小节栏位：模板写了什么，就得有对应的检查点（2026-10-28）。

    为什么测：这两块此前**一条判据都没有**——callout 33 张全少两项、157 个政策小节
    的「文号」与「生效日期」栏一个都没有、13 处影响判断写成整段论述，全都不报错。
    模板要求而脚本不查的栏位，等于不存在。
    """

    def judge(self, doc):
        S.issues.clear()
        S.warns.clear()
        fm, body = S.parse_fm(doc)
        secs, _bad = S.extract_sections(body)
        S._check_info_box('能源', fm, body, secs)
        for d, t, chunk, _r in secs:
            S._check_section('能源', d, t, chunk)
        return ([m for _o, m in S.issues.get('1-frontmatter', [])],
                [m for _o, m in S.issues.get('3-小节', [])])

    def test_全齐不报(self):
        box, sec = self.judge(GOOD)
        self.assertEqual((box, sec), ([], []))

    def test_callout缺项要报(self):
        box, _s = self.judge(GOOD.replace('> - 关键词：甲、乙、丙\n', ''))
        self.assertTrue(any('关键词' in m for m in box), box)

    def test_最新政策与第一小节不符要报(self):
        box, _s = self.judge(GOOD.replace('某政策（2026-10-01）', '另一份（2026-09-01）'))
        self.assertTrue(any('最新政策' in m for m in box), box)

    def test_关键词与frontmatter不一致要报(self):
        box, _s = self.judge(GOOD.replace('> - 关键词：甲、乙、丙', '> - 关键词：甲、乙'))
        self.assertTrue(any('关键词' in m for m in box), box)

    def test_发文机关重复要报(self):
        box, _s = self.judge(GOOD.replace('甲部、乙部', '甲部、乙部、甲部'))
        self.assertTrue(any('重复' in m for m in box), box)

    def test_缺文号要报(self):
        _b, sec = self.judge(GOOD.replace(' ｜ **文号**：甲发〔2026〕1号', ''))
        self.assertTrue(any('文号' in m for m in sec), sec)

    def test_缺生效日期要报(self):
        _b, sec = self.judge(GOOD.replace('- **生效日期**：2026-10-01\n\n', ''))
        self.assertTrue(any('生效日期' in m for m in sec), sec)

    def test_影响判断缺三行要报(self):
        bad = GOOD.replace('- 影响对象：甲\n- 影响程度：中\n- 一句话判断：略。',
                           '- **财政端**：减少支出。')
        _b, sec = self.judge(bad)
        self.assertTrue(any('影响对象' in m for m in sec), sec)

    def test_有论述也有三行不报(self):
        ok = GOOD.replace('- 一句话判断：略。', '- 一句话判断：略。\n\n（以下为依据）\n- **财政端**：减少支出。')
        _b, sec = self.judge(ok)
        self.assertEqual(sec, [])

    def test_缺政策原文要报(self):
        _b, sec = self.judge(GOOD.replace(' ｜ [政策原文](https://example.gov.cn/a)', ''))
        self.assertTrue(any('政策原文' in m for m in sec), sec)

    def test_核心要点照抄标题只提示不阻断(self):
        _b, sec = self.judge(GOOD.replace('1. 甲。', '某政策'))
        self.assertEqual(sec, [], '照抄标题是质量问题，不该判成结构错误')
        self.assertTrue(any('复述' in m for _o, m in S.warns.get('3-质量', [])),
                        S.warns.get('3-质量'))


class Test序列卡(unittest.TestCase):
    """序列卡：主卡索引、卷名、卷内容三者必须说同一段时间（2026-10-28）。

    这三条都是「拆完才对得上」的判据——拆卷那一刻是对的，之后每一次新增都可能
    让它们悄悄错位：新加一卷忘了进索引，读者从主卡永远找不到；卷名写着 2026-10
    而里面躺着 9 月的政策，按日期找的人会直接略过。**都不会报错，只会让人找不到。**
    """

    def build(self, vols, listed):
        """vols: {卷名: [日期, ...]}；listed: 主卡索引里列出的卷名。"""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(d, ignore_errors=True))
        cd = d / '政策卡片'
        card = cd / '政策卡片-能源'
        card.mkdir(parents=True)
        main = card / '政策卡片-能源.md'
        rows = '\n'.join(f'| [[政策卡片-能源/{v}]] | x | 1 |' for v in listed)
        main.write_text('---\n类型: 政策卡片\n---\n\n# 能源\n\n## 政策演进\n\n' + rows + '\n',
                        encoding='utf-8')
        per = []
        for name, dates in vols.items():
            f = card / f'{name}.md'
            body = '\n'.join(f'### {dt} · 某政策\n\n正文\n' for dt in dates)
            f.write_text('# 能源\n\n## 政策演进\n\n' + body, encoding='utf-8')
            per.append({'path': f, 'size': len(body), 'secs': S.extract_sections(body)})
            per[-1]['secs'] = per[-1]['secs'][0]
        S.issues.clear()
        S.warns.clear()
        S._check_series('能源', main, main.read_text(encoding='utf-8'), per)
        return [m for _o, m in S.issues.get('7-序列', [])]

    def test_对得上不报(self):
        self.assertEqual(self.build({'2026-10': ['2026-10-09'], '2025-11至2026-09': ['2026-01-06']},
                                    ['2026-10', '2025-11至2026-09']), [])

    def test_卷没进索引要报(self):
        got = self.build({'2026-10': ['2026-10-09'], '2025-11至2026-09': ['2026-01-06']},
                         ['2026-10'])
        self.assertTrue(any('没进主卡索引' in m for m in got), got)

    def test_索引写了不存在的卷要报(self):
        got = self.build({'2026-10': ['2026-10-09']}, ['2026-10', '2026-11'])
        self.assertTrue(any('没有这个文件' in m for m in got), got)

    def test_卷名区间与内容不符要报(self):
        """卷名叫 2026-10，里面却有 9 月的政策——按日期找会漏掉它。"""
        got = self.build({'2026-10': ['2026-10-09', '2026-09-30']}, ['2026-10'])
        self.assertTrue(any('超出卷名区间' in m for m in got), got)

    def test_卷名不是日期区间要报(self):
        got = self.build({'第一卷': ['2026-10-09']}, ['第一卷'])
        self.assertTrue(any('不是日期区间' in m for m in got), got)


class Test卡片发现(unittest.TestCase):
    """扁平卡与目录卡都要被发现——漏一种，那一类卡就完全不进检查。"""

    def test_两种形态都算一张卡(self):
        from pkb.core import card_files
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(d, ignore_errors=True))
        (d / '政策卡片-甲.md').write_text('# 甲', encoding='utf-8')
        (d / '政策卡片-乙').mkdir()
        (d / '政策卡片-乙' / '政策卡片-乙.md').write_text('# 乙', encoding='utf-8')
        (d / '政策卡片-乙' / '2026-10.md').write_text('# 卷', encoding='utf-8')
        names = sorted(p.name for p in card_files(d))
        self.assertEqual(names, ['政策卡片-乙.md', '政策卡片-甲.md'],
                         '卷不是独立卡片，不该出现在卡片清单里')
