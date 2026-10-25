#!/usr/bin/env python3
"""来源违规清理：删除黑名单链接，主体本身违规的整行删，删后不足 3 类主体的节降 B 档。

用法：
  python3 clean_sources.py --dry-run    # 只报告
  python3 clean_sources.py --apply      # 执行

处置分四类：
  R1 表格行·主体本身违规（今日头条/网易号/搜狐号/百家号/公众号/界面新闻/中华网）→ 整行删
  R2 表格行·主体合规但链接是转载/自媒体页 → 保留观点，链接改为「原始出处待核」
  R3 信号「来源」字段 → 删违规 URL，改为「原始出处未能核实」
  R4 正文「政策原文」等行内链接 → 去掉链接，标「官方链接待补」
清理后逐节复核「各方观点」表：数据行 <3 或主体类别 <3 → 整表与辨析一并降为「（待补全）」
"""
import argparse
import re
import collections

from pkb.core import WORKSPACE, VAULT  # 路径唯一定义处：pkb/core/paths.py
from pkb.domain import BLACK, BAD_SUBJECT, is_bad  # 黑名单唯一定义处：pkb/domain/blacklist.py
LINK = re.compile(r'\[([^\]]*)\]\((https?://[^)\s]+)\)')


def subject_cell(line):
    """表格行第 1 列文本。"""
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    return cells[0] if cells else ''


def fix_line(line, dry, log, rel):
    """处理单行，返回 (新行, 动作) 。动作: keep / delete / rewrite"""
    urls = LINK.findall(line)
    if not urls or not any(is_bad(u) for _, u in urls):
        return line, 'keep'

    stripped = line.strip()
    is_row = stripped.startswith('|') and not re.match(r'^\|[\s:\-|]+\|?$', stripped)

    if is_row:
        subj = subject_cell(line)
        if any(k in subj for k in BAD_SUBJECT):
            log.append((rel, 'R1 整行删', subj[:32]))
            return None, 'delete'
        new = LINK.sub(lambda m: m.group(1) + '（原始出处待核）' if is_bad(m.group(2))
                       else m.group(0), line)
        log.append((rel, 'R2 链接改待核', subj[:32]))
        return new, 'rewrite'

    if '**来源**' in line:
        anchors = [a for a, u in urls]
        all_bad = all(is_bad(u) for _, u in urls)
        if all_bad and any(k in ''.join(anchors) for k in BAD_SUBJECT):
            # 标注主体本身就是黑名单/排除名单：整行只说「未能核实」，不留主体名
            log.append((rel, 'R3 主体违规→整行未能核实', stripped[:40]))
            return re.sub(r'^(- \*\*来源\*\*：).*$', r'\1（原始出处未能核实）', line), 'rewrite'
        new = LINK.sub(lambda m: m.group(1) + '（原始出处未能核实）' if is_bad(m.group(2))
                       else m.group(0), line)
        log.append((rel, 'R3 来源改未能核实', stripped[:40]))
        return new, 'rewrite'

    # R4 行内链接
    new = LINK.sub(lambda m: (m.group(1) + '（官方链接待补）' if '政策原文' in m.group(1)
                              else m.group(1) + '（原始出处待核）')
                   if is_bad(m.group(2)) else m.group(0), line)
    log.append((rel, 'R4 行内链接改写', stripped[:40]))
    return new, 'rewrite'


def table_block(lines, start):
    """从 start 起找表格块，返回 (表头行号, 结束行号exclusive, 数据行列表)"""
    i = start
    rows = []
    while i < len(lines) and lines[i].strip().startswith('|'):
        rows.append((i, lines[i]))
        i += 1
    data = [(n, l) for n, l in rows if not re.match(r'^\|[\s:\-|]+\|?$', l.strip())]
    # 第一行数据是表头
    return start, i, data[1:] if data else []


def collect_view(text):
    """返回 {节标题: (数据行数, 主体类别数)}，只统计「各方观点」表。"""
    lines = text.split('\n')
    res = {}
    sect = ''
    for i, line in enumerate(lines):
        if line.startswith('### '):
            sect = line.strip()
        if line.strip() == '**各方观点**':
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith('|'):
                _, e, data = table_block(lines, j)
                cats = set()
                for _, l in data:
                    cells = [c.strip() for c in l.strip().strip('|').split('|')]
                    if len(cells) > 1:
                        cats.add(cells[1])
                res[sect] = (len(data), len(cats))
    return res


def downgrade_sections(text, before, rel, log):
    """只处理「删前合格、删后不合格」的节——原本就欠账的不在此列（属历史欠账）。"""
    lines = text.split('\n')
    after = collect_view(text)
    targets = [k for k, v in after.items()
               if (v[0] < 3 or v[1] < 3) and before.get(k, (0, 0))[0] >= 3
               and before.get(k, (0, 0))[1] >= 3]
    if not targets:
        return text
    out = list(lines)
    for tgt in targets:
        i = 0
        while i < len(out):
            if out[i].startswith('### ') and out[i].strip() == tgt:
                # 找「**各方观点**」后的表格
                k = i
                while k < len(out) and out[k].strip() != '**各方观点**':
                    k += 1
                if k >= len(out):
                    break
                j = k + 1
                while j < len(out) and not out[j].strip():
                    j += 1
                if j < len(out) and out[j].strip().startswith('|'):
                    s, e, data = table_block(out, j)
                    out[s:e] = ['', '（待补全）']
                    b = e
                    while b < len(out) and out[b].strip() != '**观点辨析**':
                        b += 1
                    if b < len(out):
                        m = b + 1
                        while m < len(out) and not out[m].strip():
                            m += 1
                        end = m
                        while end < len(out) and not out[end].startswith(('**', '###', '## ')):
                            end += 1
                        out[m:end] = ['', '（待补全）', '']
                    log.append((rel, 'D 删后不足3类→降B档', tgt[:44]))
                break
            i += 1
    return '\n'.join(out)


def run(argv=None):
    ap = argparse.ArgumentParser(description='来源违规清理')
    ap.add_argument('--apply', action='store_true', help='实际写盘（默认只演练）')
    ap.add_argument('--dry-run', action='store_true', help='只报告不写盘（默认行为，保留以兼容旧调用）')
    args = ap.parse_args(list(argv or []))
    dry = not args.apply
    log = []
    files = sorted(p for p in (VAULT / 'wiki').rglob('*.md'))
    touched = 0
    for p in files:
        rel = str(p.relative_to(VAULT))
        text = p.read_text(encoding='utf-8')
        if not any(k in text for k in BLACK):
            continue
        new_lines = []
        acts = []
        for line in text.split('\n'):
            nl, act = fix_line(line, dry, acts, rel)
            if nl is not None:
                new_lines.append(nl)
        if acts:
            touched += 1
        new_text = '\n'.join(new_lines)
        before = collect_view(text)
        new_text = downgrade_sections(new_text, before, rel, acts)
        log.extend(acts)
        if not dry and acts:
            p.write_text(new_text, encoding='utf-8')

    c = collections.Counter(a[1].split(' ')[0] for a in log)
    print(('【DRY-RUN】' if dry else '【已执行】') + f' 涉及文件 {touched} 个，动作 {len(log)} 项')
    for k, v in sorted(c.items()):
        print(f'  {k:6s} {v:3d}')
    print('\n--- 明细（前 40）---')
    for a in log[:40]:
        print(f'  {a[1]:22s} {a[0]:34s} {a[2]}')
    if len(log) > 40:
        print(f'  ……另有 {len(log)-40} 项')
    # 落盘报告（工作区路径同样只在 lib.py 定义一次）
    rep = WORKSPACE / '来源清理报告.md'
    rep.write_text('# 来源违规清理报告\n\n'
                   f'{"" if dry else "已执行"}　动作 {len(log)} 项，文件 {touched} 个\n\n'
                   + '\n'.join(f'- {a[1]}｜{a[0]}｜{a[2]}' for a in log) + '\n',
                   encoding='utf-8')
    print(f'\n报告：{rep}')

