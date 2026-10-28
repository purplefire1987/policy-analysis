#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查库：给一个词、一条链、一段时间窗，回答「库里哪里有、在哪一行」。

为什么需要它
------------
这套工具原来十个动作**全在维护库**（存、检、修、派活），没有一个是「取」。
结果：规则、检查、台账都很厚，而回答一个政策问题仍要靠人肉 grep 四十万字符。
「存得住、检得出」不等于「查得到」——第三种能力要单独建。

它只做检索，不做判断：命中的原话照抄，不下结论、不合并同类项。
判断归周观点与分析报告，那两处有各自的判据。

两种口径，界限明确（2026-10-29 合并 `recent` 时定）
--------------------------------------------------
**检索**（给词／链／日期）回答「这个词在哪」，输出是「文件:起-止 + 命中行号」。
**总览**（给 `--days`）回答「这几天实际落了什么」，输出是分类计数 + 一行一条。

总览原来是一个独立动作 `recent`，两者共用同一批扫描结果，只是输出形态不同——
合并后由 `--days` 选择，但**两种口径不许混用参数**：混用会让输出形态随参数隐式
改变，而「同一个命令有两种说不清的形态」正是当初分成两个动作的原因。

用法（统一走入口）
----
    run.py query 出口管制                     # 全文：命中小节＋命中行号
    run.py query 出口管制 --since 2026-09-01  # 限时间窗
    run.py query --chain 金融强国             # 该链下全部政策小节
    run.py query 稀土 --full                  # 连小节正文一起打
    run.py query 房车 --notes                 # 连人的笔记（raw/notes）一起查
    run.py query --kind 政策 稀土             # 只查政策小节，不碰信号页
    run.py query --days 10 --kind 笔记         # 近 10 天新增了什么（原 `recent`）

恒 exit 0：这是取素材的，不是校验器。查不到会明说「0 处」，不静默。
参数用错 exit 2：形态选错必须当场报，不能跑出个看起来像结果的半成品。
"""
import argparse
import datetime
import re

from pkb.core import (CARD_DIR, CHAIN_DIR, NOTES_DIR, SIGNAL_DIR,
                      md_section_lines, read, scan_dated, scan_notes, summary)

DEFAULT_LIMIT = 40
DEFAULT_DAYS = 7
KINDS = ('政策', '信号', '笔记')


def collect(include_notes=False):
    """政策小节、信号条目（可选笔记）各扫一遍，统一成一种形状（带文件、行号、卡名）。

    `kind` 分开是因为三者含义不同：政策是已落定的文件，信号是表态，笔记是**人写的
    东西**。读者一眼要能分清，所以输出里标【政策】/【信号】/【笔记】，不混排成一张表。
    笔记默认不进来：它是人的私稿，混进政策检索会让「这条政策库里有没有」变得可疑。
    """
    out = []
    for sec in scan_dated(CARD_DIR):
        sec.update(kind='政策', dir=CARD_DIR)
        sec['card'] = re.sub(r'^政策卡片-|\.md$', '', sec['file'])
        out.append(sec)
    for sec in scan_dated(SIGNAL_DIR):
        sec.update(kind='信号', dir=SIGNAL_DIR)
        sec['card'] = re.sub(r'^政策信号-|\.md$', '', sec['file'])
        out.append(sec)
    if include_notes:
        for sec in scan_notes(NOTES_DIR):
            sec.update(kind='笔记', dir=NOTES_DIR, card='')
            out.append(sec)
    return out


def chain_cards(name):
    """一条链的「关联卡片」节里点到的卡名。链是目录，卡片才是内容——按链查等于按卡查。"""
    p = CHAIN_DIR / f'政策链-{name}.md'
    if not p.exists():
        return None
    body = '\n'.join(md_section_lines(read(p, ''), '关联卡片'))
    return {m for m in re.findall(r'\[\[政策卡片-([^]#|]+)', body)}


def card_keywords():
    """{卡名: [关键词]}，现读卡片 frontmatter。

    关键词此前是**只写不读**的字段（在必填表里，没有任何代码看它）。这里给它第一个
    消费端：读者用的词与政策用的词常不一样——查「旅居车」不命中，因为库里写「房车」。
    卡片关键词正是存这种别名的地方，所以检索时先按它兜一次底。
    """
    from pkb.core.fm import parse_fm
    out = {}
    for p in sorted(CARD_DIR.glob('*.md')):
        fm, _body = parse_fm(read(p, ''))
        kws = fm.get('关键词')
        if isinstance(kws, list):
            out[re.sub(r'^政策卡片-|\.md$', '', p.name)] = [
                str(k) for k in kws if str(k).strip()]
    return out


def kw_cards(keyword, mapping):
    """哪些卡的关键词接得住这个词（互为子串即算；短于 2 字不猜，那样几乎人人命中）。"""
    q = keyword.strip()
    if len(q) < 2:
        return []
    return [(card, k) for card, kws in mapping.items()
            for k in kws if q in k or (len(k) >= 2 and k in q)]


def body_text(sec):
    """小节正文（含标题行）。查询要的是原话，不做摘要——摘要就是判断。"""
    p = sec['dir'] / sec['file']
    lines = read(p, '').split('\n')
    return lines, lines[sec['start'] - 1:sec['end']]


def hits(sec, kw):
    """返回命中处的行号（1 基，相对文件）。标题行本身不算命中——那是已知的。"""
    lines, chunk = body_text(sec)
    base = sec['start']
    return [base + i + 1 for i, line in enumerate(chunk[1:]) if kw.lower() in line.lower()]


def select(secs, args, cards):
    """按链、类型、时间窗、关键词四层过滤。任一层没给就不筛，不猜默认值。"""
    picked = []
    for sec in secs:
        if cards is not None and sec['kind'] == '政策' and sec['card'] not in cards:
            continue
        if cards is not None and sec['kind'] != '政策':
            continue
        if args.kind and sec['kind'] not in args.kind:
            continue
        if args.since and sec['date'] < args.since:
            continue
        if args.until and sec['date'] > args.until:
            continue
        got = hits(sec, args.keyword) if args.keyword else []
        if args.keyword and not got:
            continue
        picked.append((sec, got))
    picked.sort(key=lambda x: (x[0]['date'], x[0]['title']), reverse=True)
    return picked


def show(picked, args):
    """一行一条：日期·标题，后面跟「文件:起-止」与命中行号。"""
    print(f'{"关键词「" + args.keyword + "」：" if args.keyword else ""}'
          f'命中 {len(picked)} 个小节'
          + (f'（只列最近 {args.limit} 个）' if len(picked) > args.limit else ''))
    if not picked:
        print('  （0 处。查不到就是查不到——换词、放宽时间窗，或这条政策库里确实没有）')
        return
    for sec, got in picked[:args.limit]:
        print(f'\n【{sec["kind"]}】{sec["date"] or "（无日期）"} · {sec["title"]}')
        print(f'    {sec["file"]}:{sec["start"]}-{sec["end"]}'
              + (f'　命中行 {", ".join(map(str, got))}' if got else ''))
        if args.full:
            _lines, chunk = body_text(sec)
            keep = ([line for i, line in enumerate(chunk) if (sec['start'] + i) in got]
                    if got else chunk)
            print('    ' + '\n    '.join(keep)[:args.limit_chars])


def window(items, since, kinds):
    """按日期窗与类型过滤。无日期的条目丢掉并在摘要里说一句，不替它猜日期。"""
    picked, undated = [], 0
    for it in items:
        if kinds and it['kind'] not in kinds:
            continue
        if not it['date']:
            undated += 1
            continue
        if it['date'] >= since:
            picked.append(it)
    picked.sort(key=lambda x: (x['date'], x['kind'], x['title']), reverse=True)
    return picked, undated


def overview(args):
    """`--days` 的总览口径：这一窗里实际落了什么，分类计数、一行一条。

    为什么不能省掉这个分支、让 `--days` 走检索口径：检索按「命中」筛，没有关键词时
    只能把全部小节铺出来，且不给分类计数——而周观点真正要问的是「这几天有没有东西
    进来」，空窗本身也是信息。
    """
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=max(args.days, 1) - 1)).isoformat()
    picked, undated = window(collect(include_notes=True), since, args.kind)

    cnt = {k: sum(1 for it in picked if it['kind'] == k) for k in KINDS}
    # 给了 --kind 就只列那几类（0 也列，那是「这一窗没有」）；没给就三类全列。
    keep = [k for k in KINDS if not args.kind or k in args.kind]
    print(f'最近 {args.days} 天（{since} ~ {today}）：'
          + ' · '.join(f'{k} {cnt[k]}' for k in keep))
    if not picked:
        print('  （0 条。空窗本身是信息：可能是没采到，也可能是这几天确实没有新文件。）')
    for it in picked[:args.limit]:
        print(f'{it["date"]}  【{it["kind"]}】{it["title"]}')
        print(f'          {it["file"]}:{it["start"]}-{it["end"]}')
    if len(picked) > args.limit:
        print(f'  …还有 {len(picked) - args.limit} 条，加 --limit 或缩 --days')
    if undated:
        print(f'  ! 另有 {undated} 条没有日期（笔记的 `日期` 字段空着），未计入——'
              '不替它猜一个日期')
    summary(f'近 {args.days} 天：' + '／'.join(f'{k} {cnt[k]}' for k in keep))
    return 0


def check_shape(ap, args):
    """两种口径不许混用参数。混了就是 exit 2，别让它跑出个半成品。

    错在调用方，不是库有问题——所以是 2（用法错）不是 1（检查不过）。
    """
    bad = [n for n, v in (('关键词', args.keyword), ('--chain', args.chain),
                          ('--since', args.since), ('--until', args.until),
                          ('--full', args.full)) if v]
    if bad:
        ap.error(f'--days 是总览口径，不能与 {"、".join(bad)} 同用。'
                 f'要查具体内容请改用 --since {args.since or "YYYY-MM-DD"}；'
                 f'要两种都要，分两次跑。')


def run(argv=None):
    ap = argparse.ArgumentParser(prog='run.py query', description='查库：词／链／时间窗／近 N 天')
    ap.add_argument('keyword_pos', nargs='?', metavar='关键词', help='全文检索的词')
    ap.add_argument('--chain', help='只查一条链下的政策（如 金融强国）')
    ap.add_argument('--since', help='起始日期 YYYY-MM-DD（含）')
    ap.add_argument('--until', help='截止日期 YYYY-MM-DD（含）')
    ap.add_argument('--days', type=int, help='近 N 天总览（默认口径 7 天，见 --kind）；'
                                            '与 --since/--until/--chain/--full 互斥')
    ap.add_argument('--kind', action='append', choices=KINDS,
                    help='限定类型，可重复给；选「笔记」会自动把 raw/notes 纳入')
    ap.add_argument('--full', action='store_true', help='连小节正文一起打')
    ap.add_argument('--notes', action='store_true', help='连 raw/notes 里人的笔记一起查')
    ap.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                    help=f'最多列几条（默认 {DEFAULT_LIMIT}）')
    ap.add_argument('--limit-chars', type=int, default=800, dest='limit_chars',
                    help='--full 时每条最多字符（默认 800）')
    args = ap.parse_args(list(argv or []))
    args.keyword = (args.keyword_pos or '').strip()

    if args.days is not None:
        check_shape(ap, args)
        return overview(args)

    if not (args.keyword or args.chain or args.since or args.until) and not args.notes:
        ap.print_help()
        summary('未给检索条件，无结论')
        return 0

    cards = None
    if args.chain:
        cards = chain_cards(args.chain)
        if cards is None:
            print(f'✗ 没有这条链：政策链-{args.chain}.md（链名以 index.md 为准）')
            summary(f'链不存在：{args.chain}')
            return 0
        if not cards:
            print(f'⚠ 政策链-{args.chain}.md 的「关联卡片」节没点到任何卡——链是空的')

    with_notes = args.notes or '笔记' in (args.kind or ())
    selected = select(collect(with_notes), args, cards)
    show(selected, args)

    if args.keyword:
        kw = kw_cards(args.keyword, card_keywords())
        if kw:
            print(f'\n这词也在卡片关键词里（{len(kw)} 处）——按卡看得到这块的全部政策，'
                  f'不管正文有没有写这个说法：')
            for card, k in kw[:8]:
                print(f'  {card}｜关键词「{k}」→ run.py trace --card {card}')

    scope = '／'.join(x for x in (
        f'链 {args.chain}' if args.chain else '',
        f'{args.since or "…"}~{args.until or "…"}' if (args.since or args.until) else '',
        f'词「{args.keyword}」' if args.keyword else '',
        '类 ' + '/'.join(args.kind) if args.kind else '',
        '含笔记' if with_notes else '') if x) or '全库'
    summary(f'查询 {scope}：命中 {len(selected)} 个小节'
            + (f'（只列 {args.limit} 个）' if len(selected) > args.limit else ''))
    return 0
