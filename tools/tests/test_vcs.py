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
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkb.checks import vcs                     # noqa: E402


def facts(**kw):
    base = {'commits': '3', 'dirty': [], 'leaked': [],
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


if __name__ == '__main__':
    unittest.main()
