#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时目录清扫：清什么、留什么、什么时候不扫。

为什么单测：这段代码**会删文件**，而且删的正是「名字以 tmp 开头、内容无关」的目录——
条件写松一格，就会把正在跑的采集用的临时目录一起删掉；写紧一格，垃圾照旧堆。
四个开关都要钉住：过期线（`KEEP_SECONDS`）、节流（`SWEEP_GAP`）、
单次预算（`SWEEP_BUDGET`）、以及「戳文件自己不能被删」。

判据只有一条：**动的都是「早于过期线」的，其它一个不碰。**
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import tmp as tmp_mod               # noqa: E402

# 夹具落点必须**离开** TMP_DIR：`sweep` 自己的判据就是扫 TMP_DIR，
# 测试造的目录若落在里面，会被别的用例的 sweep 顺手清掉，也会被 check 当成残留。
SANDBOX = Path(__file__).resolve().parents[2] / '.cache' / 'test-tmp'


def ago(seconds):
    """把条目的 mtime 拨到 `seconds` 秒之前。"""
    t = time.time() - seconds
    return t


class Test清扫(unittest.TestCase):
    def setUp(self):
        SANDBOX.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=SANDBOX))
        self._old = tmp_mod.TMP_DIR
        tmp_mod.TMP_DIR = self.root

    def tearDown(self):
        tmp_mod.TMP_DIR = self._old
        # ignore_errors：沙箱可能拦删，这里不该因此让用例变红（与 conftest 同一理由）。
        shutil.rmtree(self.root, ignore_errors=True)

    def put_dir(self, name, age):
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        (p / 'f.txt').write_text('x', encoding='utf-8')
        t = ago(age)
        os.utime(p, (t, t))
        return p

    def put_file(self, name, age):
        p = self.root / name
        p.write_text('x', encoding='utf-8')
        t = ago(age)
        os.utime(p, (t, t))
        return p

    def test_只删过期的(self):
        old = self.put_dir('tmp_old', 2 * 24 * 3600)
        new = self.put_dir('tmp_new', 60)
        removed, failed, _freed, done = tmp_mod.sweep(force=True)
        self.assertEqual((removed, failed, done), (1, 0, True))
        self.assertFalse(old.exists(), '过期目录该删')
        self.assertTrue(new.exists(), '一小时内的目录可能还在用，绝不能删')

    def test_过期文件也清(self):
        f = self.put_file('tmpfile', 2 * 24 * 3600)
        removed, _failed, freed, _done = tmp_mod.sweep(force=True)
        self.assertEqual(removed, 1)
        self.assertFalse(f.exists())
        self.assertGreater(freed, 0)

    def test_戳文件自己不删(self):
        """`.swept` 的 mtime 记的是上次清扫时间，拖得越久越该被删——所以必须显式跳过。"""
        stamp = self.root / tmp_mod.STAMP_NAME
        stamp.write_text('', encoding='utf-8')
        t = ago(30 * 24 * 3600)
        os.utime(stamp, (t, t))
        removed, _failed, _freed, _done = tmp_mod.sweep(force=True)
        self.assertEqual(removed, 0)
        self.assertTrue(stamp.exists(), '戳被删掉就等于关掉了节流')

    def test_节流内不扫(self):
        """刚扫过六小时内再来一条命令，不该又 stat 一遍整个目录。"""
        self.put_dir('tmp_a', 2 * 24 * 3600)
        self.assertEqual(tmp_mod.sweep(force=True)[0], 1)
        self.put_dir('tmp_b', 2 * 24 * 3600)
        self.assertEqual(tmp_mod.sweep()[0], 0, '节流期内应直接返回')
        self.assertTrue((self.root / 'tmp_b').exists())
        self.assertEqual(tmp_mod.sweep(force=True)[0], 1, 'force 要绕过节流')

    def test_扫过就记戳_即使一个没删(self):
        self.assertFalse((self.root / tmp_mod.STAMP_NAME).exists())
        tmp_mod.sweep(force=True)
        self.assertTrue((self.root / tmp_mod.STAMP_NAME).exists())

    def test_预算用完就停_报未扫完(self):
        """沙箱审查下单个 rmtree 要 0.2 秒，4000 个要 11 分钟——
        一条 status 卡 11 分钟比垃圾更糟，所以宁可留着下次清。"""
        for i in range(3):
            self.put_dir(f'tmp_{i}', 2 * 24 * 3600)
        removed, _failed, _freed, done = tmp_mod.sweep(force=True, budget=-1)
        self.assertEqual(removed, 0)
        self.assertFalse(done, '没扫完要报出来，否则调用方以为清干净了')

    def test_目录不存在不炸(self):
        tmp_mod.TMP_DIR = self.root / 'not' / 'there'
        self.assertEqual(tmp_mod.sweep(force=True), (0, 0, 0, True))

    def test_删不掉只计数不抛(self):
        """沙箱拦删时是 OSError。这里不能抛——临时目录出问题不该让主命令崩。"""
        p = self.put_dir('tmp_locked', 2 * 24 * 3600)
        real = tmp_mod.shutil.rmtree
        tmp_mod.shutil.rmtree = lambda *a, **k: (_ for _ in ()).throw(PermissionError(1, 'denied'))
        try:
            removed, failed, _freed, _done = tmp_mod.sweep(force=True)
        finally:
            tmp_mod.shutil.rmtree = real
        self.assertEqual((removed, failed), (0, 1))
        self.assertTrue(p.exists())


if __name__ == '__main__':
    unittest.main()
