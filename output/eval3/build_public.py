#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只把「今天那一张卡 + 精选页」拷进 site_public/ —— 公开面的暴露面 = 1 条 + 1 个出处链接。
全部底稿仍留在本地/私有仓库。跑法: python3 build_public.py
"""
import os, re, shutil, sys

SITE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site'))
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site_public'))


def main():
    today = os.path.join(SITE, 'today.html')
    if not os.path.exists(today):
        print('★ 没有 today.html,先跑 build_today.py'); return 1
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'signals'), exist_ok=True)
    h = open(today, encoding='utf-8').read()
    card = re.search(r'href="signals/(id-\d+)\.html"', h).group(1)
    shutil.copy(today, os.path.join(OUT, 'today.html'))
    shutil.copy('%s/signals/%s.html' % (SITE, card), '%s/signals/%s.html' % (OUT, card))
    ch = open('%s/signals/%s.html' % (OUT, card), encoding='utf-8').read()
    for u in set(re.findall(r'assets/og/[^"\']+', ch)):
        src = os.path.join(SITE, u)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(os.path.join(OUT, u)), exist_ok=True)
            shutil.copy(src, os.path.join(OUT, u))
    n = sum(len(f) for _, _, f in os.walk(OUT))
    assert n >= 2, '公开面为空'
    print('✓ site_public/ · 公开面 = %s + today.html · 共 %d 个文件' % (card, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
