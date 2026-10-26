#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作：fetch —— 把卡片里的「政策原文」抓成落盘的一手存档。

用法
----
    python3 tools/run.py fetch                   抓「今天 + 昨天」（采集窗口就是两天）
    python3 tools/run.py fetch --date 2026-10-26 只抓某一天
    python3 tools/run.py fetch --since 2026-09-26 --until 2026-10-26    补一段
    python3 tools/run.py fetch --dry-run         只说会写哪些，一个字节都不写
    python3 tools/run.py fetch --keep            把原始页留在 .cache/fetch/ 便于复核

它替掉的是什么
--------------
此前「顺手存一手」是提示词里的一段手工动作：打开原文、复制正文、存文件、贴附件。
三件事做不到：**每天没人真的做**、**做了也不知道有没有漏**、**做漏了不报错**。
现在它是同一条命令的第一步，跑完自己给出「窗口内 N 条／新存 X／无一手源 Z」——
漏没漏，看数字。

三条边界（故意的）
------------------
1. **只写 `raw/articles/`，不碰卡片。** 卡片是采集写的，抓取脚本改卡片会让
   「谁改了政策事实」变成一笔糊涂账。
2. **只增不改。** 同一 URL 已存过就跳过；要重存先改卡片里的链接（那才是新证据）。
3. **无一手源的不猜。** 卡片链接是门户、栏目页、或打不开的，只报出来让采集登记台账，
   不拿转述顶原文——把二手当一手存下来，是这个库最贵的错。

退出码：0 = 跑完了（失败逐条列在明细里，那是欠账不是故障）；
        1 = 库不可写；2 = 参数非法。
"""
import argparse
import datetime
import re
import shutil
import tempfile
import time
from pathlib import Path

from pkb.core import ARTICLE_DIR, CARD_DIR, read, web, doc
from pkb.domain import sources

ORIGIN, MEDIA, NOT_FIRST = sources.LEVELS          # 口径只从 domain 取，不写裸字符串
SEC = re.compile(r'^### (\d{4}-\d{2}-\d{2}) · (.+?)\s*$')
STOP = re.compile(r'^#{2,3} ')
LINK = re.compile(r'\[政策原文\]\((https?://[^)\s]+)\)')
BARE = re.compile(r'政策原文[^\n]{0,20}?(https?://[^\s)）|]+)')
OFFICE = re.compile(r'\*\*发文机关\*\*[：:]\s*([^｜|\n]+)')
DOCNO = re.compile(r'\*\*文号\*\*[：:]\s*([^｜|\n]+)')
STORED = re.compile(r'^原文链接:\s*(\S+)', re.M)
# 卡片里填成占位符／截断的链接（`t20261023_xxx.html`）。这不是「抓不到」，
# 是**卡片本身写错了**——报成「取回失败」会让采集去重试一个不存在的地址。
PLACEHOLDER = re.compile(r'xxx|\*\*\*|待补|todo', re.I)
MAX_ATT = 6
THROTTLE = 0.4          # 秒。批量补采时限流，条间留一点间隔比整片超时快
# 正文少于这个数（字符）就认为没抽到——通知类短是短，但不至于 120 字都没有
MIN_BODY = 120


def parse_args(rest):
    """返回 dict；参数非法返回 None（由 run 转成 exit 2）。"""
    ap = argparse.ArgumentParser(prog='run.py fetch', add_help=False)
    ap.add_argument('--date')
    ap.add_argument('--since')
    ap.add_argument('--until')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--keep', action='store_true')
    try:
        a = ap.parse_args(rest or [])
    except SystemExit:
        return None
    today = datetime.date.today()
    try:
        if a.date:
            start = end = datetime.date.fromisoformat(a.date)
        else:
            start = datetime.date.fromisoformat(a.since) if a.since else today - datetime.timedelta(days=1)
            end = datetime.date.fromisoformat(a.until) if a.until else today
    except ValueError:
        return None
    if start > end:
        return None
    return {'start': start, 'end': end, 'dry': a.dry_run, 'keep': a.keep}


def blocks(text):
    """按 `### 日期 · 标题` 切小节：[(日期, 标题, 小节正文)]。

    只在二级/三级标题处切断——小节内部的粗体行（`**核心要点**`）属于本小节，
    切掉就会把「政策原文」那一行留在上一节里，链接串到别人头上。
    """
    out, cur = [], None
    for line in text.splitlines():
        m = SEC.match(line)
        if m:
            if cur:
                out.append(cur)
            cur = [m.group(1), m.group(2).strip(), [line]]
        elif cur is not None:
            if STOP.match(line):
                out.append(cur)
                cur = None
            else:
                cur[2].append(line)
    if cur:
        out.append(cur)
    return [(d, t, '\n'.join(ls)) for d, t, ls in out]


def entry_of(path, date, title, body):
    """一条政策小节 → 抓取任务。缺链接就是缺链接，不拿标题去搜（搜出来未必是同一份）。"""
    m = LINK.search(body) or BARE.search(body)
    url = m.group(1).rstrip('.,;') if m else ''
    org, no = OFFICE.search(body), DOCNO.search(body)
    return {'date': date, 'title': title, 'card': path.stem, 'url': url,
            'org': org.group(1).strip() if org else '',
            'no': no.group(1).strip() if no else '',
            'level': sources.level(url), 'why': sources.why(url)}


def collect(start, end):
    """窗口内的全部政策小节，按日期正序（写盘顺序稳定，重名后缀才不乱跳）。"""
    out = []
    if not CARD_DIR.exists():
        return out
    for p in sorted(CARD_DIR.glob('*.md')):
        for date, title, body in blocks(read(p, '')):
            if start.isoformat() <= date <= end.isoformat():
                out.append(entry_of(p, date, title, body))
    out.sort(key=lambda e: (e['date'], e['card'], e['title']))
    return out


def stored_urls():
    """已存档的原文链接集合——幂等的唯一依据（文件名不可靠，标题天天改写）。"""
    urls = set()
    if not ARTICLE_DIR.exists():
        return urls
    for p in ARTICLE_DIR.glob('*.md'):
        urls.update(STORED.findall(read(p, '')))
    return urls


def san(s, n=70):
    s = re.sub(r'[\\/:*?<>|]', '', s or '')
    return re.sub(r'\s+', '', s).strip('《》.')[:n]


def clean_no(no):
    """文号只留可辨认的一段：`〔年份〕序号` 或 `年份年第序号`。

    不把「商务部 海关总署公告」这类机关前缀搬进文件名——机关已经是第二段了，
    再抄一遍只会把文件名撑长。括号里的解释性文字（（附清单）之类）同样不进。
    """
    no = re.sub(r'（[^）]*）|\([^)]*\)', '', no or '').strip()
    for pat, n in ((r'([\u4e00-\u9fa5]{0,10}[〔\[]\d{4}[〕\]]\s*\d+\s*号)', 24),
                   (r'(\d{4}年第\s*\d+\s*号)', 20),
                   (r'(第\s*\d+\s*号)', 12)):
        m = re.search(pat, no)
        if m:
            return san(m.group(1), n)
    return ''


def fname(e):
    """日期_机关_文号_标题.md（与库内既有 45 份同一规则，改规则要整批重命名）。"""
    org = re.sub(r'（.*', '', san(re.split(r'[、，,]', e['org'] or '未标机关')[0], 12))
    parts = [e['date'], org] + ([clean_no(e['no'])] if clean_no(e['no']) else [])
    return '_'.join(parts + [san(re.sub(r'（[^）]*）$', '', e['title']), 60)]) + '.md'


def fetch_attachments(atts, idx, tmpdir):
    """下载附件并转文本若干段。返回 (markdown 片段, 转成的份数, 未转的格式集合)。"""
    out, ok, seen, skipped = [], 0, 0, set()
    for name, url in atts[:MAX_ATT]:
        ext = web.suffix(url)
        seen += 1
        target = Path(tmpdir) / f'{idx:02d}_{seen}.{ext or "bin"}'
        code, body, _ = web.fetch(url, timeout=40)
        if body:
            target.write_bytes(body)
        text = doc.to_text(target) if (body and ext and not doc.unsupported(ext)) else ''
        if text and len(text) >= 40:
            ok += 1
        else:
            skipped.add(ext or '未知')
            text = '（该附件未能转为文本，请在原文件核阅）'
        out.append(f'### 附件 {seen}：{name}\n\n> 原文件 <{url}>（{ext}，HTTP {code}）\n\n{text}')
    return '\n\n'.join(out), ok, skipped


def quality_of(e, body, n_att):
    """正文完整性怎么写才不算撒谎：短就是短，别一律填「完整」。

    「完整」这个词有具体含义——读者据此判断能不能只靠这份存档下结论。
    2026-10-26 实测：一份《印发通知》正文只有 396 字、清单是图片，
    存档却写着「完整」，等于告诉后来的人「不用再核了」。
    """
    if e['level'] == MEDIA:
        return '报道全文（非文件本身，须回原文核）'
    if len(body) >= 600:
        return '完整'
    if n_att:
        return f'正文较短（{len(body)} 字），实质内容在附件'
    return f'正文较短（{len(body)} 字），实质内容可能在图片或另页'


def build(e, lines, degraded, atts_md, n_att, n_ok):
    """组装存档正文：frontmatter + 判定依据 + 正文 + 附件原文。"""
    body = '\n\n'.join(lines)
    quality = quality_of(e, body, n_att)
    fm = ['---', '类型: 一手存档', f'政策日期: {e["date"]}',
          f'发文机关: {e["org"] or "未标"}', f'文号: {e["no"] or "无"}',
          f'原文链接: {e["url"]}', f'存档级别: {e["level"]}',
          f'正文完整性: {quality}', f'附件数: {n_att}', f'附件转文本: {n_ok}',
          'tags: [一手源]', '---', '']
    head = [f'# {e["title"]}', '',
            f'> 存档 {datetime.datetime.now():%Y-%m-%d %H:%M} ｜ 来源 <{e["url"]}>',
            f'> 级别：{e["level"]}（{e["why"]}）',
            f'> 卡片：{e["card"]}']
    if degraded:
        head.append('> ⚠ 该站证书校验未通过，内容已取回但未经传输层验证')
    if n_att:
        head.append('> 附件按原样转为文本，未做删减；清单类才算边界，通知书／申报表属程序类')
    return '\n'.join(fm + head) + '\n\n## 正文\n\n' + (body or '（正文未能抽取，见原文链接）') + \
        ('\n\n## 附件原文\n\n' + atts_md if atts_md else '') + '\n'


def attempt(e, idx, args, stats, tmpdir):
    """处理一条：跳过／不入档／抓取／写盘。返回 (动作标签, 说明)，由 main 统一打印。"""
    if not e['url']:
        stats['nofirst'] += 1
        return 'nofirst', '卡片无「政策原文」链接'
    if PLACEHOLDER.search(e['url']):
        stats['nofirst'] += 1
        return 'nofirst', '链接含占位符，卡片里填的不是完整地址'
    if e['url'] in stats['seen']:
        stats['skip'] += 1
        return 'skip', '已存档'
    if e['level'] == NOT_FIRST:
        stats['nofirst'] += 1
        return 'nofirst', e['why']
    if web.is_listing(e['url']):
        stats['nofirst'] += 1
        return 'nofirst', '链接是栏目页，无具体文件页'
    code, raw, degraded = web.fetch(e['url'])
    if not raw:
        stats['fail'] += 1
        why = f'HTTP {code}' if code else '无响应（超时或域名解析失败）'
        return 'fail', f'取回失败：{why}'
    h = web.decode(raw)
    lines = web.body_lines(h)
    body = '\n'.join(lines)
    if web.looks_binary(body):
        stats['fail'] += 1
        return 'fail', '取回的不是网页文本（二进制或压缩流解错），未落盘——别把乱码当正文存档'
    if len(body) < MIN_BODY:
        stats['fail'] += 1
        return 'fail', f'正文抽取为空（{len(body)} 字）'
    atts = web.attachments(h, e['url'])
    if args['keep']:
        keep_page(e, raw)
    if args['dry']:
        stats['new'] += 1
        return 'dry', f'{len(body)} 字，附件 {len(atts)}'
    return write_file(e, lines, degraded, atts, stats, tmpdir, idx)


def keep_page(e, raw):
    """`--keep`：原页留在 .cache/fetch/，抽取抽歪了有得查。不是库内容，不进 git。"""
    from pkb.core import CACHE_DIR
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / (fname(e)[:-3] + '.html')).write_bytes(raw)


def write_file(e, lines, degraded, atts, stats, tmpdir, idx):
    """落盘。附件先转文本再写，免得正文写完了附件还在失败。"""
    atts_md, n_ok, skipped = fetch_attachments(atts, idx, tmpdir)
    name = fname(e)
    dest, n = ARTICLE_DIR / name, 2
    while dest.exists():
        dest, n = ARTICLE_DIR / f'{name[:-3]}-{n}.md', n + 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build(e, lines, degraded, atts_md, len(atts), n_ok), encoding='utf-8')
    stats['seen'].add(e['url'])
    stats['new'] += 1
    stats['chars'] += len('\n'.join(lines))
    note = f'{len("\n".join(lines))} 字，附件 {len(atts)}（转成 {n_ok}）'
    if skipped:
        note += f'，未转：{"、".join(sorted(skipped))}'
    return 'new', f'{dest.name} ｜ {note}'


def run(argv=None):
    args = parse_args(list(argv or []))
    if args is None:
        print('✗ 参数不对。用法：fetch [--date YYYY-MM-DD] [--since 起 --until 止] [--dry-run] [--keep]')
        return 2
    if not ARTICLE_DIR.parent.exists():
        print(f'✗ 找不到 raw/ 目录：{ARTICLE_DIR.parent}（POLICY_KB_VAULT 设错了？）')
        return 1
    entries = collect(args['start'], args['end'])
    stats = {'new': 0, 'skip': 0, 'nofirst': 0, 'fail': 0, 'chars': 0, 'seen': stored_urls()}
    tmpdir = tempfile.mkdtemp(prefix='pkb-fetch-') if not args['dry'] else None
    print(f'\n【fetch】窗口 {args["start"]} ~ {args["end"]}，卡片内 {len(entries)} 条')
    try:
        for i, e in enumerate(entries, 1):
            tag, note = attempt(e, i, args, stats, tmpdir)
            mark = {'new': '✓ 新存', 'dry': '· 将存', 'skip': '· 跳过',
                    'nofirst': '! 无一手源', 'fail': '✗ 失败'}[tag]
            print(f'  {mark:<9} {e["date"]} {e["title"][:34]} ｜ {note}')
            if tag in ('new', 'dry'):
                time.sleep(THROTTLE)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    if args['dry']:
        print('\n（--dry-run：以上都还没写盘）')
    miss = stats['nofirst'] + stats['fail']
    print(f'\n▸摘要: fetch {args["start"]}~{args["end"]} 卡片 {len(entries)} 条 · '
          f'新存 {stats["new"]}（{stats["chars"]} 字）· 已存跳过 {stats["skip"]} · '
          f'无一手源 {stats["nofirst"]} · 抓取失败 {stats["fail"]}'
          + (f'  ← {miss} 条需登记台账' if miss else '  ✓'))
    return 0
