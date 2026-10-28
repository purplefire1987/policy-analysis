#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown → HTML：出库方向的最小实现（2026-10-28 增）。

为什么自己写而不引 markdown 库：
本机 `pandoc`／`python-docx`／`markdown` 都没有，而 `fetch` 那条入库线已经证明
「不引第三方依赖」在本机是硬约束（pdfminer 是碰巧装的）。更要紧的是**只支持本库真的
会写的那几种结构**——多一项支持就多一处会判断错的地方。这里认识标题、段落、列表、
表格、引用块（含 callout）、代码块、粗体、行内码、`[[双链]]`，仅此。

它不是渲染器，是「把 Markdown 的结构翻成 HTML 的结构」：所以格式细节（字号、行距、
分页）全在 `PAGE_CSS` 里一处定义。改版式不用碰解析。
"""
import re

from .fm import parse_fm

# 版式只在这一次定义：A4、宋体、1.75 行距、表头灰底、``@media print`` 去掉边距。
# 为什么把样式写在 HTML 里而不外链：交出去的是一份文件，外链一断就没有版式了。
PAGE_CSS = """
@page { size: A4; margin: 22mm 18mm; }
body { font-family: "Songti SC", "SimSun", serif; font-size: 11pt; line-height: 1.75;
       color: #1a1a1a; max-width: 46em; margin: 0 auto; padding: 2em 1.2em; background: #fff; }
h1 { font-size: 20pt; text-align: center; margin: 0 0 1.4em; letter-spacing: 1px; }
h2 { font-size: 14pt; margin: 1.8em 0 .6em; padding-bottom: .25em; border-bottom: 1px solid #ddd; }
h3 { font-size: 12pt; margin: 1.2em 0 .5em; }
p { margin: .6em 0; text-indent: 2em; }
p.noindent, li p { text-indent: 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #bbb; padding: .4em .6em; text-align: left; vertical-align: top; }
th { background: #f2f2f2; }
blockquote { margin: .8em 0; padding: .1em 1em; border-left: 3px solid #ccc; background: #fafafa; }
.callout { border-left: 3px solid #4a7ab5; background: #f4f7fb; padding: .6em 1em; }
.callout .t { font-weight: 700; margin: 0 0 .3em; }
code { font-family: Menlo, monospace; font-size: .92em; background: #f4f4f4; padding: .1em .3em; }
pre { background: #f6f6f6; padding: .8em 1em; overflow-x: auto; }
pre code { background: none; padding: 0; }
ul, ol { margin: .5em 0 .5em 1.6em; }
li { margin: .25em 0; }
hr { border: 0; border-top: 1px solid #ddd; margin: 1.8em 0; }
.meta { color: #666; font-size: 9.5pt; text-align: center; margin-bottom: 2em; }
@media print { body { padding: 0; max-width: none; } a { color: inherit; text-decoration: none; } }
"""


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _inline(s):
    """行内：先转义，再粗体／行内码／双链／外链。顺序不能反，否则转义会把标签吃掉。"""
    s = _esc(s)
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', s)   # [[X|显示]] → 显示
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)              # [[X]] → X（导出件里没有库内跳转）
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    return s


def _is_table(line):
    return line.lstrip().startswith('|')


def _table(rows):
    """markdown 表格 → <table>。首行表头，第二行分隔线（全由 -:| 组成）丢弃。"""
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
    if len(cells) >= 2 and set(''.join(cells[1])) <= set('-: '):
        cells = [cells[0]] + cells[2:]
    if not cells:
        return ''
    head = ''.join(f'<th>{_inline(c)}</th>' for c in cells[0])
    body = ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in r) + '</tr>'
                   for r in cells[1:])
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _quote(lines):
    """引用块 → <blockquote>；`> [!info] 标题` 转成带标题的 callout。"""
    body, title = [], ''
    for ln in lines:
        t = ln.lstrip('>').strip()
        m = re.match(r'\[!\w+\]\s*(.*)', t)
        if m:
            title = m.group(1).strip()
            continue
        if t:
            body.append(f'<p class="noindent">{_inline(t.lstrip("- ").strip())}</p>')
    inner = f'<p class="t">{_inline(title)}</p>' if title else ''
    cls = 'callout' if title else ''
    return f'<blockquote class="{cls}">{inner}{"".join(body)}</blockquote>'


def _list(lines, ordered):
    tag = 'ol' if ordered else 'ul'
    items = [re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', ln) for ln in lines]
    return f'<{tag}>' + ''.join(f'<li>{_inline(x)}</li>' for x in items) + f'</{tag}>'


def _block(para):
    """一段连续文本 → 段落；`### 日期 · 标题` 这类小节也走这里（导出的不是 wiki 页）。"""
    text = ' '.join(para).strip()
    return f'<p>{_inline(text)}</p>' if text else ''


HEAD_RE = re.compile(r'^(#{1,4})\s+(.*)$')
UL_RE = re.compile(r'^[-*+]\s+')
OL_RE = re.compile(r'^\d+\.\s+')
HR_RE = re.compile(r'^(-{3,}|\*{3,})$')


def _group(lines, i, pred):
    """从 i 起取满足 pred 的连续行 → (组, 下一个 i)。"""
    j = i
    while j < len(lines) and pred(lines[j].strip()):
        j += 1
    return lines[i:j], j


def _code(lines, i):
    """``` 围栏代码块 → (html, 下一个 i)。"""
    j, body = i + 1, []
    while j < len(lines) and not lines[j].strip().startswith('```'):
        body.append(lines[j])
        j += 1
    return '<pre><code>' + _esc('\n'.join(body)) + '</code></pre>', j + 1


def _block_at(lines, i):
    """一个**非段落**块 → (html, 下一个 i)；不是特殊块时返回 (None, i)。"""
    s = lines[i].strip()
    if s.startswith('```'):
        return _code(lines, i)
    m = HEAD_RE.match(s)
    if m:
        lv = min(len(m.group(1)), 3)
        cls = ' class="noindent"' if lv == 1 else ''
        i += 1
        return f'<h{lv}{cls}>{_inline(m.group(2))}</h{lv}>', i
    if s.startswith('>'):
        grp, i = _group(lines, i, lambda x: x.startswith('>'))
        return _quote(grp), i
    if _is_table(s):
        grp, i = _group(lines, i, _is_table)
        return _table(grp), i
    if UL_RE.match(s) or OL_RE.match(s):
        grp, i = _group(lines, i, lambda x: UL_RE.match(x) or OL_RE.match(x))
        return _list(grp, bool(OL_RE.match(s))), i
    if HR_RE.match(s):
        return '<hr>', i + 1
    return None, i


def md_to_html(text, title=''):
    """整篇转换。frontmatter 不进正文，只在页首放一行来源。"""
    fm, body = parse_fm(text)
    name = title or str(fm.get('标题') or fm.get('名称') or '').strip()
    out, buf, lines, i = [], [], body.split('\n'), 0
    while i < len(lines):
        if not lines[i].strip():
            if buf:
                out.append(_block(buf))
                buf = []
            i += 1
            continue
        html, nxt = _block_at(lines, i)
        if html is not None:
            if buf:
                out.append(_block(buf))
                buf = []
            out.append(html)
            i = nxt
        else:
            buf.append(lines[i].strip())
            i += 1
    if buf:
        out.append(_block(buf))
    head = f'<div class="meta">{_inline(name)}</div>' if name else ''
    return ('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<title>{_esc(name)}</title><style>{PAGE_CSS}</style></head><body>'
            f'{head}\n' + '\n'.join(x for x in out if x) + '</body></html>\n')
