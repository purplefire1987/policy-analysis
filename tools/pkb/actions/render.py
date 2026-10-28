#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render —— 出库：把库里的 Markdown 变成能交给别人的成品。

为什么要有（2026-10-28）：入库方向（HTML/docx/pdf → 文本）早就扎实，
出库方向一直是零——周观点、分析报告要给别人看，得另找工具重排一遍，
而重排出来的那一版和库里那一版从此分叉，谁是最新没人知道。

产两种，默认落 `归档/导出/`：
* `.html`  自带版式（A4、宋体、1.75 行距、表头灰底），单文件、无外链，
           打开就能读，浏览器「打印为 PDF」即得 PDF；
* `.docx`  调系统 `textutil` 转换，中文与加粗正常，**表格会退化成段落**
           （textutil 不保留 <table> 结构）——表格多的件建议用 HTML 打印。

为什么不做 PDF：本机 cupsfilter 不支持 html→pdf，手写 PDF 又要处理中文字体嵌入，
出错时的表现是「文件能打开、字是乱的」——那比没有 PDF 更坏。宁可明说没有。
"""
import argparse
import shutil
import subprocess
from pathlib import Path

from pkb.core import ANALYSIS_DIR, EXPORT_DIR, VAULT, WEEKLY_DIR, markdown, read


def _resolve(raw):
    """参数 → Path。先按库内相对路径找，找不到就当普通路径（允许导库外文件）。"""
    p = VAULT / raw
    return p if p.exists() else Path(raw)


def _targets(paths):
    """参数 → [源文件]。目录只取该目录下的 *.md，不递归：导出范围要人指定。"""
    out = []
    for raw in paths:
        p = _resolve(raw)
        if p.is_dir():
            out += sorted(p.glob('*.md'))
        elif p.is_file():
            out.append(p)
        else:
            print(f'  ! 找不到：{raw}')
    return out


def _docx(html_path, out_dir):
    """系统 textutil 转 docx。返回 (是否成功, 说明)。"""
    if shutil.which('textutil') is None:
        return False, '本机没有 textutil，跳过'
    out = out_dir / (html_path.stem + '.docx')
    try:
        r = subprocess.run(['textutil', '-convert', 'docx', '-output', str(out), str(html_path)],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f'调用 textutil 失败：{e}'
    if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        return False, f'textutil 失败：{(r.stderr or r.stdout).strip()[:80]}'
    return True, f'{out.name}（{max(1, out.stat().st_size // 1024)} KB）'


def _one(src, out_dir):
    """导一份：HTML 必出，docx 可选。返回要打印的行。"""
    html = out_dir / (src.stem + '.html')
    html.write_text(markdown.md_to_html(read(src, '')), encoding='utf-8')
    rows = [f'  {src.name} → {html.name}']
    ok, msg = _docx(html, out_dir)
    rows.append(f'    {"✓" if ok else "·"} docx：{msg}')
    return rows


def run(argv=None):
    ap = argparse.ArgumentParser(
        prog='render', description='导出为 HTML（与 docx）：交给别人的成品，落 归档/导出/')
    ap.add_argument('paths', nargs='*',
                    help='库内路径（文件或目录）；不写则导出全部周观点与分析报告')
    ap.add_argument('--out', default='', help=f'输出目录（默认 {EXPORT_DIR}）')
    args = ap.parse_args(list(argv or []))

    out_dir = Path(args.out) if args.out else EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.paths:
        targets = _targets(args.paths)
    else:
        targets = sorted(WEEKLY_DIR.glob('*.md')) + sorted(ANALYSIS_DIR.glob('*.md'))
    if not targets:
        print('没有找到要导出的文件——检查路径，或不带参数导出周观点与分析报告')
        return 2

    print('\n' + '=' * 62)
    print(f'出库：{len(targets)} 份 → {out_dir}')
    print('=' * 62)
    done = 0
    for src in targets:
        rows = _one(src, out_dir)
        print('\n'.join(rows))
        done += 1
    print(f'\n  共 {done} 份。HTML 自带版式，浏览器「打印为 PDF」即得 PDF；'
          f'表格多的件建议走 HTML（docx 会丢表格结构）')
    return 0
