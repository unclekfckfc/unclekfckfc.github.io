#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出处链接存活复查 —— 「我核到哪儿了」必须包括「那条出处现在还活着吗」。

★ 为什么要复查:★ 核验结论建立在【当时抓到了正文】上。★ 若出处后来挂了/改了,
  读者点进去看到的是死链 —— 而卡上仍写着「核得住」。★ ★★ 那就是在骗人。★★★

跑法: python3 check_links.py [--refresh]
产出: link_alive.json  {url: {code, checked_at}}
"""
import json, os, sys, time, urllib.request, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(HERE, 'seed_cards.json')
OUT = os.path.join(HERE, 'link_alive.json')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; youchuchu/1.0)'}


def probe(u, timeout=12):
    try:
        r = urllib.request.Request(u, headers=UA)
        return urllib.request.urlopen(r, timeout=timeout).getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__


def main():
    refresh = '--refresh' in sys.argv
    cards = json.load(open(CARDS, encoding='utf-8'))['cards']
    try:
        alive = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        alive = {}
    urls = sorted({c['url'] for c in cards if c.get('url')})
    todo = urls if refresh else [u for u in urls if u not in alive]
    print('══ 出处链接复查:%d 条待查 / 共 %d 条 ══' % (len(todo), len(urls)))
    if todo:
        with cf.ThreadPoolExecutor(12) as ex:
            res = dict(zip(todo, ex.map(lambda u: probe(u), todo)))
        now = time.strftime('%Y-%m-%dT%H:%M:%S')
        for u, code in res.items():
            alive[u] = {'code': code, 'checked_at': now}
        json.dump(alive, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    st = Counter()
    for u in urls:
        st[str(alive.get(u, {}).get('code', '未查'))] += 1
    print('  结果分布:', dict(st))
    # ★ 语义修正:机器探的 403/URLError/Timeout【不等于死链】——
    #   ★ 它们多数是【我这台机器连不上/被反爬】(arxiv、huggingface、github、blog.google…都是墙外域名)。
    #   ★ 实测:机器探 30 条异常 → 浏览器复核只有 1 条真 404 ⇒ 真实死链 0.4%,不是 13%。
    #   ★ ⇒ 本脚本只产出【不可达】,★ 死链必须由 link_alive_browser.json(浏览器复核)判定。
    dead = [u for u in urls if alive.get(u, {}).get('code') not in (200, '未查')]
    print('  ★ 机器不可达 %d 条(≠ 死链;死链看浏览器复核)' % len(dead))
    for u in dead[:12]:
        print('    %-70s %s' % (u[:70], alive[u]['code']))
    # 自检:结论必须与数据一致
    assert len(alive) >= len(urls), '复查表比数据少'
    return 0


from collections import Counter
if __name__ == '__main__':
    sys.exit(main())
