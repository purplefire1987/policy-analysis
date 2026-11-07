#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.fs.read 的契约：**一次运行内同一份文件只真正读一遍**。

为什么要单独锁这一条：本机每打开一次文件约 25ms（读 1 字节也一样，stat 却是 0），
而九个检查各自扫库、逻辑上不重叠却撞在同一批文件上——2026-11-07 实测一轮全量自检
打开 1128 次，只对应 293 个文件，多出来的 835 次全是重复打开同一批文件。

这条缓存失效时**不会报错，只会变慢**，所以两件事都得钉住：
  ① 同一文件读两次，只允许真打开一次；
  ② 文件被改过，下一次读必须拿到新内容——缓存不许退化成「旧副本」。
再加一条静态守卫：`pkb/` 里除 `core/fs.py` 外不许出现 `read_text`／`write_text`，
绕过一次就多开一次文件，且没有任何读数会提示。

跑法：python3 -m pytest -q tools/tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.core import fs                       # noqa: E402

PKG = Path(__file__).resolve().parents[1] / 'pkb'


class TestReadOnce(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.p = self.dir / 'a.md'
        self.p.write_text('第一版', encoding='utf-8')

    def count_opens(self):
        """包一层 Path.read_text 数「真打开了几个文件」，返回 (计数表, patch)。"""
        real, seen = Path.read_text, []

        def wrapper(self_, *a, **k):
            seen.append(str(self_))
            return real(self_, *a, **k)
        return seen, mock.patch.object(Path, 'read_text', wrapper)

    def test_同一文件读两次只打开一次(self):
        seen, patch = self.count_opens()
        with patch:
            self.assertEqual(fs.read(self.p), '第一版')
            self.assertEqual(fs.read(self.p), '第一版')
        self.assertEqual(len(seen), 1, f'重复打开了：{seen}')

    def test_多文件各读两次按文件数打开(self):
        files = []
        for i in range(5):
            q = self.dir / f'{i}.md'
            q.write_text(f'第{i}份', encoding='utf-8')
            files.append(q)
        seen, patch = self.count_opens()
        with patch:
            for _ in range(2):
                for q in files:
                    fs.read(q)
        self.assertEqual(len(seen), 5, f'应只打开 5 次，实际 {len(seen)}：{seen}')

    def test_文件被改过之后读到的是新内容(self):
        """体积不变、只动 mtime 的改写也必须重读——判据不能吃旧文本。"""
        fs.read(self.p)
        self.p.write_text('第二版', encoding='utf-8')      # 与「第一版」同为 9 字节
        st = self.p.stat()
        os.utime(self.p, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
        self.assertEqual(fs.read(self.p), '第二版')

    def test_write之后读到的是新内容(self):
        fs.read(self.p)
        fs.write(self.p, '第三版')
        self.assertEqual(fs.read(self.p), '第三版')

    def test_mtime没动也必须看见write的内容(self):
        """mtime 粒度粗的文件系统上（同秒同大小），stat 比对认不出这次写入。

        这一条专门验 write() 里那条主动作废：只靠 stat 时它会漏，且漏得静默。
        """
        before = self.p.stat()
        fs.read(self.p)
        fs.write(self.p, '第四版')                  # 仍为 9 字节
        os.utime(self.p, ns=(before.st_atime_ns, before.st_mtime_ns))   # 把 mtime 拨回原值
        self.assertEqual(fs.read(self.p), '第四版')

    def test_不存在时行为不变(self):
        miss = self.dir / '没有这份.md'
        self.assertEqual(fs.read(miss, ''), '')
        self.assertEqual(fs.read(miss, 'x'), 'x')
        with self.assertRaises(FileNotFoundError):
            fs.read(miss)


class TestSingleDoor(unittest.TestCase):
    """读写文件只有 core/fs.py 一扇门：绕过去就等于绕过「只读一遍」。"""

    def test_除core_fs外不直接读写文本(self):
        offenders = []
        for p in sorted(PKG.rglob('*.py')):
            if p == PKG / 'core' / 'fs.py' or '__pycache__' in p.parts:
                continue
            text = p.read_text(encoding='utf-8')
            for bad in ('read_text', 'write_text'):
                if bad in text:
                    offenders.append(f'{p.relative_to(PKG)}：{bad}')
        self.assertEqual(offenders, [],
                         '读写文本请走 pkb.core.read／write（否则同一文件会被反复打开）：\n  '
                         + '\n  '.join(offenders))


if __name__ == '__main__':
    unittest.main()
