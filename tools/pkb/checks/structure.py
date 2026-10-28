#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政策知识库结构校验。

用途：结构变更（重构、批量替换、字段迁移、模板改版）之后必跑，抓批量事故；
      日常也可跑，作为周观点产出前的底座检查。

检查 7 类：
  [1] 产业卡 frontmatter 完整性与取值合规（枚举、tags 数组写法、名称三字段一致）
      ＋「基本信息」callout 五项与源值一致
  [2] 产业卡数值一致性（政策数=小节数、发布日期=最新、时间跨度首尾）
  [3] 政策小节结构：模板每一栏都在（小标题、文号、生效日期、影响判断三行）
      ＋ 日期严格倒序 ＋ 标题格式
  [4] 政策链与产业卡双向一致（主题匹配、关联卡片、所属政策链）
  [5] 受控词表（index 第二节）与产业卡双向一致
  [6] 全库 wikilink 断链
  [8] 索引与总览的统计数字

口径（五领域/影响/状态/必填字段/体积线）在 pkb/domain/fields.py。
观点覆盖率不在这里——它已拆到 checks/views，两类问题语义不同（欠账不阻断）。
"""
import argparse
import difflib
import re
from collections import defaultdict

from pkb.core import (VAULT, CARD_DIR, CHAIN_DIR, INDEX, SKIP_DIRS,
                      parse_fm, extract_sections, all_names, FM_RE,
                      Result, Verdict)
from pkb.domain import DOMAINS, IMPACTS, STATUSES, REQUIRED_FIELDS, CARD_SIZE_WARN
# 模板里的结构名（callout 五项、小节小标题、影响判断三行）**不进 domain.__all__**：
# 口径扫描以「代码常量与 domain 某取值逐字相同」为判据，而这些是通用词
# （「关键词」「影响判断」在文档里到处都是），进扫描词典只会误伤正确写法。
# 同 ledger 那两张表的处理（见 domain/__init__ 说明）。
from pkb.domain.fields import CARD_INFO_ITEMS, SECTION_ELEMS, IMPACT_FIELDS

THEME_FILE = INDEX   # 受控词表已并入 index.md 第二节（2026-10-24 三合一）

issues = defaultdict(list)   # 类别 -> [(对象, 问题)]，阻断
warns = defaultdict(list)    # 警告，不阻断


def add(bucket, cat, obj, msg):
    bucket[cat].append((obj, msg))


def raw_fm_text(text):
    """frontmatter 原文（用于识别字段的写法形式，如 tags 是否被写成多行列表）。"""
    m = FM_RE.match(text)
    return m.group(1) if m else ''


def load_theme_words():
    """从 index.md 第二节读出 {大类: [产业卡名...]} 与全部标准词集合"""
    if not THEME_FILE.exists():
        return {}, set()
    t = THEME_FILE.read_text(encoding='utf-8')
    mapping = {}
    for line in t.split('\n'):
        if not line.startswith('|'):
            continue
        # 表格里 `[[政策链-X\|X]]` 用反斜杠转义竖线，先替换成哨兵，避免 split 切错列
        safe = line.replace('\\|', '\x00')
        cells = [c.strip().replace('\x00', '|') for c in safe.strip().strip('|').split('|')]
        if len(cells) < 2:
            continue
        m = re.search(r'政策链-([^|\]]+)', cells[0])
        if not m:
            continue
        chain = m.group(1).strip()
        words = [w.strip() for w in cells[1].split('、') if w.strip()]
        words = [re.sub(r'^\[\[|\]\]$', '', w) for w in words]
        mapping[chain] = words
    all_words = set(w for ws in mapping.values() for w in ws)
    return mapping, all_words


def load_all_md_names():
    """全库页面名集合（断链判断用）。"""
    return all_names()


def _check_tags(name, fm, text):
    """tags 必须是行内数组。解析结果看不出写法，所以要看 frontmatter 原文。"""
    tags = fm.get('tags')
    multiline = bool(re.search(r'(?m)^\s*tags\s*[:：]\s*\n\s*-\s', raw_fm_text(text)))
    if multiline or not isinstance(tags, list):
        add(issues, '1-frontmatter', name,
            f'tags 写成 `{tags}`，不是行内 YAML 数组（应写 [政策]，单行 `- 政策` 的写法本库不收）')
        return
    if '政策' not in tags:
        add(issues, '1-frontmatter', name, f'tags 缺基础标签「政策」：{tags}')
    for t in tags:
        if not re.fullmatch(r'[\w\u4e00-\u9fff]+', t):
            add(issues, '1-frontmatter', name, f'tags 含脏值「{t}」')


def _check_keywords(name, fm, text):
    """关键词必须是行内数组，且每一项都是干净的一个词（2026-10-28 增）。

    为什么单列：这个字段从建库起就在 `REQUIRED_FIELDS` 里，却**没有任何代码读它的值**——
    只写不读，于是坏成什么样都没人知道。实际盘点：18 张是行内数组、11 张写成块式、
    4 张的行内数组里混着 Markdown 列表号（`[- 文化遗产, 旅游强国, …]`，解析出来第一项
    就叫「- 文化遗产」）。**同库三种写法、一种还带脏值**，而校验一条都没有。

    判据只认形态，不认好坏：关键词选得准不准是判断，脚本不该判（判了就是逼人凑数）。
    """
    kw = fm.get('关键词')
    raw = raw_fm_text(text)
    block = bool(re.search(r'(?m)^\s*关键词\s*[:：]\s*\n\s*-\s', raw))
    if block:
        add(issues, '1-frontmatter', name,
            '关键词写成块式列表，本库统一行内数组 `[词1, 词2]`（同 tags 的规矩）')
        return
    if not isinstance(kw, list):
        add(issues, '1-frontmatter', name, f'关键词不是数组：{str(kw)[:30]}')
        return
    if len(kw) < 3:
        add(warns, '1-frontmatter', name, f'关键词只有 {len(kw)} 个，检索时几乎不起作用')
    seen = set()
    for k in kw:
        if not isinstance(k, str) or not k.strip():
            add(issues, '1-frontmatter', name, f'关键词含空项：{kw}')
            break
        if re.match(r'^[-\*\s]', k):
            add(issues, '1-frontmatter', name,
                f'关键词「{k}」带 Markdown 列表号——写成了 `[- 词, 词]`，第一个词会变成「- 词」')
        if re.search(r'\s', k):
            add(issues, '1-frontmatter', name, f'关键词「{k}」含空格，一个词一项')
        if k in seen:
            add(issues, '1-frontmatter', name, f'关键词「{k}」重复')
        seen.add(k)


def _check_card_fields(name, fm, theme_words):
    """字段完整性、三字段一致、受控词与枚举——一张卡的 frontmatter 判据。"""
    for f in REQUIRED_FIELDS:
        if f not in fm or fm[f] == '' or fm[f] == []:
            if f in ('所属政策链',):          # 允许为空但会警告
                add(warns, '1-frontmatter', name, f'字段「{f}」为空')
            else:
                add(issues, '1-frontmatter', name, f'缺少字段「{f}」')

    for f in ('名称', '二级分类', '主题'):
        if fm.get(f) and fm[f] != name:
            add(issues, '1-frontmatter', name, f'「{f}」={fm[f]}，应为 {name}')

    if theme_words and fm.get('主题') and fm['主题'] not in theme_words:
        add(issues, '1-frontmatter', name, f'「主题」={fm["主题"]} 不在受控词表')

    if fm.get('领域') and fm['领域'] not in DOMAINS:
        add(issues, '1-frontmatter', name, f'「领域」={fm["领域"]} 不在允许值 {sorted(DOMAINS)}')
    if fm.get('影响') and fm['影响'] not in IMPACTS:
        add(issues, '1-frontmatter', name, f'「影响」={str(fm["影响"])[:24]} 不是 高/中/低')
    if fm.get('状态') and fm['状态'] not in STATUSES:
        add(issues, '1-frontmatter', name, f'「状态」={fm["状态"]} 不在允许值')


def _check_info_box(name, fm, body, secs):
    """「基本信息」callout：五项齐全，且三项可核的必须与源值一致（2026-10-28 增）。

    为什么单列：这块从建库起就**没有任何判据**，于是漂成什么样都没人知道。盘点时
    33 张卡全是四项（模板要求六项），其中「收录政策 N 项」与 frontmatter 的 `政策数`
    有 5 张已经对不上（养老卡写「3 项」而实际 1 条）；「发文机关」是各小节机关的
    手工汇总，养老卡拼成「国家发展改革委、民政部、国家卫生健康委、民政部、国务院」——
    民政部出现三次。**重复拼接是手工汇总必然的样子**，不是个别疏忽。

    所以「收录政策」这一项直接删掉（同一个量两处写必然漂，同第六节副本归零），
    剩下的五项里三项能逐字核：最新政策＝最新小节、所属政策链＝frontmatter、
    关键词＝frontmatter。「发文机关」只能核「没有重复项」——它是汇总，
    逐项核对要重算一遍汇总，等于把同一逻辑写两处。
    """
    head = body.split('\n## ')[0]
    if '> [!info]' not in head:
        add(issues, '1-frontmatter', name, '缺「> [!info] 基本信息」callout（模板第一屏）')
        return
    got = re.findall(r'(?m)^>\s*-\s*([^：:]+)[：:]', head)
    for item in CARD_INFO_ITEMS:
        if item not in got:
            add(issues, '1-frontmatter', name, f'基本信息缺「{item}」一行')

    newest = f'{secs[0][1]}（{secs[0][0]}）' if secs else ''
    m = re.search(r'(?m)^>\s*-\s*最新政策[：:]\s*(.+)$', head)
    if m and newest and m.group(1).strip() != newest:
        add(issues, '1-frontmatter', name,
            f'「最新政策」写「{m.group(1).strip()[:40]}」，最新小节是「{newest[:40]}」')

    raw_chain = re.sub(r'^\[\[|\]\]$', '', str(fm.get('所属政策链', '')).strip().strip('"'))
    m = re.search(r'(?m)^>\s*-\s*所属政策链[：:]\s*(.+)$', head)
    if m and raw_chain and raw_chain not in m.group(1) and m.group(1).strip() not in raw_chain:
        add(issues, '1-frontmatter', name,
            f'「所属政策链」写「{m.group(1).strip()[:30]}」，frontmatter 是「{raw_chain}」')

    kw = fm.get('关键词')
    m = re.search(r'(?m)^>\s*-\s*关键词[：:]\s*(.+)$', head)
    if m and isinstance(kw, list):
        if m.group(1).strip() != '、'.join(str(k) for k in kw):
            add(issues, '1-frontmatter', name,
                '基本信息里的关键词与 frontmatter 的 `关键词` 不一致（两处是同一个值，改一处要改两处）')

    m = re.search(r'(?m)^>\s*-\s*发文机关[：:]\s*(.+)$', head)
    if m:
        parts = [x.strip() for x in re.split(r'[、，,]', m.group(1)) if x.strip()]
        dup = {x for x in parts if parts.count(x) > 1}
        if dup:
            add(issues, '1-frontmatter', name,
                f'基本信息「发文机关」重复列出 {sorted(dup)}——汇总时没去重')


def check_cards(theme_words):
    cards = {}
    for p in sorted(CARD_DIR.glob('*.md')):
        name = p.stem.replace('政策卡片-', '')
        text = p.read_text(encoding='utf-8')
        fm, body = parse_fm(text)
        if not fm:
            add(issues, '1-frontmatter', name, '缺少 frontmatter')
            continue
        secs, bad = extract_sections(body)
        # 一次切好存进来：下面三处判据（callout／数值／每节栏位）都要用它，
        # 各切一遍等于同一件事写三遍，还多两次全库重扫。
        cards[name] = {'fm': fm, 'body': body, 'path': p, 'secs': secs, 'bad': bad}

        # 体积哨兵（只提示，不阻断）：卡越大，每次插入新政策要读入的 token 越多。
        # 这不是格式错误，是使用成本——所以放警告不放问题。
        if len(text) > CARD_SIZE_WARN:
            add(warns, '0-体积', name,
                f'{len(text)} 字符（≈{len(text) // 2} token），超 {CARD_SIZE_WARN} 提示线'
                '——改卡时只读卡头 40 行即可定位插入点，不必全文读')

        _check_card_fields(name, fm, theme_words)
        _check_tags(name, fm, text)
        _check_keywords(name, fm, text)
        _check_info_box(name, fm, body, secs)

    return cards


def check_numbers(cards):
    for name, c in cards.items():
        fm = c['fm']
        secs = c['secs']
        for t in c['bad']:
            add(issues, '3-小节', name, f'小节标题格式不符（应为 `### YYYY-MM-DD · 政策名`）：{t[:50]}')

        n_declared = fm.get('政策数', '')
        try:
            n_declared = int(n_declared)
        except ValueError:
            add(issues, '2-数值', name, f'「政策数」不是整数：{fm.get("政策数")}')
            n_declared = None
        if n_declared is not None and n_declared != len(secs):
            add(issues, '2-数值', name, f'政策数={n_declared}，实际小节 {len(secs)} 个')

        dates = [d for d, _, _, _ in secs]
        if dates:
            if fm.get('发布日期') and fm['发布日期'] != dates[0]:
                add(issues, '2-数值', name, f'发布日期={fm["发布日期"]}，最新小节为 {dates[0]}')
            span = fm.get('时间跨度', '')
            expect = f'{min(dates)} ~ {max(dates)}'
            if span and span.replace(' ', '') != expect.replace(' ', ''):
                add(issues, '2-数值', name, f'时间跨度="{span}"，应为 "{expect}"')

            for a, b in zip(dates, dates[1:]):
                if a < b:
                    add(issues, '3-小节', name, f'小节未按时间倒序：{a} 在 {b} 之后（应为新→旧）')
                    break


def _check_section(name, d, t, chunk):
    """一个小节的模板合规：小标题齐、有文号、有生效日期、影响判断三行（2026-10-28 增）。

    此前只查四个小标题，于是「文号」与「生效日期」两栏 157 个全节无一有，
    「影响判断」有 13 处写成整段论述而不是三行——**都不报错**。判据补到这一步，
    模板要求的每一栏才有对应的检查点；没有检查点的栏位等于不存在。
    """
    label = f'{d} · {t}'
    for s in SECTION_ELEMS:
        if f'**{s}**' not in chunk:
            add(issues, '3-小节', name, f'{label[:46]} 缺「{s}」')
    if '**文号**' not in chunk:
        add(issues, '3-小节', name,
            f'{label[:46]} 发文机关行缺「**文号**」——无文号的写「（无文号：规划／法律／报告）」，'
            f'没查的写「（待补全）」，留空与没查分不开')
    if '**生效日期**' not in chunk:
        add(issues, '3-小节', name, f'{label[:46]} 缺「**生效日期**」')
    if '**影响判断**' in chunk:
        seg = chunk.split('**影响判断**', 1)[1].split('**国际对比**')[0]
        for f in IMPACT_FIELDS:
            if f not in seg:
                add(issues, '3-小节', name,
                    f'{label[:46]} 影响判断缺「{f}」——论述可附在后面作依据，三行骨架不能没有')


def check_sections(cards):
    """只查结构：模板要求的栏位缺失＝结构问题，阻断。

    观点覆盖率（完整／待补全／无观点三分类）是历史欠账，不阻断，
    已拆到 checks/views——两类问题语义不同，不该挤在同一个退出码里。
    """
    n_secs = 0
    for name, c in cards.items():
        n_secs += len(c['secs'])
        for d, t, chunk, _raw in c['secs']:
            _check_section(name, d, t, chunk)
    return n_secs


def _check_chain_file(chain, fm, body, theme_map):
    """一条链自身：主题匹配、双向链接、必备节、标题前空行。"""
    words = fm.get('主题匹配')
    if not isinstance(words, list):
        add(issues, '4-政策链', chain, f'「主题匹配」不是数组写法：{words}')
        words = []
    expect = set(theme_map.get(chain, []))
    if expect and set(words) != expect:
        miss, extra = expect - set(words), set(words) - expect
        if miss:
            add(issues, '4-政策链', chain, f'主题匹配缺：{sorted(miss)}')
        if extra:
            add(issues, '4-政策链', chain, f'主题匹配多（词表无此项）：{sorted(extra)}')

    relink = set(re.findall(r'\[\[政策卡片-([^|\]]+)', body))
    for w in words:
        if w not in relink:
            add(issues, '4-政策链', chain, f'「关联卡片」/正文缺 [[政策卡片-{w}]]')
    for r in relink:
        if r not in words:
            add(issues, '4-政策链', chain, f'链接了 [[政策卡片-{r}]]，但它不在本链主题匹配中')

    for sec in ('关联卡片', '时间轴', '变化轨迹', '政策信号新闻'):
        if f'## {sec}' not in body:
            add(issues, '4-政策链', chain, f'缺「## {sec}」节')

    # 标题前应有空行（Markdown 渲染要求）
    lines = body.split('\n')
    for i, l in enumerate(lines):
        if l.startswith('#') and i > 0 and lines[i - 1].strip() != '' and not lines[i - 1].startswith('#'):
            add(issues, '4-政策链', chain, f'「{l[:30]}」前缺空行')
            break


def _check_chain_backlink(cards, chain_files):
    """反向：卡片「所属政策链」必须存在，且该链的主题匹配里有本卡。"""
    for name, c in cards.items():
        raw = c['fm'].get('所属政策链', '')
        if isinstance(raw, list):          # 有卡写成数组形式，取第一项
            raw = raw[0] if raw else ''
        m = re.search(r'\[\[政策链-([^|\]]+)', raw)
        if not m:
            add(issues, '4-政策链', name, f'「所属政策链」未指向政策链：{raw!r}')
            continue
        chain = m.group(1)
        if chain not in chain_files:
            add(issues, '4-政策链', name, f'所属政策链 [[政策链-{chain}]] 不存在')
            continue
        words = chain_files[chain]['fm'].get('主题匹配')
        words = words if isinstance(words, list) else []
        if name not in words:
            add(issues, '4-政策链', name, f'所属 [[政策链-{chain}]] 的主题匹配里没有「{name}」')


def check_chains(cards, theme_map):
    chain_files = {}
    for p in sorted(CHAIN_DIR.glob('*.md')):
        chain = p.stem.replace('政策链-', '')
        text = p.read_text(encoding='utf-8')
        fm, body = parse_fm(text)
        if not fm:
            add(issues, '4-政策链', chain, '缺少 frontmatter')
            continue
        chain_files[chain] = {'fm': fm, 'body': body, 'path': p}
        _check_chain_file(chain, fm, body, theme_map)

    _check_chain_backlink(cards, chain_files)
    return chain_files


def check_theme_table(cards, theme_map, theme_words):
    if not theme_map:
        add(issues, '5-词表', 'index.md', '未能解析出受控词表映射（第二节表格格式可能已改）')
        return
    for chain, words in theme_map.items():
        for w in words:
            if w not in cards:
                add(issues, '5-词表', w, f'词表列在「{chain}」下，但没有对应产业卡文件')
    for name in cards:
        if theme_words and name not in theme_words:
            add(issues, '5-词表', name, '产业卡不在受控词表任何大类下')


PLACEHOLDER_LINKS = {'页面名', '关联政策卡片名', '链接', '政策名称', '文件名'}


def check_links(names):
    """全库 wikilink 断链（跳过代码块、行内代码、模板占位符、表格内转义竖线）"""
    for p in VAULT.rglob('*.md'):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        text = re.sub(r'`[^`]*`', '', text)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
        text = text.replace('\\|', '|')          # 表格内的转义竖线
        for link in re.findall(r'\[\[([^\]]+)\]\]', text):
            target = link.split('|')[0].split('#')[0].strip().rstrip('\\')
            if not target or '{' in target or target.endswith('XXX') or target in PLACEHOLDER_LINKS:
                continue
            if target not in names:
                rel = str(p.relative_to(VAULT))
                add(issues, '6-断链', rel, f'[[{target}]] 无对应文件')


def check_stats(n_secs):
    """index.md 里的**政策数**与实际是否一致（卡数不在这里查，见下）。

    政策数每天随采集变化，属快照，只提示不阻断——根治办法是别在索引里写死政策数。
    卡数曾在这里也查一遍，与 `docs` 的 `check_structure_numbers` 重复：同一件事
    两处实现、两句文案，结构一变还要改两处。2026-10-26 只留 docs 那一处——
    它扫的是**全部规则类文档**，比只扫 index 更全。
    """
    idx = INDEX
    if idx.exists():
        t = idx.read_text(encoding='utf-8')
        for m in re.finditer(r'覆盖\s*(\d+)\s*项政策', t):
            if int(m.group(1)) != n_secs:
                add(warns, '8-统计', 'index.md',
                    f'政策数写 {m.group(1)}，实际 {n_secs}（静态数字必漂移，建议改为「政策数见政策速览」）')


def fix_numbers(cards):
    """把产业卡 frontmatter 的三个数值改成实际值，返回 (处数, 明细行)。

    只改「数得出来」的三项：政策数 / 发布日期 / 时间跨度。
    其余字段（影响、领域、tags、状态）涉及判断，脚本不猜，继续报错交人工。
    """
    n, lines = 0, []
    for name, c in cards.items():
        path, fm = c['path'], c['fm']
        secs = c['secs']
        if not secs:
            continue
        dates = [d for d, _, _, _ in secs]
        text = path.read_text(encoding='utf-8')
        orig = text

        # 冒号必须兼容半角与全角：库里实际用半角 `政策数: 3`，
        # 只写全角会让替换静默失效（本函数曾因此一处没修过）
        if str(fm.get('政策数', '')).strip() != str(len(secs)):
            text = re.sub(r'(?m)^政策数[:：].*$', f'政策数: {len(secs)}', text, count=1)

        if fm.get('发布日期') and fm['发布日期'] != dates[0]:
            text = re.sub(r'(?m)^发布日期[:：].*$', f'发布日期: {dates[0]}', text, count=1)

        expect = f'{min(dates)} ~ {max(dates)}'
        span = str(fm.get('时间跨度', '')).strip().strip('"')
        if span and span.replace(' ', '') != expect.replace(' ', ''):
            text = re.sub(r'(?m)^时间跨度[:：].*$', f'时间跨度: {expect}', text, count=1)

        if text != orig:
            path.write_text(text, encoding='utf-8')
            n += 1
            lines.append(f'      修复 数值 {name}：政策数→{len(secs)}、发布日期→{dates[0]}')
    return n, lines


def fix_links(names):
    """只修「唯一高度相似」的断链，返回 (处数, 明细行)。

    能唯一确定就改；有两个以上候选就放着——猜错会把链接指到另一张卡，
    比断链更糟。这类会继续在 check 里报出来，等人工确认。
    """
    pool = list(names)
    n, skipped, lines = 0, [], []
    for p in sorted(VAULT.rglob('*.md')):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        # log.md 里的旧链接是史实（记录「当时指向哪里」），改了就是篡改历史，只报告不改
        if p.name == 'log.md':
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        orig = text
        for link in set(re.findall(r'\[\[([^\]]+)\]\]', text)):
            target = link.split('|')[0].split('#')[0].strip().rstrip('\\')
            if not target or '{' in target or target.endswith('XXX'):
                continue
            if target in PLACEHOLDER_LINKS or target in names:
                continue
            cand = difflib.get_close_matches(target, pool, n=2, cutoff=0.85)
            if len(cand) == 1:
                text = text.replace(f'[[{link}]]', f'[[{cand[0]}]]')
                n += 1
                lines.append(f'      修复 断链 {p.name}：[[{target}]] → [[{cand[0]}]]')
            else:
                skipped.append((p.name, target, len(cand)))
        if text != orig:
            p.write_text(text, encoding='utf-8')
    for f, t, k in skipped:
        lines.append(f'      跳过 断链 {f}：[[{t}]] 有 {k} 个候选，需人工确认')
    return n, lines


def run_fix():
    """自动修复数值与唯一候选断链。返回 (修复处数, 明细行)。

    **不负责刷快照**：修复会改变 index 的统计，快照必须在这之后刷；
    顺序编排属于 actions/fix 的职责（checks 层不许反向调 action）。
    """
    issues.clear()
    warns.clear()
    lines = ['=== 结构自动修复 ===']
    theme_map, _ = load_theme_words()
    theme_words = set(w for ws in theme_map.values() for w in ws)
    cards = check_cards(theme_words)

    n1, l1 = fix_numbers(cards)
    n2, l2 = fix_links(load_all_md_names())
    lines += l1 + l2
    lines.append(f'共修复 {n1 + n2} 处（数值 {n1} / 断链 {n2}）')
    return n1 + n2, lines


CATEGORY_LABELS = {
    '1-frontmatter': '产业卡 frontmatter（字段/枚举/tags）',
    '2-数值': '产业卡数值一致性（政策数/日期/跨度）',
    '3-小节': '政策小节结构（标题/倒序/五要素）',
    '4-政策链': '政策链双向一致',
    '5-词表': '受控词表一致（index 第二节）',
    '6-断链': 'wikilink 断链',
    '8-统计': '索引与总览的统计数字',
}


def _collect():
    """跑完全部结构判据，返回汇总所需的量。issues/warns 是模块级累积器。"""
    issues.clear()
    warns.clear()
    theme_map, _ = load_theme_words()
    theme_words = set(w for ws in theme_map.values() for w in ws)

    cards = check_cards(theme_words)
    check_numbers(cards)
    n_secs = check_sections(cards)
    check_chains(cards, theme_map)
    check_theme_table(cards, theme_map, theme_words)
    check_links(load_all_md_names())
    check_stats(n_secs)
    return cards, n_secs, theme_words


def _detail_lines(cards, n_secs, theme_words, quiet):
    """按类别列出问题与警告。输出顺序＝CATEGORY_LABELS 的顺序。"""
    lines = ['=== 政策知识库结构校验 ===',
             f'产业卡 {len(cards)} 张 | 政策链 {len(list(CHAIN_DIR.glob("*.md")))} 条 | '
             f'主题词 {len(theme_words)} 个 | 政策小节 {n_secs} 个', '']
    for cat, label in CATEGORY_LABELS.items():
        items = issues.get(cat, [])
        mark = 'OK  ' if not items else f'{len(items):>3} '
        lines.append(f'[{cat[0]}] {mark}{label}')
        if items and not quiet:
            for obj, msg in items[:25]:
                lines.append(f'      · {obj}：{msg}')
            if len(items) > 25:
                lines.append(f'      …… 另有 {len(items) - 25} 条')

    wt = sum(len(v) for v in warns.values())
    if wt:
        lines += ['', f'警告（不阻断）{wt} 条：']
        for cat, items in warns.items():
            for obj, msg in items[:15]:
                lines.append(f'      · [{cat}] {obj}：{msg}')
    lines.append('')
    return lines


def run(argv=None):
    ap = argparse.ArgumentParser(description='政策知识库结构校验器')
    ap.add_argument('--fix', action='store_true', help='自动修复数值与唯一候选断链')
    ap.add_argument('--quiet', action='store_true', help='只打印汇总，不列明细')
    args = ap.parse_args(list(argv or []))
    if args.fix:
        n, lines = run_fix()
        return Result(Verdict.PASS, f'结构修复 {n} 处', lines)

    if not CARD_DIR.exists() or not CHAIN_DIR.exists():
        return Result(Verdict.BAD_INPUT, '路径错误：未找到 wiki/政策卡片 或 wiki/政策链',
                      ['路径错误：未找到 wiki/政策卡片 或 wiki/政策链'])

    cards, n_secs, theme_words = _collect()
    lines = _detail_lines(cards, n_secs, theme_words, args.quiet)
    total = sum(len(v) for v in issues.values())
    wt = sum(len(v) for v in warns.values())

    if total == 0:
        lines.append('✅ 结构校验通过（观点覆盖率见 check_views.py，属欠账进度，不参与本判定）')
        return Result(Verdict.PASS,
                      f'{len(cards)} 卡／{n_secs} 小节：结构 0 问题'
                      + (f'，体积警告 {wt} 张' if wt else '，无体积警告'), lines)
    lines.append(f'❌ 发现 {total} 个结构问题（按上列顺序修复）')
    return Result(Verdict.FAIL, f'{len(cards)} 卡／{n_secs} 小节：结构问题 {total} 个（见上列明细）',
                  lines)
