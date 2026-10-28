#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提示词本体守门：五项断言各自的反例，加上两条「不能误伤」的回归。

为什么专测反例：本项的价值全在「能不能拦住已经发生过的漂移」。2026-10-26 实际
出过两起——四份体检提示词并存、索引页自称「当前版本 v5」而生效的是 v8。
这两起都要能在测试里复现，否则这项检查只是摆设。

另一类测试是「放过」：采集提示词的正文写着「不要自己拼 `tools/xxx.py` 路径」，
那是禁令的例子。第一版判据按字面抓「tools/xxx.py」，把「不准这样干」判成了
「这样干了」——本库 2026-10-25 在 `sys.exit(` 判据上栽过同一跤，所以这里钉住。
"""
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import prompts as P          # noqa: E402
from pkb.core import Verdict                 # noqa: E402

BODY = ('读 `AGENTS.md` 再动手。收工跑 `run.py check`。'
        '台账见 [[任务台账]]，取料按 `wiki/总览/深读方法手册.md`。\n')

# 每个用例一个独立子目录，跑完不清理（见 Base.setUp）
BASE = Path(__file__).resolve().parents[2] / '.cache' / 'test-prompts'


class Base(unittest.TestCase):
    """每个用例一套临时「工作区＋库」：真库改了也测不出反例。"""

    def setUp(self):
        # 不用 tempfile（2026-10-28）：沙箱拦删除时 `gettempdir()` 会抛，
        # 于是「断言全对」的用例也报红。改用唯一子目录，不清理。
        root = BASE / uuid.uuid4().hex[:10]
        self.dir = root / 'automation-prompts'
        self.dir.mkdir(parents=True)
        self.vault = root / 'vault'
        (self.vault / 'wiki' / '总览').mkdir(parents=True)
        for name in ('深读方法手册', '任务台账'):
            (self.vault / 'wiki' / '总览' / f'{name}.md').write_text('x', encoding='utf-8')
        import pkb.core.fs as _fs
        for obj, attr, val in ((P, 'PROMPT_DIR', self.dir),
                               (P, 'PROMPT_ARCHIVE', self.dir / '旧版'),
                               (P, 'VAULT', self.vault),
                               (_fs, 'VAULT', self.vault)):
            patcher = mock.patch.object(obj, attr, val)
            patcher.start()
            self.addCleanup(patcher.stop)


    def write(self, name, body=BODY):
        p = self.dir / name
        p.write_text(body, encoding='utf-8')
        return p

    def all_autos(self, body=BODY, omit=()):
        """按 `AUTOMATIONS` 现读的名单各写一份现行存档——正常基线。

        不写死「三个」：名单加长时，这条基线要跟着长，而不是让断言变红。
        omit 用来造「缺一份」：**不建比建了再删稳**——删不掉的环境里，
        靠 unlink 造出来的反例根本到不了断言。
        """
        for aid, aname in P.AUTOMATIONS.items():
            if aid in omit:
                continue
            self.write(f'{aname}-{aid}-2026-10-26.md', body)

    def errors(self):
        r = P.run([])
        return r, '\n'.join(r.lines)


class Test现行唯一(Base):
    def test_各一份时通过(self):
        self.all_autos()
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)
        # 数量按名单现算：写死「3 个」时，加第四个自动化会让这条绿测试变红，
        # 而它想验的是「各一份即通过」，跟有几个自动化无关。
        self.assertIn(f'{len(P.AUTOMATIONS)} 个自动化', r.summary)

    def test_两份并存要报(self):
        """2026-10-26 的实况：v5/v6/v8 三份都在顶层，没人知道哪份生效。"""
        self.all_autos()
        self.write('政策知识库定期体检-96885a01-v9-2026-10-27.md')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('份并存', text)

    def test_缺一份要报(self):
        self.all_autos(omit=('3ef2d6b6',))
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('顶层没有提示词存档', text)

    def test_文件名缺ID要报(self):
        self.all_autos(omit=('3ef2d6b6',))
        self.write('政策周观点生成-2026-10-26.md')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('缺自动化 ID', text)

    def test_旧版不参与现行判定(self):
        """旧版里堆多少份都不算「并存」——归档正是为了让它不参与判定。"""
        self.all_autos()
        arc = self.dir / '旧版'
        arc.mkdir()
        for v in ('v5', 'v6'):
            (arc / f'政策知识库定期体检-96885a01-{v}.md').write_text('旧', encoding='utf-8')
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertIn('旧版 2 份', r.summary)

    def test_目录不存在返回BAD_INPUT(self):
        # 指向一个不存在的路径，而不是把建好的目录改名——改名／删除在受限环境里会失败，
        # 而「目录不存在」本来只是个路径条件，没必要真去动文件系统
        with mock.patch.object(P, 'PROMPT_DIR', self.dir / 'nope'):
            r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.BAD_INPUT)


class Test抬头自洽(Base):
    def test_自称旧版本要报(self):
        """索引页式漂移：文件名不带 v5，正文却说「当前版本：v5」。"""
        self.all_autos()
        self.write('政策知识库每周体检-96885a01.md',
                   BODY + '当前版本：**v5**。v5 全文见同目录。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('索引页式漂移', text)

    def test_自称本版不报(self):
        self.all_autos(omit=('96885a01',))
        self.write('政策知识库定期体检-96885a01-v8-2026-10-26.md',
                   BODY + '当前版本：v8。\n')
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)


class Test命令真实(Base):
    def test_动作不存在要报(self):
        self.all_autos(BODY + '然后跑 `run.py nosuchaction`。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('不存在的动作', text)

    def test_only目标不存在要报(self):
        self.all_autos(BODY + '跑 `run.py check --only nosuchthing`。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('匹配不到任何检查项', text)

    def test_only目标存在不报(self):
        self.all_autos(BODY + '跑 `run.py check --only docs`。\n')
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)


class Test不直调(Base):
    def test_直调脚本要报(self):
        self.all_autos(BODY + '```\npython3 /x/tools/check_docs.py\n```\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('直调', text)

    def test_禁令里的例子不算直调(self):
        """「不要自己拼 tools/xxx.py 路径」是禁令，不是调用——按形态判，不按字面判。"""
        self.all_autos(BODY + '不要自己拼 `tools/xxx.py` 路径，一律走 `run.py`。\n')
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)


class Test引用可达(Base):
    def test_wikilink不存在要报(self):
        self.all_autos(BODY + '见 [[已删页面]]。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('在库里不存在', text)

    def test_占位链接放过(self):
        self.all_autos(BODY + '写入 `wiki/周观点/周观点-{周号}.md` 与 [[周观点-{周号}]]。\n')
        r, _ = self.errors()
        self.assertEqual(r.verdict, Verdict.PASS)

    def test_库内路径不存在要报(self):
        self.all_autos(BODY + '按 `wiki/总览/不存在的手册.md` 取料。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('不存在', text)

    def test_缺锚点要报(self):
        """少了「run.py check」，这份提示词就不再收工自检——脚本必须能察觉。"""
        self.all_autos(omit=('d1ca26c1',))
        self.write('政策每日采集入库-d1ca26c1-2026-10-26.md',
                   '读 `AGENTS.md`。见 [[任务台账]]。\n')
        r, text = self.errors()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('缺「run.py check」', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
