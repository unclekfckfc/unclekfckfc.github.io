#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ RSS —— 这条产品形态天然该有、而我从来没做过的分发腿。

★ 为什么关键:★ 分发的其它所有腿都要求"读者能打开我的页面"。
★   而 RSS 反过来:★★ 订阅者【自己拉】内容 ⇒ ★★ 只要 feed 在一个公开可达的地址上,
★★   订阅就成立 ⇒ ★★ 【门开不开,不影响订阅】。★★★★
★ ★★ 而且 feed 顺手解决:往期索引(订阅器自带历史)· 期号(guid)· AI 抓取 · 可索引。★★★★

跑法: python3 build_feed.py [--periods N]
产出: site/feed.xml + site/archive/001.html … (每期一页,永久保留)
"""
import json, os, sys, html, re, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.abspath(os.path.join(HERE, '..', 'site'))
def _base():
    try:
        _c = json.load(open(os.path.join(HERE, 'site_config.json'), encoding='utf-8'))
        _b = (_c.get('base') or '').strip()
        if _b: return _b.rstrip('/')
    except Exception:
        pass
    return (os.environ.get('SITE_BASE') or '').rstrip('/')


BASE = _base()
N = 10
if '--periods' in sys.argv:
    N = int(sys.argv[sys.argv.index('--periods') + 1])

VC = {'ok': '核得住', 'warn': '有出入，要盯', 'x': '查不了', 'u': '没核过'}
SYM = {'ok': '✓', 'warn': '△', 'x': '?', 'u': '·'}


def esc(s):
    return html.escape(str(s or ''), quote=True)


def pub_pool(cards):
    ps = [c for c in cards if c.get('qual') and c.get('url')]
    ps.sort(key=lambda c: int(c.get('id') or 0))
    return ps


def page(c, issue, base):
    """一期一页 —— 永久保留,链接永不变
    ★ 用 {{KEY}} 占位 + replace:★ CSS 里的 % 和 { 都不会被当成格式符。"""
    q = c.get('qual') or []
    lab = VC.get(c.get('vc'), '没核过')
    vc_col = '#1f6b52' if c.get('vc') == 'ok' else '#b03a2e'
    tpl = """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>第 {{ISSUE}} 期 · {{HEAD}} · 有出处</title>
<link rel="canonical" href="{{BASE}}/archive/{{ISSUE}}.html">
<style>
:root{--ink:#16191b;--dim:#6b7370;--line:rgba(27,33,36,.14);--warn:#b03a2e;--ok:#1f6b52;--bg:#f2f5f4}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.w{max-width:720px;margin:0 auto;padding:34px 20px 56px}
a{color:#2f5d8c}
.bk{font-size:13px;color:var(--dim);text-decoration:none}
.iss{font-family:ui-monospace,Menlo,monospace;font-size:10px;letter-spacing:.14em;color:var(--warn);margin:18px 0 6px}
h1{font-size:24px;line-height:1.4;margin:0 0 12px}
.tg{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:99px;background:rgba(176,58,46,.07);color:#8d3b31;border:1px solid rgba(176,58,46,.16);margin:0 6px 6px 0}
.vc{border-left:3px solid var(--warn);padding-left:12px;margin:0 0 18px}
.vc .s{font-family:ui-monospace,Menlo,monospace;margin-right:7px;font-weight:600;font-size:16px}
.n{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:#2f5d8c}
.q{font-family:Georgia,"Songti SC",serif;font-size:15.5px;line-height:1.7;background:var(--bg);border-left:3px solid #c8d0cc;padding:12px 14px;margin:14px 0}
h2{font-size:13px;letter-spacing:.06em;color:var(--dim);margin:24px 0 8px}
.src{color:var(--dim);font-size:13px;overflow-wrap:anywhere}
.foot{margin-top:30px;padding-top:12px;border-top:1px solid var(--line);font-size:12.5px;color:var(--dim)}
</style></head><body><div class="w">
<a class="bk" href="{{BASE}}/">← 有出处</a>
<p class="iss">第 {{ISSUE}} 期 · 每日一期</p>
<h1>{{HEAD}}</h1>
<p>{{TAGS}}</p>
<div class="vc" style="border-left-color:{{VCCOL}}"><span class="s" style="color:{{VCCOL}}">{{SYM}}</span><b>{{LAB}}</b><br>
<span style="font-size:13px;color:var(--dim)">{{NOTE}}</span></div>
<p>核验号 <span class="n">bg.{{NO}}</span></p>
<h2>逐字原文</h2>
<div class="q">{{QUOTE}}</div>
<h2>口径说明</h2>
<div class="src">{{NUMS}}</div>
<h2>出处</h2>
<p class="src"><a href="{{URL}}" rel="noopener">{{URL}}</a></p>
<p class="foot">「{{LAB}}」只说明这条里的数字<b>当时</b>能在出处正文里找到,不说明结论是对的。<br>
「查不了」≠「不成立」;「没找到这个写法」≠「不存在」。<br>
<a href="{{BASE}}/feed.xml">订阅本刊(RSS)</a></p>
</div></body></html>"""
    d = {
        'ISSUE': issue, 'HEAD': esc(c['head']), 'BASE': base,
        'TAGS': ('<span class="tg">%s</span>' % '</span><span class="tg">'.join(esc(x) for x in q)) if q else '',
        'VCCOL': vc_col, 'SYM': SYM.get(c.get('vc'), '·'), 'LAB': esc(lab),
        'NOTE': '原文自己写明了限定' if q else '原文没有自述的限定词',
        'NO': esc(c['no']), 'QUOTE': esc(c.get('quote') or '（无）'),
        'NUMS': esc('; '.join('%s —— %s' % (n.get('n', ''), n.get('d', '')) for n in (c.get('nums') or [])) or '（无）'),
        'URL': esc(c.get('url') or ''),
    }
    for k, v in d.items():
        tpl = tpl.replace('{{' + k + '}}', v)
    return tpl


def main():
    cards = json.load(open(os.path.join(HERE, 'seed_cards.json'), encoding='utf-8'))['cards']
    pool = pub_pool(cards)
    os.makedirs(os.path.join(SITE_DIR, 'archive'), exist_ok=True)
    base = BASE or ''            # 没设 SITE_BASE 时用相对路径(自洽但 SEO 弱)
    items = []
    for i, c in enumerate(pool[:N]):
        issue = '%03d' % (i + 1)
        open(os.path.join(SITE_DIR, 'archive', issue + '.html'), 'w', encoding='utf-8').write(page(c, issue, base))
        desc = ('第 %s 期 · 核验号 bg.%s · 限定词:%s · 核验结论:%s。%s' % (
            issue, c['no'], '、'.join(c.get('qual') or []) or '无',
            VC.get(c.get('vc'), ''), (c.get('quote') or '')[:220]))
        items.append((issue, c, desc))

    # ── feed.xml ──
    now = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
             '<channel>',
             '<title>有出处 · 每日一期</title>',
             '<link>%s/</link>' % base,
             '<description>每天一期:原文自己写明了限定、最容易被当成事实转述出去的消息。附核验号与出处。</description>',
             '<language>zh-cn</language>',
             '<atom:link href="%s/feed.xml" rel="self" type="application/rss+xml"/>' % base,
             '<lastBuildDate>%s</lastBuildDate>' % now]
    for issue, c, desc in items:
        link = ('%s/signals/id-%04d.html' % (base, c['id'])) if base else ('signals/id-%04d.html' % c['id'])
        parts += ['<item>',
                  '<title>%s</title>' % esc('第 %s 期 · %s' % (issue, c['head'])),
                  '<link>%s</link>' % esc(link),
                  '<guid isPermaLink="false">issue-%s-%s</guid>' % (issue, c['no']),
                  '<description>%s</description>' % esc(desc),
                  '<pubDate>%s</pubDate>' % now,
                  '</item>']
    parts += ['</channel>', '</rss>']
    feed = '\n'.join(parts)
    open(os.path.join(SITE_DIR, 'feed.xml'), 'w', encoding='utf-8').write(feed)

    # ── 自检 ──
    import xml.etree.ElementTree as ET
    t = ET.fromstring(feed)
    its = t.findall('./channel/item')
    assert len(its) == min(N, len(pool)), 'item 数不对: %d' % len(its)
    for it in its:
        assert it.find('guid') is not None and it.find('link') is not None, 'item 缺 guid/link'
    assert len([f for f in os.listdir(os.path.join(SITE_DIR, 'archive')) if f.endswith('.html')]) >= len(items), '往期页数不够'
    assert '<link>' in feed and 'atom:link' in feed, 'feed 缺必要字段'
    print('✓ feed.xml · %d 期 · 往期页 %d 个 · 基址 %s' % (len(its), len(items), base or '(相对)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
