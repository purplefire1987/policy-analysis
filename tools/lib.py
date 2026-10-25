#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具层：所有脚本共用的路径、读取与输出约定。

为什么要有这一层：2026-10-24 之前，`VAULT` 那条绝对路径在 8 个脚本里各写了一遍，
frontmatter 解析、md 遍历、输出前缀也各有各的写法。改一次仓库位置要动 8 处，
而其中任何一处漏改都不会报错——这正是本库反复出现的「副本漂移」。

判据很简单：**同一件事在两处以上出现，就搬到这里。**

本层只放「无业务判断」的通用件。涉及口径的东西（什么是信号、观点算不算完整、
节拍与配额）一律留在各自脚本与 AGENTS.md 里，不进这里——
一旦口径进了共用层，改口径就要动代码，那是把规则藏进了实现。

用法：其它脚本一律 `from lib import VAULT, CARD_DIR, ...`，不要再自己拼路径。
"""

import hashlib
import os
import re
from pathlib import Path
# ── 路径：全库唯一定义处 ────────────────────────────────────────────
# 允许环境变量覆盖：专家包内带的是同一份脚本，换台机器（或换库位置）时
# 只要设 POLICY_KB_VAULT / POLICY_KB_WORKSPACE，不必改代码。
# 默认值仍是本机的绝对路径——绝大多数调用方什么都不用设。
VAULT = Path(os.environ.get('POLICY_KB_VAULT', '/Users/Mr_Zhou/Documents/知识库/资料库'))
WORKSPACE = Path(os.environ.get('POLICY_KB_WORKSPACE',
                                '/Users/Mr_Zhou/WorkBuddy/2026-09-23-07-58-53'))   # 工具、备份、报告落点
TOOLS = Path(__file__).resolve().parent

CARD_DIR = VAULT / 'wiki' / '政策卡片'
CHAIN_DIR = VAULT / 'wiki' / '政策链'
SIGNAL_DIR = VAULT / 'wiki' / '政策信号'
WEEKLY_DIR = VAULT / 'wiki' / '周观点'
ANALYSIS_DIR = VAULT / 'wiki' / '分析'
OVERVIEW_DIR = VAULT / 'wiki' / '总览'
TEMPLATE_DIR = VAULT / 'templates'

INDEX = VAULT / 'index.md'                      # 唯一入口：链名单＋受控词＋快照
AGENTS = VAULT / 'AGENTS.md'                    # 唯一规则来源
README = VAULT / 'README.md'
LOG = VAULT / 'log.md'

STATUS = OVERVIEW_DIR / '运行状态.md'            # 管「跑没跑」
LEDGER = OVERVIEW_DIR / '任务台账.md'            # 管「修没修」
COLLECT_LOG = OVERVIEW_DIR / '采集日志.md'       # 管「采到哪天」
CHECK_REPORT = OVERVIEW_DIR / '体检报告.md'
WEEK_TEMPLATE = TEMPLATE_DIR / '周观点模板.md'

# 专家包在库外，但被 check_docs 校验，路径也只在此定义一次
EXPERT_DIR = Path.home() / '.workbuddy/plugins/marketplaces/my-experts/plugins/gov-policy-analyst'
EXPERT_MD = EXPERT_DIR / 'agents' / 'gov-policy-analyst.md'

# 扫描时要排除的目录
SKIP_DIRS = ('.obsidian', '.trash', '.git')


# ── 读取 ────────────────────────────────────────────────────────────
def md_files(skip_log=True, roots=None):
    """全库 md 文件（已排除 .obsidian/.trash）。

    skip_log：log.md 是历史，多数校验应跳过；只有 log 卫生检查会显式带上它。
    """
    bases = roots or [VAULT]
    seen = set()
    for base in bases:
        if not Path(base).exists():
            continue
        for p in sorted(Path(base).rglob('*.md')):
            if any(d in p.parts for d in SKIP_DIRS):
                continue
            if skip_log and p.name == 'log.md':
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


def read(p, default=None):
    """读文本。文件不存在时：给了 default 就返回 default，否则抛异常。

    default 参数的由来：check_docs 与 plan_backlog 各自写过「文件不存在返回空串」
    的 read——同一件事两份拷贝，漏改不报错。统一到这里。
    """
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        raise FileNotFoundError(p)
    return p.read_text(encoding='utf-8', errors='ignore')


def write(p, text):
    Path(p).write_text(text, encoding='utf-8')


def digest(p):
    """文件内容的 sha256（副本是否同一份，只认这个）。

    为什么在共用层：导出时写清单、体检时比清单，是同一次计算的两端。
    两边各写一份哈希实现，正是本项目反复出事的「副本漂移」。
    """
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def all_names():
    """全库页面名（不含 .md），用于 wikilink 断链判断。"""
    return {p.stem for p in md_files(skip_log=False)}


# ── frontmatter ─────────────────────────────────────────────────────
FM_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.S)


def parse_fm(text):
    """解析 YAML frontmatter 的扁平键值（本库只用一层，不上 yaml 依赖）。

    返回 (dict, body)。数组写成 `[a, b]` 或花键下的多行 `- item` 都会被解析成 list，
    `tags: [政策, 国际博弈]` 这类必须保持数组，否则 Dataview 失效。
    无 frontmatter 时返回 ({}, 原文)。
    """
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm, body = {}, text[m.end():]
    cur = None
    for raw in m.group(1).split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # 多行列表项：`tags:` 下一行的 `- 政策`
        if line.startswith('- ') and cur is not None:
            item = line[2:].strip().strip('"').strip("'")
            if item:
                if not isinstance(fm.get(cur), list):
                    fm[cur] = []
                fm[cur].append(item)
            continue
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        cur = k.strip()
        v = v.strip().strip('"').strip("'")
        # 行内数组，但排除 `[[wikilink]]`——双括号是链接不是数组
        if v.startswith('[') and v.endswith(']') and not v.startswith('[['):
            fm[cur] = [x.strip().strip('"').strip("'")
                       for x in v[1:-1].split(',') if x.strip()]
        else:
            fm[cur] = v
    return fm, body


def set_fm_field(text, key, value):
    """改 frontmatter 里的一个键值（冒号半角/全角都认）。

    库里实际用半角 `政策数: 3`，只写全角会让替换静默失效——
    2026-10-24 的自动修复就栽在这里，一处没改却不报错。
    """
    return re.sub(rf'(?m)^{re.escape(key)}[:：].*$', f'{key}: {value}', text, count=1)


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


# 摘要行契约：每个 check_*.py 结束前输出一行 `▸摘要: …`，
# `run.py check` 只抓这一行（抓不到才退回正则）。
# 为什么要有契约：2026-10-25 前入口靠「第一行含覆盖率/OK 等词」猜摘要，
# 结果 check_views 抓到的是小节标题「=== 观点覆盖率 ===」、周覆盖抓到表头，
# 最关键的数字在入口输出里根本看不见——省 token 省成了信息黑洞。
SUMMARY_MARK = '▸摘要:'


def summary(msg):
    """本脚本的一句话结论。入口只认这一行。"""
    print(f'{SUMMARY_MARK} {msg}')


# ── 其它 ────────────────────────────────────────────────────────────
def similar(target, names, cutoff=0.85, n=2):
    """断链自动修复用：返回候选名列表。多个候选时调用方必须放弃（不猜）。"""
    import difflib
    return difflib.get_close_matches(target, list(names), n=n, cutoff=cutoff)


def iso_week(d):
    """date → 'YYYY-Www'。判定周次一律走它，不要凭感觉。"""
    y, w, _ = d.isocalendar()
    return f'{y}-W{w:02d}'


def parse_date(s):
    """'2026-10-20' → date；解析不了返回 None（不抛异常，交给调用方判）。"""
    import datetime
    try:
        return datetime.date.fromisoformat(str(s).strip())
    except (ValueError, TypeError):
        return None


def span(a, b):
    """日期区间显示：相同只写一个。"""
    return f'{a}~{b}' if a != b else f'{a}'


# ── md 切块：小节与表格的通用拆法 ───────────────────────────────────
SECTION_HEAD = re.compile(r'^### (\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\s*$', re.M)


def extract_sections(body):
    """把正文按 `### YYYY-MM-DD · 标题` 切成块。

    返回 (secs, bad)：secs = [(date, title, chunk_text, raw_line)]，
    bad = 不符合日期格式的 ### 标题行。产业卡与信号页共用这一种小节格式。
    """
    secs, bad = [], []
    cur = None
    for line in body.split('\n'):
        if line.startswith('### '):
            if cur:
                secs.append(cur)
            m = SECTION_HEAD.match(line)
            if m:
                cur = [m.group(1), m.group(2), [], line]
            else:
                bad.append(line)
                cur = None
        elif cur is not None:
            cur[2].append(line)
    if cur:
        secs.append(cur)
    return [(d, t, '\n'.join(ch), raw) for d, t, ch, raw in secs], bad


def md_section_lines(text, title):
    """取 `## ` 节（标题含 title 即中）到下一个 `## ` 之间的行。

    用包含匹配而不是全等：台账各节标题带序号，如 `## 四、存量补采队列（…）`。
    """
    out, on = [], False
    for line in text.split('\n'):
        if line.startswith('## '):
            on = title in line
            continue
        if on:
            out.append(line)
    return out


def table_rows(lines):
    """从行序列里抽 markdown 表格数据行（跳过表头与分隔行）。"""
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip().strip('|').split('|')]
        if not cells or set(''.join(cells)) <= set('-: '):
            continue
        rows.append(cells)
    return rows[1:] if rows else []   # 首行是表头


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

    def render(self, quiet=False):
        if not quiet:
            for m in self.oks:
                print(f'  OK  {m}')
        for item, msg in self.errors:
            print(f'  ✗  [{item}] {msg}')
        for item, msg in self.warns:
            print(f'  ·  [{item}] {msg}')
