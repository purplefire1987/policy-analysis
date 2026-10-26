#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一手源域名分级：哪些链接算原文、哪些算官方报道、哪些不值得入档。

为什么住在 domain 而不在抓取脚本里：这是**口径**——「什么算一手」。
放脚本里就等于把规则藏进实现，改一次要去改代码，且 `check_docs` 的口径单源扫描
扫不到它（扫描词典是从 `pkb.domain.__all__` 现读的）。名单加在这里，抓取、
体检、`check_docs` 三处同时生效，不用各改一遍。

三级与处置：
  原文     —— 发文机关自己的站点（部委、地方政府、议会/政府公报）。入档，标「原文」。
  官方报道 —— 通讯社与党报央媒发布的报道。入档，标「官方报道」，因为**它不是文件本身**，
              读者据此知道「这条还得回原文核」。
  非一手   —— 门户转载、行业站、自媒体。**不入档**：存下来的是一段转述，
              两年后拿它当证据，等于把二手当一手用。

灰名单（新浪、澎湃、证券时报等）故意归入「非一手」而不是单列一级：
它们在**观点**里可用（须标「门户转载」），但在**一手存档**里不可用。
两件事的判据不同，别为了少一个枚举把口径弄含糊。
"""
import re

from .blacklist import is_bad

# 发文机关自己的站点。`.gov` 含外国政府站点（FOMC、联邦公报一类），
# `.gov.cn`/`.gov.hk`/`.gov.mo` 是中国各级政府——香港、澳门、台湾都是中国的一部分，
# 其政府网站与内地部委同级，不是「外国来源」。
ORIGIN_SITES = (
    '.gov.cn', '.gov.hk', '.gov.mo', '.gov',
    'cas.cn',            # 中国科学院
    'ac.cn',             # 科研院所（政策原文少见，但发布口径一致）
    'cdpf.org.cn',       # 中国残联：群团组织，发文用 .org.cn，与部委同级
)

# 通讯社与央媒：报道可用，但不是文件本身。
OFFICIAL_MEDIA = (
    'news.cn', 'xinhuanet.com',            # 新华社
    'people.com.cn',                        # 人民日报
    'cctv.com', 'cctv.cn',                  # 央视
    'cnr.cn',                               # 央广
    'ce.cn',                                # 经济日报
    'gmw.cn',                               # 光明日报
    'legaldaily.com.cn',                    # 法治日报
    'chinadaily.com.cn',                    # 中国日报
)

LEVELS = ('原文', '官方报道', '非一手')


def host(url):
    """URL → 主机名（小写、去端口）。"""
    m = re.match(r'\s*https?://([^/?#:]+)', url or '', re.I)
    return m.group(1).lower() if m else ''


def _hit(h, sites):
    return any(h == s.lstrip('.') or h.endswith(s) for s in sites)


def level(url):
    """'原文' / '官方报道' / '非一手'。空链接按非一手算（没链接就没有一手）。"""
    h = host(url)
    if not h or is_bad(url):
        return '非一手'
    if _hit(h, ORIGIN_SITES):
        return '原文'
    if _hit(h, OFFICIAL_MEDIA):
        return '官方报道'
    return '非一手'


def why(url):
    """一句话说明分级理由——存档头和抓取报告都用它，免得两处措辞不一致。"""
    lv, h = level(url), host(url)
    if lv == '原文':
        return f'{h} 为发文机关站点'
    if lv == '官方报道':
        return f'{h} 为通讯社/央媒报道，非文件本身'
    if not h:
        return '无链接'
    if is_bad(url):
        return f'{h} 在黑名单内'
    return f'{h} 非发文机关站点，属门户转载或行业站'
