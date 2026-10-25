#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策知识库 —— 统一入口。

设计目的：让「采集 / 存储 / 链接 / 分析 / 产出 / 自检」六个环节共用一条命令，
不再各自拼脚本路径。新增或删除脚本时，本入口自动发现，**不用改任何提示词**。

用法
----
    python3 tools/run.py status     当前状态（采到哪天 / 跑没跑 / 修没修 + 下一步）   恒 exit 0
    python3 tools/run.py check      全量自检                                          有问题 exit 1
    python3 tools/run.py fix        一次性修复（所有能自动修的，一次改完）             恒 exit 0
    python3 tools/run.py plan       派活清单（本轮该做什么，按执行顺序）               恒 exit 0
    python3 tools/run.py week 2026-W42  周观点素材预取（索引＋行号，--full 连正文）     恒 exit 0
    python3 tools/run.py export     把脚本同步进专家包（部署副本＋哈希清单）           恒 exit 0
    python3 tools/run.py sources    来源合规扫描（--apply 才写盘）                     有问题 exit 1
    python3 tools/run.py list       列出 tools 下全部脚本与用途（不用记脚本名）

参数透传（提示词里因此不必再写具体脚本路径）
----------------------------------------
    python3 tools/run.py check --since 2026-10-20    只把 --since 交给认得它的脚本
    python3 tools/run.py check 2026-W43              周号交给认得 --week 的脚本
    python3 tools/run.py check --week 2026-W43       同上

约定
----
* 自检脚本一律命名 `check_*.py`，本入口自动纳入 `check` 动作——新增即生效。
* 任何脚本只要**声明**了 `--fix`（源码含 `'--fix' in sys.argv` 或 `add_argument('--fix'`），
  就自动纳入 `fix` 动作。注释里提到 --fix 不算声明——2026-10-24 前判据太松，
  check_docs.py 因注释里有这字样被误编进修复队列。
* 路径只在 `lib.py` 定义一次，各脚本 `from pkb.core import`——不各写一遍。
* `status` / `plan` 是给人看的，永远不阻断（恒 exit 0），不要用它们的退出码判成败。
* 规则只有一处：库内 `AGENTS.md`。本文件不复述规则，只负责调度。
"""
import subprocess
import sys
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
from pkb.core import SUMMARY_MARK          # 摘要行契约唯一定义处：pkb/core/report.py
PY = sys.executable or 'python3'

USAGE = __doc__


def sh(cmd, cwd=None):
    """跑一条命令，返回 (退出码, 输出文本)。永不抛异常。"""
    try:
        r = subprocess.run(cmd, cwd=cwd or str(HERE), capture_output=True,
                           text=True, timeout=600)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except Exception as e:                                  # 脚本崩了也算它没过
        return 1, f'[run.py] 执行失败：{e}'


def discover_checks():
    """自动发现全部自检脚本。新增 check_x.py 即自动纳入，无需改动本文件。"""
    return sorted(p for p in HERE.glob('check_*.py') if p.is_file())


FIX_DECL = re.compile(r"'--fix'\s*in\s*sys\.argv|add_argument\(\s*['\"]--fix")
ALL_DECL = re.compile(r"'--all'\s*in\s*sys\.argv|add_argument\(\s*['\"]--all")


def declares(p, pattern):
    try:
        return bool(pattern.search(p.read_text(encoding='utf-8')))
    except Exception:
        return False


def discover_fixable():
    """源码里**声明**了 --fix 的脚本，才纳入 fix 动作。

    必须是真的声明（解析 argv 或注册参数），不能只是注释里提到——
    check_docs.py 的注释写着「本脚本刻意不提供 --fix」，
    若按「文本包含」判断，它会被当成具备修复能力而编进队列。
    """
    out = []
    for p in sorted(HERE.glob('*.py')):
        if p.name in ('run.py', 'lib.py'):
            continue
        if declares(p, FIX_DECL):
            out.append(p)
    return out


def supports(p, flag):
    """脚本真的认得这个参数吗？

    判据与 FIX_DECL 一致：必须真注册（argparse add_argument），不能靠文本包含。
    2026-10-25 前这里用 `flag in 源码`，于是 `check --week 2026-W43` 把 --week
    交给只认位置参数的 check_week_coverage，argparse 直接报错；
    而拼错的 `--snice` 又被静默丢弃、全量照跑并 exit 0——调用方以为窗口核过了。
    """
    if flag == '--all':
        return declares(p, ALL_DECL)
    return declares(p, re.compile(r"add_argument\(\s*['\"]" + re.escape(flag) + r"['\"]"))


def route_args(p, rest):
    """把命令行参数交给认得它的脚本，认不得的不传（传了会报未知参数）。"""
    out = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a.startswith('--'):
            flag = a.split('=')[0]
            if supports(p, flag):
                out.append(a)
                if '=' not in a and i + 1 < len(rest) and not rest[i + 1].startswith('--'):
                    out.append(rest[i + 1])
                    i += 1
        elif re.match(r'\d{4}-W\d{2}$', a):           # 裸周号 → 转成 --week
            if supports(p, '--week'):
                out += ['--week', a]
        i += 1
    return out


def pick_summary(out):
    """抓脚本的一句话结论。

    优先认契约标记 `▸摘要:`；抓不到才退回正则猜，且**从后往前找带数字的行**。
    2026-10-25 前是「第一条匹配 `覆盖率|OK` 的行」，结果抓到的是小节标题
    『=== 观点覆盖率 ===』和表头『周号 窗口内 表行…』——最关键的百分比
    恰恰被省掉了。摘要行现在是契约，不是猜测。
    """
    lines = [l.strip() for l in out.split('\n') if l.strip()]
    marked = [l for l in lines if l.startswith(SUMMARY_MARK)]
    if marked:
        return marked[-1][len(SUMMARY_MARK):].strip()[:120]
    for l in reversed(lines):
        if re.search(r'覆盖率|完整率|命中|断链|通过|错误|违规', l) and re.search(r'\d', l):
            return l[:120]
    return ''


def head(title):
    print('\n' + '=' * 62)
    print(title)
    print('=' * 62)


# ─────────────────────────── 动作：status ───────────────────────────
def action_status():
    """委托给 status_report.py（2026-10-25 外移：三页格式变更不该改入口）。"""
    sr = HERE / 'status_report.py'
    if not sr.exists():
        print('状态脚本不存在：tools/status_report.py')
        return 1
    code, out = sh([PY, str(sr)])
    print(out)
    return code


# ─────────────────────────── 动作：check ───────────────────────────
def action_check(rest=None):
    """全量自检。实现已迁到 pkb/actions/check.py（输出详略与退出码聚合都在那一层）。

    可带参数：--since（信号窗口）／--week 或裸周号（周观点）／--only（单项全量输出）／--full
    """
    from pkb.actions import check as check_action
    return check_action.run(rest)


# ─────────────────────────── 动作：fix ────────────────────────────
def action_fix():
    """一次性修复：把所有能自动修的改完，并报告改了什么、哪些仍需人工。"""
    head('一次性修复')

    changed = 0

    # 1. 快照必须先刷：否则后面的结构检查会拿旧数字报假警
    #    （不再先跑一次 --dry-run：这条路径紧接着就写盘，预演只是白花一次全库扫描）
    snap = HERE / 'refresh_snapshot.py'
    if snap.exists():
        code, out = sh([PY, str(snap)])
        n = re.findall(r'(\d+)\s*处', out)
        print(f'[1] 快照刷新          退出码 {code}'
              + (f'，更新 {n[-1]} 处' if n else '，无变化（幂等）'))
        changed += int(n[-1]) if n else 0

    # 2. 声明了 --fix 的脚本，逐个跑
    fx = discover_fixable()
    if not fx:
        print('[2] 没有脚本声明 --fix（跳过自动修复）')
    for i, p in enumerate(fx, 2):
        code, out = sh([PY, str(p), '--fix'])
        n = re.findall(r'修复\s*(\d+)|更新\s*(\d+)|已修\s*(\d+)', out)
        cnt = sum(int(x) for t in n for x in t if x) if n else 0
        print(f'[{i}] {p.name:<24} 退出码 {code}'
              + (f'，修复 {cnt} 处' if cnt else ''))
        changed += cnt
        for l in out.strip().split('\n')[:8]:
            if re.search(r'修复|改写|删除|替换|更新', l):
                print('      ' + l.strip()[:96])

    # 3. 来源清理（只在真有违规时才写盘，平时是 no-op）
    cs = HERE / 'clean_sources.py'
    if cs.exists():
        code, out = sh([PY, str(cs), '--dry-run'])
        hits = re.findall(r'命中\s*(\d+)', out) or re.findall(r'(\d+)\s*条', out)
        if hits and int(hits[0]) > 0:
            code2, out2 = sh([PY, str(cs), '--apply'])
            print(f'[{len(fx) + 2}] 来源清理            清理 {hits[0]} 条违规链接，退出码 {code2}')
            changed += int(hits[0])
        else:
            print(f'[{len(fx) + 2}] 来源清理            无违规链接（跳过）')

    # 4. 专家包副本同步：副本漂移属于「能自动修」的——源头在 tools/，副本只是下游，
    #    保持同源不需要任何判断。唯一不许自动的是文档口径冲突（两份文档各说一套，只有人能定）。
    ex = HERE / 'export_expert.py'
    if ex.exists():
        code, out = sh([PY, str(ex)])
        m = re.search(r'更新\s*(\d+)', out)
        n_up = int(m.group(1)) if m else 0
        print(f'[{len(fx) + 3}] 副本同步            退出码 {code}'
              + (f'，更新 {n_up} 个脚本' if n_up else '，与 tools 同源（无需同步）'))
        changed += n_up

    head('修复结论')
    print(f'本轮自动修改 {changed} 处。')
    print('\n仍需人工判断（脚本不猜，猜了就是编造）：')
    print('  · 观点覆盖率欠账 —— 要联网检索，属采集活')
    print('  · 信号断档补采 —— 过了日期补不回来，属采集活')
    print('  · 字段取值异常（影响/领域/tags）—— 涉及判断')
    print('  · 跨链归属错位 —— 只报告不移动')
    print('  · 文档口径冲突（含 AGENTS／README／专家定义各说一套）—— 改哪一份须问用户')
    print('\n修完请再跑一次 `python3 tools/run.py check` 确认归零。')
    return 0


# ─────────────────────────── 动作：plan ───────────────────────────
def action_plan():
    pb = HERE / 'plan_backlog.py'
    if not pb.exists():
        print('派活器不存在：tools/plan_backlog.py')
        return 0
    code, out = sh([PY, str(pb)])
    print(out)
    return 0


# ─────────────────────────── 动作：list ────────────────────────────
def action_list():
    """列出 tools 下的脚本与用途。

    存在的理由：脚本有几个不该由人去记。需要知道时跑这条命令，
    它读的是文件本身（新增/删除脚本自动反映），不会像文档那样过时。
    """
    head('tools 目录清单')
    fx = {p.name for p in discover_fixable()}
    ck = {p.name for p in discover_checks()}
    for p in sorted(HERE.glob('*.py')):
        src = p.read_text(encoding='utf-8')
        m = re.search(r'"""(.*?)"""', src, re.S)
        first = ''
        if m:
            for l in m.group(1).strip().split('\n'):
                if l.strip() and not l.strip().startswith(('用法', '---', '===')):
                    first = l.strip()
                    break
        tags = []
        if p.name in ck:
            tags.append('check 自动纳入')
        if p.name in fx:
            tags.append('fix 自动纳入')
        print(f'  {p.name:<24}{first[:52]}')
        if tags:
            print(f'  {"":<24}↳ {"、".join(tags)}')
    print('\n（清单由目录实际内容生成；新增脚本不用改任何提示词或文档）')
    return 0


# ─────────────────────────── 动作：sources ─────────────────────────
def action_sources(argv):
    cs = HERE / 'clean_sources.py'
    if not cs.exists():
        print('来源清理脚本不存在：tools/clean_sources.py')
        return 1
    code, out = sh([PY, str(cs)] + argv)
    print(out)
    return code


# ─────────────────────────── 动作：week ────────────────────────────
def action_week(argv):
    """周观点素材预取：窗口内政策与信号的索引＋行号（--full 连正文）。

    存在的理由：周观点要「窗口内全部政策＋全部信号」，若靠遍历全库，
    读入量约 40 万字符，而真正用到的不到 5%。这里只给索引与行号，
    按行号读那一段即可——把「找」和「读」拆开。
    """
    ws = HERE / 'week_sources.py'
    if not ws.exists():
        print('素材预取脚本不存在：tools/week_sources.py')
        return 0
    code, out = sh([PY, str(ws)] + list(argv))
    print(out)
    return 0


# ─────────────────────────── 动作：export ──────────────────────────
def action_export(argv):
    """把 tools 下的脚本同步进专家包（部署副本），并写哈希清单。

    存在的理由：专家包要能独立运行就得自带脚本，自带就有第二份副本。
    副本怕的不是漂移，是漂移了没人知道——所以导出即记账（MANIFEST 记 sha256），
    体检时 check_docs 拿清单比对，不一致直接 exit 1。
    """
    ep = HERE / 'export_expert.py'
    if not ep.exists():
        print('导出脚本不存在：tools/export_expert.py')
        return 1
    code, out = sh([PY, str(ep)] + list(argv))
    print(out)
    return code


ACTIONS = {
    'status':  (action_status,  '当前状态：采到哪天 / 跑没跑 / 修没修'),
    'check':   (action_check,   '全量自检，有问题 exit 1（可带 --since / 周号 / --only / --full）'),
    'fix':     (action_fix,     '一次性修复所有能自动修的'),
    'plan':    (action_plan,    '派活清单'),
    'week':    (action_week,    '周观点素材预取：某周政策与信号索引＋行号'),
    'export':  (action_export,  '把脚本同步进专家包（部署副本＋哈希清单，--check 只比对）'),
    'sources': (action_sources, '来源合规扫描（--apply 写盘）'),
    'list':    (action_list,    '列出脚本与用途（不用记脚本名）'),
}


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(USAGE)
        print('可用动作：')
        for k, (_, d) in ACTIONS.items():
            print(f'  {k:<9} {d}')
        return 0
    act, rest = argv[0], argv[1:]
    if act not in ACTIONS:
        print(f'未知动作：{act}')
        print('可用动作：' + ' / '.join(ACTIONS))
        return 2
    fn = ACTIONS[act][0]
    return fn(rest) if act in ('sources', 'check', 'week', 'export') else fn()


if __name__ == '__main__':
    sys.exit(main())
