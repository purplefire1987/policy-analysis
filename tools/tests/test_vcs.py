#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本控制的判定：哪几种情况该判失败、哪几种只提示。

为什么单测：这一项最容易走两个极端——「脏就报红」会让体检天天红（自动化改完
文件本来就是脏的），「只报仓库存在」又会把「有目录无历史」当成通过。
两端都得钉住：_diagnose 是纯函数，不碰磁盘，正好逐条测。

**夹具只放 `leaked`，不放具体路径名**：第一版判据写死「raw/articles 被跟踪就算
失败」，几小时后决定把它纳入 git，判据立刻把正确做法判成硬问题。现在判据核的是
「.gitignore 声明的和事实一致吗」，路径改不改都不用动这里——这也是为什么下列
用例里出现的都是 `some/dir/`，不是真实目录。
"""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import vcs                     # noqa: E402


def facts(**kw):
    base = {'commits': '3', 'dirty': [], 'leaked': [], 'probes': [],
            'last_ts': int(time.time()), 'last_subj': '基线'}
    base.update(kw)
    return base


class Test硬问题(unittest.TestCase):
    def test_没有提交算失败(self):
        hard, _soft = vcs._diagnose(facts(commits='0'))
        self.assertTrue(any('一个提交都没有' in m for m in hard), hard)

    def test_Gitignore声明排除却仍被跟踪(self):
        hard, _soft = vcs._diagnose(facts(leaked=['some/dir/a.md', 'some/dir/b.md']))
        self.assertTrue(any('some/dir/' in m and '2 个文件' in m for m in hard), hard)

    def test_没有泄漏就不报(self):
        """把原排除项纳入版本控制是正当决定，判据不该拦。"""
        hard, _soft = vcs._diagnose(facts(leaked=[]))
        self.assertEqual(hard, [])


class Test只提示(unittest.TestCase):
    def test_有未提交改动不阻断(self):
        hard, soft = vcs._diagnose(facts(dirty=[' M a.md', '?? b.md']))
        self.assertEqual(hard, [], '自动化改完文件本来就会脏，判红等于天天红')
        self.assertTrue(any('2 处' in m for m in soft), soft)

    def test_久未提交要提示(self):
        old = int(time.time()) - 30 * 86400
        hard, soft = vcs._diagnose(facts(last_ts=old))
        self.assertEqual(hard, [])
        self.assertTrue(any('30 天前' in m for m in soft), soft)


class Test干净(unittest.TestCase):
    def test_全绿时两档都空(self):
        hard, soft = vcs._diagnose(facts())
        self.assertEqual((hard, soft), ([], []))


# 造探针的测试**不能把落点放在 `TMP_DIR`**：`tempfile` 被 `core/tmp.py` 钉在
# `.cache/tmp`，那正好在探针扫描范围之内；而沙箱拦删时 `cleanup()` 会失败（conftest
# 吞掉异常），造出来的假探针就留在原地，下一轮 `run.py check` 把测试造的东西当真问题报红。
# 2026-10-29 实测踩到：跑完 pytest 立刻 `check` 报「2 个沙箱探针残留」，点开一看是
# `.cache/tmp/tmpXXXX/ab12cd34`——是上一个用例造的那个。**测试不该生产体检对象。**
PROBE_SANDBOX = Path(__file__).resolve().parents[2] / '.cache' / 'test-tmp'


class Test探针判定(unittest.TestCase):
    """沙箱探针：名 8 位 `[a-z0-9_]` ＋ 大小 4 字节 ＋ 内容恰为 `blat`，三者全中才认。

    为什么逐条测「差一点」：这条判据会**删文件**。2026-10-28 已有一次删除条件写错、
    误删 AGENTS.md 等四个文件（靠刚建的 git 对象库取回）。凭「4 字节」或「8 字符名」
    单独一条去删，迟早重演——库里 4 字节的空标记文件不止一类。
    """

    def setUp(self):
        PROBE_SANDBOX.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=PROBE_SANDBOX))
        self._old = vcs.PROBE_BASES
        vcs.PROBE_BASES = (self.root,)

    def tearDown(self):
        vcs.PROBE_BASES = self._old
        # ignore_errors：沙箱可能拦删，这里**不该因此让用例变红**（与 conftest 同一理由）。
        shutil.rmtree(self.root, ignore_errors=True)

    def put(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return p

    def test_三重全中才认(self):
        p = self.put('ab12cd34', b'blat')
        self.assertEqual(vcs._probes(), [str(p)])

    def test_内容不同不认(self):
        self.put('ab12cd34', b'abcd')
        self.assertEqual(vcs._probes(), [])

    def test_大小不对不认(self):
        self.put('ab12cd34', b'blat!')
        self.assertEqual(vcs._probes(), [])

    def test_名不是八位不认(self):
        for name in ('ab12cd3', 'ab12cd345', 'AB12CD34'):
            self.put(name, b'blat')
        self.assertEqual(vcs._probes(), [], '长度、大小写都必须是恰好那个形态')

    def test_子目录一层认_再深不认(self):
        shallow = self.put('sub/ab12cd34', b'blat')
        self.put('sub/deeper/ef56gh78', b'blat')     # 两层：限深之外
        self.assertEqual(vcs._probes(), [str(shallow)],
                         '探针只落在执行命令的目录，限深两层够用；更深的不猜')

    def test_fix只删认下的那些(self):
        probe = self.put('ab12cd34', b'blat')
        keep = self.put('xx11yy22', b'abcd')          # 长得一样但内容不同
        n, lines = vcs.run_fix()
        self.assertEqual(n, 1, lines)
        self.assertFalse(probe.exists())
        self.assertTrue(keep.exists(), '不认的必须原地留着——宁可漏清，不可错删')

    def test_没有探针时fix不报修复数(self):
        n, lines = vcs.run_fix()
        self.assertEqual(n, 0)
        self.assertTrue(any('跳过' in x for x in lines), lines)


class Test探针报红(unittest.TestCase):
    """进结论表：有探针是硬问题，不是提示——因为它会被 `git add -A` 带进库。"""

    def test_有探针判硬问题(self):
        hard, _soft = vcs._diagnose(facts(probes=['/x/tools/ab12cd34']))
        self.assertEqual(len(hard), 1)
        self.assertIn('沙箱探针', hard[0])
        self.assertIn('run.py fix', hard[0])

    def test_报出来时只举一个例子(self):
        many = [f'/x/tools/ab12cd3{i}' for i in range(5)]
        hard, _ = vcs._diagnose(facts(probes=many))
        self.assertIn('5 个', hard[0])
        self.assertEqual(hard[0].count('/x/tools/'), 1, '只举一个例子，列全会淹掉结论')


if __name__ == '__main__':
    unittest.main()
