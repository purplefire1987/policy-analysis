#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""派活器：把散落在三处的欠账，合成一张按执行顺序排列的待办清单。

为什么需要它：采集与体检各自都有机制，但「谁该干什么」没有单一出口。
体检报告里最有价值的那一半（待补全清单、建议补采区间、长期空白页）没有下游——
采集的零点五是自己去数卡片，不是读体检结论，同一件事两本账。本脚本把这层接上。

它只读不写（唯一例外：什么都不改，连台账也不动）。输出的每一段都直接可执行，
并给出可以原样粘回任务台账的表格行，避免手工算日期算错。

观点两段的每条下面有一行「检索：」——机关取自卡片已有的「发文机关」字段，主体类别取
AGENTS 七要素的口径。它是**提示不是结论**：省掉「从哪找」这一步，判断与出处仍由人核。

用法（统一走入口）：
  run.py plan                 # 本轮清单（采集开工前跑）
  run.py plan --round 34      # 只影响标题里的轮次号
  run.py plan --json          # 机器可读（供体检/专家内联调用）
  run.py plan --top 8         # 存量观点清单最多列几条（默认 8）

退出码：恒 0。派活器不阻断——结构/周观点/信号是否合格，仍由四个校验脚本判定。
"""

import argparse
import re
import json
import datetime

from pkb.core import (CARD_DIR, SIGNAL_DIR, COLLECT_LOG, LEDGER, SECTION_HEAD,
                 read as lib_read, md_section_lines, table_rows, parse_date,
                 span, iso_week)
from pkb.domain import STANCES, STANCE_MIN
from pkb.domain.fields import views_state           # 观点两节状态，与 check_views 同一份
from pkb.domain.ledger import LEDGER_COLS, col    # 列名→下标，不写裸下标
from pkb.checks.docs.ledger import ledger_tables  # 两张表的分法只此一处（actions→checks 下行）
# 路径与通用件唯一定义处：pkb/core/paths.py
# 命名注意：lib 里 LEDGER=任务台账、COLLECT_LOG=采集日志；本文件沿用旧名 LEDGER=采集日志
TASKS = LEDGER                 # 任务台账.md
LEDGER = COLLECT_LOG           # 采集日志.md（保留旧变量名，避免全文改名）

ORG = re.compile(r'\*\*发文机关\*\*：\s*([^｜|\n]+)')
TITLE_NOISE = re.compile(r'^(关于|印发|转发)|(的)?(若干)?(通知|意见|方案|规划|办法|规定|条例|决定|公告|措施|指引|细则)$')

TODAY = datetime.date.today()
STOCK_GAP = 14      # 信号页断档超过此天数 → 进存量队列
STOCK_BATCH = 14    # 存量页每批只补 14 天，不追 78 天（追全段＝又一次半途而废）
GAP_BATCH = 2       # 政策断档每批 2 天
GAP_TRIGGER = 3     # 断档 >3 天才分批；≤3 天一轮补完，不必等体检
VIEW_DAILY = 3      # 存量观点每轮保底回填
VIEW_WEEKLY = 5     # 存量观点每周目标（2026-10-24 由 10 下调：实测到不了 10）
CLAIM_PER_CHECK = 1 # 每次释放的存量页数／断档批次数
GATE_DAYS = 2       # 领活闸门：距上次领取满 N 天可领（2026-10-28 与体检解耦）


# ────────────────────── 通用 ──────────────────────

def read(p):
    return lib_read(p, '')


def section(text, title):
    return md_section_lines(text, title)


def d(s):
    return parse_date(s)



def scan_cards():
    """返回 [{card, date, title, state, kind}]
    state: a 完整 / b 待补全 / c 无观点节（判定在 domain.fields.views_state，
           与 check_views 同一份实现——两处各写一遍，改口径就要改两处）
    kind:  b→'占位'  c→'无标题' 或 '缺辨析'
    """
    out = []
    for p in sorted(CARD_DIR.glob('*.md')):
        if p.name.startswith('.'):
            continue
        card = p.stem.replace('政策卡片-', '')
        text = read(p)
        hits = list(SECTION_HEAD.finditer(text))
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            chunk = text[m.end():end]
            has_v = '**各方观点**' in chunk
            has_d = '**观点辨析**' in chunk
            ph = views_state(chunk) == 'b'
            if has_v and has_d and not ph:
                st, kind = 'a', ''
            elif has_v and ph:
                st, kind = 'b', '占位'
            elif has_v:
                st, kind = 'c', '缺辨析'
            else:
                st, kind = 'c', '无标题'
            out.append({'card': card, 'date': m.group(1),
                        'title': m.group(2), 'state': st, 'kind': kind,
                        'org': short_org(chunk)})
    return out


def short_org(chunk):
    """小节「发文机关」→ 检索用的短名：首个机关 + 「等 N 部门」。

    只取事实（机关名就写在小节里），不推断该找谁写观点——那是检索之后的事。
    括注（「国务院（国家发展改革委、商务部编制）」的括号部分）只保留主机关，
    检索式里塞一串编制单位反而搜不准。
    """
    m = ORG.search(chunk)
    if not m:
        return ''
    raw = re.sub(r'（[^）]*）|\([^)]*\)', '', m.group(1))
    names = [x.strip() for x in raw.split('、') if x.strip()]
    if not names:
        return ''
    return names[0] + (f'等 {len(names)} 部门' if len(names) > 1 else '')


def search_hint(x):
    """一行「怎么搜」：机关 + 标题主干。只打印，不写盘、不生成观点。

    为什么加：欠账清单只给标题，等于把「去搜什么」也留给人工重新想一遍；
    2026-10-26 的审计里，50 多个无观点小节的补录长期停滞，卡点往往不是写作而是
    「不知道从哪找」。这里只把**已写在卡片里的事实**（发文机关、政策名）整理成检索式。

    标题主干是机械去噪（去书名号／去「关于」「的若干意见」这类文种词），搜不准就当
    提示忽略；**不许**把这里的结果当检索结论——它没有联网，也没有看过任何原文。
    """
    title = re.sub(r'[《》""''（）()]', '', x['title'])
    kernel = TITLE_NOISE.sub('', title).strip() or title
    head = f'{x["org"]} ' if x.get('org') else ''
    return f'     检索：{head}{kernel[:30]}'


def scan_signals():
    """返回 {页名: {'n': 条数, 'last': date|None}}"""
    out = {}
    for p in sorted(SIGNAL_DIR.glob('*.md')):
        if p.name.startswith('.'):
            continue
        items = [d(m.group(1)) for m in SECTION_HEAD.finditer(read(p))]
        items = [x for x in items if x]
        out[p.stem.replace('政策信号-', '')] = {
            'n': len(items), 'last': max(items) if items else None}
    return out


def last_round():
    """台账里最近一条真正的采集轮次（跳过手工补录等非轮次行）"""
    rows = table_rows(section(read(LEDGER), '运行台账'))
    best = None
    for r in rows:
        if len(r) < 2:
            continue
        if '轮' not in r[1] or '第' not in r[1]:
            continue
        dt = d(r[0])
        if dt and (best is None or dt > best):
            best = dt
    return best


def claim_ok(last_claim):
    """能否领活：从未领过 → 能；距上次领取满 `GATE_DAYS` 天 → 能。

    闸门原先挂在「体检最近运行日」上（2026-10-28 解耦）。那样等于让补采节奏被体检
    频率绑架：想降体检频率就拖慢存量清零，想加快补采就得每 2 天写三页报告。而闸门
    本来要防的只是「一次领太多、领了不补」，与体检跑没跑没有因果关系。
    """
    if last_claim is None:
        return True
    return (TODAY - last_claim).days >= GATE_DAYS


def ledger_gap_cursor():
    """任务台账「断档补采游标」：{start, end, done, left, claim, status}
    表列：断档区间 | 总天数 | 已补至 | 剩余天数 | 最近领取 | 状态"""
    for r in table_rows(section(read(TASKS), '断档补采游标')):
        if len(r) < 4:
            continue
        m = re.match(r'(\d{4}-\d{2}-\d{2})\s*[~～-]\s*(\d{4}-\d{2}-\d{2})', r[0])
        if not m:
            continue
        a, b = d(m.group(1)), d(m.group(2))
        done = d(r[2]) if d(r[2]) else None
        left = 0
        if done and b:
            left = (b - done).days
        return {'start': a, 'end': b, 'done': done, 'left': left,
                'claim': d(r[4]) if len(r) > 4 else None,
                'status': r[5] if len(r) > 5 else '', 'raw': r}
    return None


def stock_rows():
    """任务台账「存量补采队列」：{页: {first, done, left, claim, status}}
    表列固定为：页 | 首次空白日 | 已补至 | 剩余天数 | 最近领取 | 状态
    「最近领取」记日期而非 ISO 周——闸门已由体检节拍决定。"""
    out = {}
    for r in table_rows(section(read(TASKS), '存量补采队列')):
        if len(r) < 6:
            continue
        out[r[0]] = {'first': d(r[1]), 'done': d(r[2]),
                     'left': r[3], 'claim': d(r[4]), 'status': r[5]}
    return out


def debt_cursor():
    """任务台账「清欠进度」：最近一周的 {week, done}"""
    rows = table_rows(section(read(TASKS), '清欠进度'))
    got = []
    for r in rows:
        if len(r) < 3:
            continue
        try:
            done = int(re.sub(r'\D', '', r[2]) or 0)
        except ValueError:
            done = 0
        got.append({'week': r[0], 'done': done, 'status': r[-1]})
    return got


# ────────────────────── 计算 ──────────────────────

def _views(cards):
    """① 观点：T+1 必清（新政策沉淀成欠账是最主要的漏口）＋存量。

    分界就是「昨天」：昨天及今天新增的走必清，更早的进配额清单。
    """
    a = [c for c in cards if c['state'] == 'a']
    b = [c for c in cards if c['state'] == 'b']
    c_ = [c for c in cards if c['state'] == 'c']
    total = len(cards)
    cov = (len(a) / total * 100) if total else 0.0

    cut = TODAY - datetime.timedelta(days=1)
    fresh = sorted([x for x in b + c_ if d(x['date']) and d(x['date']) >= cut],
                   key=lambda x: x['date'], reverse=True)
    back = sorted([x for x in b + c_ if d(x['date']) and d(x['date']) < cut],
                  key=lambda x: (x['date'], x['card']))

    wk = iso_week(TODAY)
    cur = next((x for x in debt_cursor() if x['week'] == wk), None)
    done_wk = cur['done'] if cur else 0
    return {'total': total, 'a': len(a), 'b': len(b), 'c': len(c_),
            'cov': round(cov, 1), 'fresh': fresh, 'back': back,
            'back_total': len(b) + len(c_), 'weekly_done': done_wk,
            'weekly_need': max(0, VIEW_WEEKLY - done_wk),
            'quota_today': VIEW_DAILY,
            'weeks_left': round(max(1.0, (7 - TODAY.isoweekday() + 1) / 5.0), 1)}


def _gap():
    """② 政策断档：短断档一轮补完，长断档分批且每批等一次体检。

    领取闸门挂在体检节拍上——体检每 2 天一次，按周记会丢掉两次体检之间的机会。
    """
    lr = last_round()
    gap = {'last': lr, 'days': (TODAY - lr).days if lr else None}
    if lr:
        gap['start'] = lr + datetime.timedelta(days=1)
        gap['span_days'] = (TODAY - lr).days
    cursor = ledger_gap_cursor()
    batch = None
    if lr and (TODAY - lr).days >= 1:
        start = gap['start']
        if cursor and cursor['done'] and cursor['done'] >= start:
            start = cursor['done'] + datetime.timedelta(days=1)
        if start <= TODAY:
            short = (TODAY - lr).days <= GAP_TRIGGER
            end = TODAY if short else min(
                start + datetime.timedelta(days=GAP_BATCH - 1), TODAY)
            claim = cursor['claim'] if cursor else None
            batch = {'start': start, 'end': end,
                     'left_after': (TODAY - end).days, 'short': short,
                     'wait': (not short) and not claim_ok(claim),
                     'claim': claim}
    return gap, batch, cursor


def _stock(sig):
    """③ 存量页队列：断档超 STOCK_GAP 的信号页，每次体检后只释放一页。"""
    old = stock_rows()
    queue = []
    for page, info in sig.items():
        g = (TODAY - info['last']).days if info['last'] else 9999
        if g <= STOCK_GAP:
            continue
        first = (info['last'] + datetime.timedelta(days=1)) if info['last'] else None
        done = old.get(page, {}).get('done')
        if done and first and done >= TODAY:
            continue
        begin = done + datetime.timedelta(days=1) if done else first
        if begin and begin > TODAY:
            begin = None
        end = min(begin + datetime.timedelta(days=STOCK_BATCH - 1), TODAY) if begin else None
        queue.append({
            'page': page, 'gap': g, 'last': info['last'], 'n': info['n'],
            'first': first, 'begin': begin, 'end': end,
            'left': (TODAY - end).days if end else None,
            'status': old.get(page, {}).get('status', '未领'),
            'claim_date': old.get(page, {}).get('claim'),
            'claimable': claim_ok(old.get(page, {}).get('claim')),
        })
    queue.sort(key=lambda x: -x['gap'])
    claimed = [q for q in queue if q['claimable']]
    inq = {q['page'] for q in queue}
    stale = [p for p, v in old.items()
             if p not in inq and '✅' not in v.get('status', '')]
    return queue, claimed, stale


def _todo():
    """④ 任务台账待办：两张表各取一遍，只派「负责环节＝采集」的活。

    「等你拍板」那张表的行不进采集清单——它等的是人拍板，派给采集只会让它一直躺在待办里，
    看起来像「没做完」。这一类单列一段交给读者，与「机器自己能做」分开摆。
    归属不看行里的字，看它在哪张表（表名就是负责人，见 domain/ledger）。
    """
    out, mine = [], []
    for owner, _head, rows in ledger_tables(read(TASKS)):
        for _i, r in rows:
            if len(r) < len(LEDGER_COLS):
                continue
            status = r[col('状态')]
            if any(k in status for k in ('✅', '🚫')):
                continue
            item = {'id': r[col('编号')], 'found': r[col('首次发现')],
                    'issue': r[col('问题')], 'type': r[col('类型')],
                    'status': status, 'owner': owner}
            if owner == '用户':
                mine.append(item)
            elif '采集' in r[col('负责环节')]:
                out.append(item)
    return out, mine


def plan(round_no=None, top=8):
    """四块欠账各自的取数与判定分开算，这里只负责拼装。"""
    cards = scan_cards()
    sig = scan_signals()
    gap, batch, cursor = _gap()
    queue, claimed, stale = _stock(sig)
    todo, mine = _todo()

    return {
        'today': TODAY.isoformat(), 'week': iso_week(TODAY), 'round': round_no,
        'gate': GATE_DAYS,
        'views': _views(cards),
        'gap': gap, 'batch': batch, 'cursor': cursor,
        'stock': queue, 'claim': claimed, 'stale': stale,
        'todo': todo, 'mine': mine,
        'top': top,
    }


# ────────────────────── 输出 ──────────────────────

def tag(x):
    return {'占位': '（待补全）', '无标题': '（无「各方观点」标题）',
            '缺辨析': '（缺「观点辨析」）'}.get(x.get('kind', ''), '')


def pr_header(p):
    v = p['views']
    print(f'=== 派活清单 · {p["today"]}（{p["week"]}'
          + (f' · 第 {p["round"]} 轮' if p['round'] else '') + '）===')
    print(f'观点覆盖率 {v["cov"]}%（完整 {v["a"]} / 待补全 {v["b"]} / '
          f'无观点节 {v["c"]} / 共 {v["total"]}）')
    print()


def pr_todo(p):
    print('【1·台账待办（负责环节＝采集）】' + ('无' if not p['todo'] else f'{len(p["todo"])} 项'))
    for t in p['todo']:
        print(f'  {t["id"]}｜{re.sub(r"[*`]", "", t["issue"])[:44]}｜{t["status"]}')
    if p['mine']:
        print(f'\n【1b·等你拍板（负责人＝用户，共 {len(p["mine"])} 项）】'
              f'这些机器做不了，也不该由自动化代签')
        for t in p['mine']:
            print(f'  {t["id"]}｜{re.sub(r"[*`]", "", t["issue"])[:52]}｜{t["status"]}')


def pr_gap(p):
    g = p['gap']
    if g['days'] is None:
        print('\n【2·政策断档】台账里找不到采集轮次记录 → 视为未知，按近 14 天全段覆盖')
        return
    if g['days'] <= 1:
        print(f'\n【2·政策断档】上次采集 {g["last"]}（{g["days"]} 天前）→ 常规窗口，无断档')
        return
    print(f'\n【2·政策断档】上次采集 {g["last"]}，已断 {g["days"]} 天'
          f'（{span(g["start"], TODAY)}）')
    bt = p['batch']
    if not bt:
        print('  游标已补到今天，但台账日期仍落后 → 检查台账是否漏记')
        return
    if bt['short']:
        print(f'  断档 ≤{GAP_TRIGGER} 天，本轮一次补完 {span(bt["start"], bt["end"])}'
              f'（短断档不等闸门，等两天反而把窗口拖长）')
    elif bt['wait']:
        print(f'  断档 >{GAP_TRIGGER} 天，按 {GAP_BATCH} 天/批推进；'
              f'**本批等闸门释放**（上次领取 {bt["claim"] or "—"}，'
              f'须满 {p["gate"]} 天）')
        print('  → 本周期只补当日窗口，不要整段扫；闸门释放后再补这一段')
    else:
        print(f'  本批补 {span(bt["start"], bt["end"])}'
              f'（{GAP_BATCH} 天/批，补完还剩 {bt["left_after"]} 天）')
    if not bt['wait']:
        print('  补完把任务台账「断档补采游标」改成：')
        print(f'  | {span(g["start"], TODAY)} | {g["days"]} | {bt["end"]} | '
              f'{bt["left_after"]} | {p["today"]} | '
              f'{"补采中" if bt["left_after"] else "✅ 已完成"} |')


def pr_stock(p):
    q = p['stock']
    print(f'\n【3·存量补采队列（信号页断档 >{STOCK_GAP} 天）】{len(q)} 页'
          f'　|　每满 {p["gate"]} 天领 {CLAIM_PER_CHECK} 页（闸门按上次领取日算）')
    for x in q:
        flag = '← 本次领这页' if p['claim'] and x is p['claim'][0] else ''
        got = f'｜已领 {x["claim_date"]}' if x['claim_date'] else ''
        print(f'  {x["page"]:<14}断档 {x["gap"]:>4} 天（最近 {x["last"] or "—"}，共 {x["n"]} 条）'
              f'{got} {flag}')
    if p['claim']:
        x = p['claim'][0]
        print(f'  本周期窗口：{x["page"]} 页 {span(x["begin"], x["end"])}'
              f'（每批 {STOCK_BATCH} 天，不追全段）')
        print('  领完把任务台账「存量补采队列」改成：')
        print(f'  | {x["page"]} | {x["first"] or "—"} | {x["end"]} | '
              f'{x["left"]} | {p["today"]} | 补采中 |')
    else:
        print(f'  本周期已领过（上次 {q[0]["claim_date"] if q else "—"}），'
              f'下个页面等闸门释放（距上次领取满 {p["gate"]} 天）')
    if p['stale']:
        print(f'  可归档（断档已 ≤{STOCK_GAP} 天或已清零，把状态改 ✅）：'
              + '、'.join(p['stale']))


def pr_views(p):
    v = p['views']
    print(f'\n【4·观点·T+1 必清（昨日及今天新增）】{len(v["fresh"])} 个')
    for x in v['fresh']:
        print(f'  {x["card"]} → {x["date"]} · {x["title"][:40]}{tag(x)}')
        print(search_hint(x))

    print(f'\n【5·观点·存量（配额 {VIEW_DAILY} 个/轮，本周已清 {v["weekly_done"]}/{VIEW_WEEKLY}'
          + (f'，本周还需 {v["weekly_need"]} 个' if v['weekly_need'] else '，本周目标已达成') + '）】')
    for x in v['back'][:p['top']]:
        print(f'  {x["date"]} · {x["card"]} → {x["title"][:38]}{tag(x)}')
        print(search_hint(x))
    if len(v['back']) > p['top']:
        print(f'  …… 另有 {len(v["back"]) - p["top"]} 个，按日期从旧到新取')
    if v['back_total']:
        print(f'  余额 {v["back_total"]} 个；按 {VIEW_DAILY} 个/轮约需 '
              f'{v["back_total"] // VIEW_DAILY + 1} 轮，按周目标 {VIEW_WEEKLY} 个约需 '
              f'{v["back_total"] / VIEW_WEEKLY:.1f} 周')
    print(f'\n注：每条观点 5~8 条、至少覆盖 {STANCE_MIN} 类主体'
          f'（{"／".join(STANCES)}），逐条须有可访问来源——口径见 AGENTS 第六节「七要素」。')
    print('注：T+1 必清优先于存量——新政策当天不闭环，就会变成明天的存量，欠账永远追不上。')


def pr(p):
    """输出顺序 ＝ 执行顺序：台账待办 → 断档 → 存量页 → 观点（T+1）→ 观点（存量）。"""
    pr_header(p)
    pr_todo(p)
    pr_gap(p)
    pr_stock(p)
    pr_views(p)
    return 0


def run(argv=None):
    ap = argparse.ArgumentParser(description='派活器：本轮待办清单')
    ap.add_argument('--round', type=int, default=None, help='只影响标题里的轮次号')
    ap.add_argument('--top', type=int, default=8, help='存量观点清单最多列几条')
    ap.add_argument('--json', action='store_true', help='机器可读输出')
    args = ap.parse_args(list(argv or []))

    if not CARD_DIR.exists():
        print(f'✗ 未找到产业卡目录：{CARD_DIR}')
        return 0
    p = plan(args.round, args.top)

    if args.json:
        p2 = dict(p)
        p2['views'] = {k: v for k, v in p['views'].items() if k not in ('fresh', 'back')}
        p2['stock'] = [{k: (str(v) if isinstance(v, datetime.date) else v)
                        for k, v in x.items()} for x in p['stock']]
        p2['gap'] = {k: (str(v) if isinstance(v, datetime.date) else v)
                     for k, v in p['gap'].items()}
        p2['batch'] = ({k: (str(v) if isinstance(v, datetime.date) else v)
                        for k, v in p['batch'].items()} if p['batch'] else None)
        p2['views']['fresh_n'] = len(p['views']['fresh'])
        p2['views']['back_n'] = len(p['views']['back'])
        print(json.dumps(p2, ensure_ascii=False, indent=2, default=str))
        return 0

    return pr(p)

