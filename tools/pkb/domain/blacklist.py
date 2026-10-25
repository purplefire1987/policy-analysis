#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""来源黑名单：全库唯一清单。

为什么单列一个模块而不进 core：这是**口径**（什么来源算违规），不是机制。
core 的原则是「口径不进共用层」，所以黑名单住在 domain，
由 check_docs.py（查）与 clean_sources.py（清）共同 import——
两处各写一份清单的历史教训：2026-10-24 清理时发现两份名单已经漂移
（check_docs 有 14 项、clean_sources 只有 10 项，漏了界面新闻/雪球/股吧）。

改这里 = 改全库口径；AGENTS.md 黑名单节的「域名自查清单」表是它的文档副本，
由 check_docs.py 的 check_blacklist 负责核对文档侧是否还在用旧口径。
"""

# 域名/路径片段 → 违规原因。命中方式：子串包含（`k in url`）。
BLACK = {
    'toutiao.com': '今日头条聚合页',
    'm.toutiao.com': '今日头条聚合页',
    'mp.weixin.qq.com': '微信公众号',
    '163.com/dy': '网易号自媒体',
    'k.sina.com.cn': '新浪看点号（非新浪财经）',
    'sohu.com/a/': '搜狐号自媒体',
    'baijiahao': '百家号',
    'so.html5.qq.com': '搜索中间页',
    'fxbaogao.com': '二手研报平台',
    'gzylhyzx.com': '域名与主体不符',
    'somo.com.my': '境外转载站',
    'jiemian.com': '界面新闻（用户明确排除）',
    'xueqiu.com': '雪球',
    'guba': '股吧',
}

# 标注主体本身即违规/排除的关键词（用于 clean_sources 判定「整行删」）。
BAD_SUBJECT = ['今日头条', '头条', '网易号', '搜狐号', '百家号', '微信', '公众号',
               '界面新闻', '中华网', '雪球', '股吧', '匿名', '从业者评论', '网友']


def is_bad(url):
    """这条链接是否落在黑名单里。"""
    return any(k in url for k in BLACK)
