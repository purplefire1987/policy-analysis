#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""附件转文本：docx / doc / pdf → 可直接贴进存档的纯文本。

为什么不留附件原文件、只留链接：附件给**边界**（编码、清单、阈值、名单），
正文给规模。只存链接的档案，过两年链接一断，边界就没了；而边界正是这类
政策最需要回头核的东西。所以附件必须落成**可 grep 的文本**。

不引第三方依赖：docx 就是 zip + XML（标准库够用），doc 用 macOS 自带 textutil，
PDF 用已装的 pdfminer。装不上的环境返回空串并在存档里注明——不静默丢。
"""
import re
import subprocess
import zipfile
from pathlib import Path

# 坑：`<w:t[^>]*>` 会匹配到 `<w:textAlignment`，把整段原始 XML 吞进正文，
# 看起来「有内容」，其实是元数据。必须要求标签名后紧跟空白或 `>`。
W_T = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>')
W_BLOCK = re.compile(r'(?s)<w:(p|tr|tbl)\b[^>]*>(.*?)</w:\1>')
W_CELL = re.compile(r'(?s)<w:tc\b[^>]*>(.*?)</w:tc>')
SENT_END = re.compile(r'[。；：！？》）】]$')
STRUCT = re.compile(r'^(第[一二三四五六七八九十百]+[章节条]|[一二三四五六七八九十]+、|'
                    r'（[一二三四五六七八九十]+）|\d+[.、])')


def docx_text(path):
    """docx → 文本。表格按 `| 单元格 | 单元格 |` 保留，别摊成一串。"""
    try:
        xml = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8', 'ignore')
    except Exception:
        return ''
    out = []
    for m in W_BLOCK.finditer(xml):
        cells = W_CELL.findall(m.group(2))
        if cells:
            vals = [' '.join(W_T.findall(c)).strip() for c in cells]
            out.append('| ' + ' | '.join(vals) + ' |')
            continue
        txt = ''.join(W_T.findall(m.group(2))).strip()
        if txt:
            out.append(txt)
    return '\n\n'.join(out)


def doc_text(path):
    """doc → 文本：只走 macOS 的 textutil（无第三方依赖）。"""
    try:
        r = subprocess.run(['textutil', '-convert', 'txt', '-stdout', str(path)],
                           capture_output=True, timeout=60)
        return r.stdout.decode('utf-8', 'ignore').strip()
    except Exception:
        return ''


def pdf_text(path):
    """PDF → 文本，并把断行接回去（PDF 每行都硬断，逐行贴会没法读）。"""
    try:
        from pdfminer.high_level import extract_text
        raw = extract_text(str(path))
    except Exception:
        return ''
    merged = []
    for line in (x.strip() for x in raw.split('\n')):
        if not line:
            continue
        prev = merged[-1] if merged else ''
        if prev and not SENT_END.search(prev) and len(prev) < 45 and not STRUCT.match(line):
            merged[-1] = prev + line
        else:
            merged.append(line)
    return '\n\n'.join(merged)


def to_text(path):
    """按扩展名分派。不支持的扩展名返回空串（调用方据此写「未转文本」）。"""
    ext = Path(path).suffix.lower().lstrip('.')
    fn = {'docx': docx_text, 'doc': doc_text, 'pdf': pdf_text}.get(ext)
    if fn is None:
        return ''
    try:
        return fn(path)
    except Exception:
        return ''


def unsupported(ext):
    """明确没有转换器的格式——写进存档时要说清「不是抽坏了，是抽不了」。"""
    return ext in ('wps', 'et', 'ofd', 'zip', 'xlsx')
