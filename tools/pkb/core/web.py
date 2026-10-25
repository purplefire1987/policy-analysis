#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网页取回与正文抽取：抓、解码、切正文、找附件。

为什么在 core：这是**机制**，不是判定。哪些域名算一手、什么算清单类附件、
抓到之后放哪儿——全在 domain 与 actions，这里只回答「这一页的正文是什么」。

三个坑都踩过，写在实现里而不是别处：
1. **编码**：部委网站大量仍是 GBK/GB2312，按 UTF-8 解会整页乱码，
   而乱码不报错、看起来只是「没有正文」。所以先读 meta charset。
2. **正文容器**：政府站正文多在 `UCAP-CONTENT`/`TRS_Editor`/`zoom` 一类容器里，
   整页切会把导航条混进正文。容器命中就只切容器，切出来太短才退回全文。
3. **附件扩展名**：商务部附件是 `download?fileUrl=…&fileName=xxx.docx`，
   按路径取扩展名会得到 `download`，于是「附件转文本」永远跳过——静默失效。
"""
import html as htmllib
import re
import shutil
import subprocess
import time
from urllib.parse import unquote, urljoin

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.0 Safari/605.1.15')
CHARSET = re.compile(rb'charset=["\']?([\w-]+)', re.I)
TITLE = re.compile(r'(?is)<title[^>]*>(.*?)</title>')
NOISE = re.compile(r'^(字号|打印|分享|收藏|扫一扫|返回|首页|网站地图|关于我们|联系我们|'
                   r'版权|主办|承办|技术支持|ICP|京ICP|政府网|客户端|微信|微博|无障碍|'
                   r'责任编辑|编辑|来源|上一篇|下一篇|相关阅读|相关链接|热点推荐|相关稿件|'
                   r'当前位置|您的位置|打印本页|关闭窗口|字体|大\s*中\s*小|【我要纠错|'
                   r'扫一扫在手机|Produced By|主办单位|网站标识码|公安备案|'
                   r'[A-Za-z /|]*PC[A-Za-z /|]*$)')
MAIN = re.compile(r'id="(UCAP-CONTENT|zoom|content|Content|mainText|article|fontzoom|'
                  r'TRS_Editor|pages_content|conTxt|con_txt|wzcon|content_area)"|'
                  r'class="(TRS_Editor|article|article-content|content|main-content|'
                  r'pages_content|Custom_UnionStyle|content_area|view|text)"', re.I)
TAG = re.compile(r'<(\w+)')
OPEN_TAG = r'<{name}\b'
CLOSE_TAG = r'</{name}\s*>'
ATT = re.compile(r'(?is)<a[^>]+href="([^"]+\.(?:docx?|pdf|wps|xlsx?|zip|ofd))"[^>]*>(.*?)</a>')
EXT_IN_QUERY = re.compile(r'[?&]fileName=([^&]+)')


def fetch(url, timeout=25, insecure=False):
    """取一页。返回 (HTTP 码, 字节, 是否降级)；**字节为空即没取到**，码只用于说明原因。

    为什么保留非 200 的码：`404` 和「超时」是两种病。前者多半是卡片里的链接写错了
    （2026-10-26 实测：gov.cn 那几条 `content_7100000.htm` 不是失效，是从来没存在过），
    后者重试就好。都报成「失败」等于让人把数据错误当网络抖动。

    降级＝证书校验没过但内容取到了。政府站偶有过期证书，此时**照常取回并标注**，
    比悄悄失败好：读者能自己判断要不要用这份。`insecure` 供调用方显式放开。

    失败重试一次：批量补采时部委站会限流，首轮几十条一起打，后段会整片超时——
    看起来像「全站挂了」，实际隔一秒就通。重试放在这里，调用方不必各自记得。
    """
    code, body, degraded = _once(url, timeout, insecure)
    if body:
        return code, body, degraded
    time.sleep(1.5)
    return _once(url, timeout, insecure)


def _once(url, timeout, insecure):
    if not shutil.which('curl'):
        return _fetch_urllib(url, timeout)
    flags = ['-k'] if insecure else []
    r = subprocess.run(['curl', '-sL', '--max-time', str(timeout), '-A', UA] + flags +
                       [url, '-w', '%{http_code}'], capture_output=True)
    digits = re.search(rb'(\d{3})\s*$', r.stdout)      # -w 把状态码追加在体后面
    if not digits:
        return 0, b'', bool(flags)
    status = int(digits.group(1))
    payload = r.stdout[:digits.start()].rstrip(b'\n')
    if status != 200:
        payload = b''                                  # 404 的页面也返回两万字节错误页
    return status, payload, bool(flags)


def _fetch_urllib(url, timeout):
    """没有 curl 时的退路：够用，但不带证书降级。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), False
    except Exception:
        return 0, b'', False


def decode(body):
    """按 meta charset 解码，GB 系一律走 gb18030（gbk 的超集）。"""
    m = CHARSET.search(body[:4000])
    enc = m.group(1).decode('ascii', 'ignore').lower() if m else 'utf-8'
    if enc in ('gb2312', 'gbk', 'gb18030'):
        enc = 'gb18030'
    try:
        return body.decode(enc, 'ignore')
    except LookupError:
        return body.decode('utf-8', 'ignore')


def page_title(h):
    m = TITLE.search(h)
    return re.sub(r'\s+', ' ', htmllib.unescape(m.group(1))).strip() if m else ''


def _plain(block):
    block = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', block)
    block = re.sub(r'(?is)<!--.*?-->', ' ', block)
    block = re.sub(r'(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr|td|section|article)>', '\n', block)
    text = htmllib.unescape(re.sub(r'(?s)<[^>]+>', '', block))
    return text.replace('\u3000', ' ').replace('\xa0', ' ').replace('\u200b', '')


def _keep(t):
    """一行留不留：太短、站点导航、无标点的碎块都不要。"""
    if len(t) < 12 or NOISE.match(t):
        return False
    return not (len(t) < 30 and not re.search(r'[，。；：！？、（）《》“”]', t))


def container(h, pos):
    """`pos` 所在标签的 (起, 止)。配不成对就返回整篇——宁可多取，不可漏正文。

    为什么不用「切到 footer/share 关键词」：2026-10-26 实测，gov.cn 的正文容器里
    就带着 `class="share-title"`，按关键词切会在正文中间截断——那份《「高效办成
    一件事」第二批清单》抽出 487 字就断了，标题后面整段消失，而脚本报「完整」。
    漏正文比混进两行导航严重得多：混进导航看得见，漏掉的边界看不见。
    """
    start = h.rfind('<', 0, pos)
    m = TAG.match(h, start) if start >= 0 else None
    if not m or m.group(1).lower() in ('br', 'img', 'meta', 'link', 'input'):
        return 0, len(h)
    name = m.group(1)
    op = re.compile(OPEN_TAG.format(name=name), re.I)
    cl = re.compile(CLOSE_TAG.format(name=name), re.I)
    depth, i = 0, start
    while True:
        o, c = op.search(h, i), cl.search(h, i)
        if not c:
            return 0, len(h)
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
            if depth == 0:
                return start, i


def body_lines(h):
    """正文行（已去重）。容器配对成功且够长就只取容器，否则退回全文。"""
    m = MAIN.search(h)
    if m:
        start, end = container(h, m.start())
        lines = _lines_of(h[start:end])
        if len('\n'.join(lines)) >= 250:
            return lines
    return _lines_of(h)


def _lines_of(block):
    out, seen = [], set()
    for raw in _plain(block).split('\n'):
        t = re.sub(r'\s+', ' ', raw).strip()
        if not _keep(t) or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def suffix(url):
    """附件扩展名：`fileName=` 参数优先，其次路径。"""
    m = EXT_IN_QUERY.search(url)
    base = unquote(m.group(1)) if m else url.split('?')[0]
    return base.rsplit('.', 1)[-1].lower() if '.' in base.split('/')[-1] else ''


def attachments(h, base_url):
    """页内附件链接 [(显示名, 绝对 URL)]，按出现顺序去重。"""
    out, seen = [], set()
    for m in ATT.finditer(h):
        href = urljoin(base_url, m.group(1))
        if href in seen:
            continue
        seen.add(href)
        name = htmllib.unescape(re.sub(r'(?s)<[^>]+>', '', m.group(2))).strip()
        out.append((name or unquote(href.split('/')[-1].split('?')[0]), href))
    return out


def is_listing(url):
    """栏目页/首页：没有具体文件页，取回来也只是导航——别当成抓取成功。"""
    path = re.sub(r'^https?://[^/]+', '', url.split('?')[0].split('#')[0])
    return path in ('', '/') or path.endswith('/')
