#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""附件转文本：一切格式 → 可直接贴进存档的纯文本（TXT／Markdown）。

**入库的终点只有一种格式：TXT**（2026-10-28 定）。本库是知识库，不做 HTML／docx
出库，所以这个模块只负责「进来」，不负责「出去」；能 grep 的文本才进得了库。

为什么不留附件原文件、只留链接：附件给**边界**（编码、清单、阈值、名单），
正文给规模。只存链接的档案，过两年链接一断，边界就没了；而边界正是这类
政策最需要回头核的东西。所以附件必须落成**可 grep 的文本**。

不引第三方依赖：docx 就是 zip + XML（标准库够用），doc 用 macOS 自带 textutil，
PDF 用已装的 pdfminer。装不上的环境返回空并在存档里写明**原因**。

返回值是 `(文本, 没转成的原因)`，不是裸字符串（2026-10-28 改）：空字符串至少有
四种成因——扫描件要 OCR、缺库要装库、文件坏了要重下、格式不支持要人工看。
压成一句「未能转为文本」，四种处置就被合并成同一个动作：不管。
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

# 本身已是文本的格式：入库终点就是 TXT，这些不需要「转换」，直接读。
PLAIN = ('txt', 'md', 'markdown', 'csv', 'tsv', 'json', 'xml')


def plain_text(path):
    """纯文本直接读：utf-8 → gb18030 → utf-16 依次试。

    为什么单列一条：此前转换表里没有 txt，于是 `.txt` 附件被写成「未能转为文本」——
    **最不该失手的一种恰恰失手了**，而且看起来像是文件有问题。
    部委的清单附件常是 GBK 编码的 txt，所以不能只试 utf-8。
    """
    data = Path(path).read_bytes()
    for enc in ('utf-8', 'gb18030', 'utf-16'):
        try:
            return data.decode(enc), ''
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode('utf-8', 'ignore'), '编码认不出，已按 utf-8 强制解（可能有乱码）'


def docx_text(path):
    """docx → 文本。表格按 `| 单元格 | 单元格 |` 保留，别摊成一串。"""
    try:
        xml = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8', 'ignore')
    except Exception:
        return '', 'docx 打不开（可能是加密文档或下载不全）'
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
    return '\n\n'.join(out), '' if out else 'docx 里没有文字（可能是整页图片）'


def doc_text(path):
    """doc → 文本：只走 macOS 的 textutil（无第三方依赖）。"""
    try:
        r = subprocess.run(['textutil', '-convert', 'txt', '-stdout', str(path)],
                           capture_output=True, timeout=60)
    except FileNotFoundError:
        return '', 'textutil 不可用（非 macOS 环境），.doc 需另找转换器'
    except Exception:
        return '', 'textutil 调用失败'
    text = r.stdout.decode('utf-8', 'ignore').strip()
    if text:
        return text, ''
    return '', 'doc 转出来是空的（可能是加密文档或整页图片）'


def pdf_text(path):
    """PDF → 文本，并把断行接回去（PDF 每行都硬断，逐行贴会没法读）。"""
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return '', '缺 pdfminer（pip install pdfminer.six），PDF 未抽取'
    try:
        raw = extract_text(str(path))
    except Exception:
        return '', 'PDF 打不开（加密或文件损坏）'
    merged = []
    for line in (x.strip() for x in raw.split('\n')):
        if not line:
            continue
        prev = merged[-1] if merged else ''
        if prev and not SENT_END.search(prev) and len(prev) < 45 and not STRUCT.match(line):
            merged[-1] = prev + line
        else:
            merged.append(line)
    if not merged:
        return '', 'PDF 没有文字层——多半是扫描件，需 OCR（人来做，工具不猜）'
    return '\n\n'.join(merged), ''


def xlsx_text(path):
    """xlsx → 文本。清单类附件（阈值、编码、名单）多半是表格，摊成散文就没法核。

    不引 openpyxl：xlsx 就是 zip + 两三个 XML，标准库够用。
    只读**值**，不读样式；公式取缓存值（`<v>`），因为读者要的是公布出来的数，
    不是 `=SUM(A1:A9)`。
    """
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return '', 'xlsx 打不开（可能下载不全）'
    names = z.namelist()
    shared = []
    if 'xl/sharedStrings.xml' in names:
        raw = z.read('xl/sharedStrings.xml').decode('utf-8', 'ignore')
        for si in re.findall(r'(?s)<si\b[^>]*>(.*?)</si>', raw):
            # 富文本会拆成多个 <t>，只取第一个就会丢半句
            shared.append(''.join(re.findall(r'<t(?:\s[^>]*)?>(.*?)</t>', si)))
    sheets = sorted(n for n in names if n.startswith('xl/worksheets/') and n.endswith('.xml'))
    books = []
    for nm in sheets:
        xml = z.read(nm).decode('utf-8', 'ignore')
        rows = []
        for row in re.findall(r'(?s)<row\b[^>]*>(.*?)</row>', xml):
            cells = []
            for attrs, body in re.findall(r'(?s)<c\b([^>]*)>(.*?)</c>', row):
                style = re.search(r't="([^"]+)"', attrs)
                kind = style.group(1) if style else ''
                if kind == 'inlineStr':
                    val = ''.join(re.findall(r'<t(?:\s[^>]*)?>(.*?)</t>', body))
                else:
                    v = re.search(r'(?s)<v\b[^>]*>(.*?)</v>', body)
                    val = v.group(1) if v else ''
                    if kind == 's' and val.isdigit():
                        val = shared[int(val)] if int(val) < len(shared) else ''
                cells.append(_unescape(val).strip())
            if any(cells):
                rows.append('| ' + ' | '.join(cells) + ' |')
        if rows:
            books.append(f'（{Path(nm).stem}）\n' + '\n'.join(rows))
    return '\n\n'.join(books), '' if books else 'xlsx 里没有值（可能只有空表或全为图片）'


def html_text(path):
    """另存为网页的附件 → 文本。部委附件偶有 `.html`，直接读会带一屏标签。"""
    data = Path(path).read_bytes()
    for enc in ('utf-8', 'gb18030', 'utf-16'):
        try:
            h = data.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        h = data.decode('utf-8', 'ignore')
    h = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', h)
    h = re.sub(r'(?is)<t[dh]\b[^>]*>', ' | ', h)
    h = re.sub(r'(?is)</tr\s*>', ' |\n', h)
    h = re.sub(r'(?is)<br\s*/?>|</(p|div|h[1-6]|li|tr)\s*>', '\n', h)
    txt = _unescape(re.sub(r'(?s)<[^>]+>', '', h))
    lines = [re.sub(r'[ \t]{2,}', ' ', x).strip() for x in txt.splitlines()]
    txt = '\n'.join(x for x in lines if x)
    return txt, '' if txt.strip() else 'html 里没有文字'


def _unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
             .replace('&apos;', "'").replace('&#39;', "'").replace('&nbsp;', ' ')
             .replace('&amp;', '&'))


def to_text(path):
    """按扩展名分派 → (文本, 没转成的原因)。原因空串即成功。

    调用方（`fetch`）把原因原样写进存档：读者据此决定是去 OCR、去装库、
    还是去重下——三种处置完全不同，这正是不能只回空串的理由。
    """
    ext = Path(path).suffix.lower().lstrip('.')
    if not ext:
        return '', '扩展名未知，无法判断格式'
    if ext in PLAIN:
        return plain_text(path)
    fn = {'docx': docx_text, 'doc': doc_text, 'pdf': pdf_text,
          'xlsx': xlsx_text, 'html': html_text, 'htm': html_text}.get(ext)
    if fn is None:
        return '', f'.{ext} 不在可转之列（本库只收能转成文本的格式）'
    try:
        return fn(path)
    except Exception as e:
        return '', f'转换时出错：{type(e).__name__}'


def unsupported(ext):
    """明确没有转换器的格式——写进存档时要说清「不是抽坏了，是抽不了」。

    `.xls` 是 BIFF 二进制，标准库解不了，别再让它伪装成「转换失败」：
    另存为 xlsx／csv 之后同一套代码就能抽。
    """
    return ext in ('wps', 'et', 'ofd', 'zip', 'xls')
