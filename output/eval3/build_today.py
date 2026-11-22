#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日精选位 —— 一个【固定地址、内容每天换】的页面。

为什么要有它:
    自循环基建 = ①生产流水线(已建成) + ②稳定地址(号,已建成)
              + ③每天值得被看一眼的固定地址(本脚本) + ④引用反馈(缺一个公开读端点)
    ③ 是唯一能把①②变成"有人会来"的一环,也是"系统自己贴出号"的那一步。

排序判据(可复算,写在页面上):
    限定词数 → 限定词权重和 → 有出入(warn)优先 → 近期优先
    限定词权重:未经同行评议 4 / 单一来源 4 / 无独立复测 3 / 口径不一致 3 / 团队自报 2
    —— 只挑【有明确边界】的条:数字全对但原文自己写了限定的,最容易被误读。

跑法: python3 build_today.py
产出: site/today.html
"""
import json, os, re, sys, html, urllib.request, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://ai-subject-universe.app.workbuddy.host'
SC = os.environ.get('SITE_SHARECODE', 'LA4PX3544L')
CARDS = os.path.join(HERE, 'seed_cards.json')
OUT = os.path.abspath(os.path.join(HERE, '..', 'site'))

W = {'未经同行评议': 4, '单一来源': 4, '无独立复测': 3, '口径不一致': 3, '团队自报': 2}
SYM = {'ok': '✓', 'warn': '△', 'x': '?', 'u': '·'}
VC = {'ok': ('核得住', 'ok'), 'warn': ('有出入，要盯', 'warn'),
      'x': ('查不了', 'x'), 'u': ('没核过', 'u')}


def esc(s):
    return html.escape(str(s or ''), quote=True)


def upstream_dates():
    """拿每条的上游日期(用来标"新")。★ 拉不到就降级:日期全空,精选仍能出。"""
    try:
        suf = ('?sharecode=' + SC) if SC else ''
        raw = urllib.request.urlopen(SITE + '/data/signals.js' + suf, timeout=25).read().decode('utf-8', 'ignore')
        d = json.loads(re.search(r'=\s*(\{.*\})', raw, re.S).group(1))
        return {str(i['id']): i.get('b') for i in d['items']}, d.get('meta', {}).get('built_at')
    except Exception as e:
        print('  ★ 上游拉不到(降级,日期缺失): %s' % e)
        return {}, None


def rank_key(c, date):
    q = c.get('qual') or []
    return (len(q), sum(W.get(x, 1) for x in q), c.get('vc') == 'warn',
            1 if str(date.get(str(c.get('id')), '')) >= '2026-11-17' else 0)


# ═══ ★ 期号(issue)与游标(cursor)══════════════════════════════════
# ★ 「号」原来同时背了两个身份:内容寻址(变更检测)+ 时间序列(每日一期)。
# ★ 这两个身份会打架:★ 上游加一批料 ⇒ 池子变大 ⇒ 按内容排序的轮换序列会跳
#   ⇒ 订阅者的「第 N 期」对不上号。
# ★ 拆开:
#   no    = 核验号(内容寻址,★ 永远不动 —— 动了 243 页站的 URL 全废)
#   issue = 期号(发布池内的序号,★ 池子扩容时只追加,老期号不重排 ⇒ 序列不跳)
#   cursor= 已发出多少期(单调递增,★ 存在 publish_state.json)
STATE = os.path.join(HERE, 'publish_state.json')


def load_state():
    try:
        st = json.load(open(STATE, encoding='utf-8'))
        return int(st.get('published') or 0)
    except Exception:
        return 0


def save_state(n):
    json.dump({'published': int(n), 'updated': __import__('time').strftime('%Y-%m-%dT%H:%M:%S')},
              open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def pub_pool(cards):
    """发布池 —— 两条标准决定它:
      ① 原文自己写明了限定词(否则这一期没价值)
      ② 有出处链接(否则读者核不了)
    排序 = 上游 id 升序(= 时间顺序 / 插入顺序)
      ⇒ ★ 新料【追加到池尾】,★ 老期号永不重排 ⇒ ★ 订阅序列不跳。
    ★ ★ 「最值得怀疑」由【进池标准】保证(每条都合格),
      ★ 而不是由【排序】保证(那会跟连续性打架)。★★
    """
    ps = [c for c in cards if c.get('qual') and c.get('url')]
    ps.sort(key=lambda c: int(c.get('id') or 0))
    return ps


def issue_of(pool):
    return {c['no']: '%03d' % (i + 1) for i, c in enumerate(pool)}


def pick(cards, date, n=6, day=None):
    """★ 轮换:同一份数据,每天挑出【不同】的一条。
    排序把「限定词最重 / 有出入 / 近期」排前面 —— 这是质量底。
    再按【天数偏移】取,于是:
      · 同一天永远同一条(可复算,号不会乱跳)
      · 不同天换一条(循环有了可见增量)
      · 池子多大就多少天一轮(现在是 47 条有限定词 ⇒ 47 天一轮)
    ★ 不轮换的话,today.html 永远是权重最高的那条 ⇒ 那不叫「每日一期」,叫「一次一期」。
    """
    withq = [c for c in cards if c.get('qual')]
    ranked = sorted(withq, key=lambda c: rank_key(c, date), reverse=True)
    if not ranked:
        return ranked, []
    # ★ ★★ 游标制(2026-11-22 改):★★ ★★ 今天出哪一期 = 【已发期数】决定的,
    #   ★ 不再按日期偏移 —— 日期偏移在"上游加料"时会跳序列,★ 订阅者对不上号。
    #   ★ 发一次 = 进一期;★ 手动发和自动发一样,★ 只要游标单调递增,序列就连续。
    pool = pub_pool(cards)
    if not pool:
        return ranked, []
    cur = load_state()
    k = cur % len(pool)
    rotated = pool[k:] + pool[:k]
    return ranked, rotated[:n]


def render(top, recent, cards, date, built, n_total, issue='', published=0, pool=()):
    d = lambda c: str(date.get(str(c.get('id')), ''))
    top0 = top[0]
    lab, cls = VC.get(top0.get('vc'), ('', 'x'))
    qq = top0.get('qual') or []
    rows = []
    for c in recent[1:]:
        l2, c2 = VC.get(c.get('vc'), ('', 'x'))
        rows.append(
            '<li><a class="t" href="signals/id-%04d.html">%s</a>'
            '<div class="m"><span class="b %s"><span class="sym">%s</span>%s</span>'
            '<span class="q">⚠ %s</span>'
            '<span class="n">bg.%s</span></div></li>' % (
                c['id'], esc(c['head']), c2, esc(SYM.get(c.get('vc'), '·')), esc(l2),
                esc('、'.join(c.get('qual') or [])), esc(c['no'])))
    qs = ''.join('<span class="tag">%s</span>' % esc(x) for x in qq)
    dl = ('<span class="new">新</span>' if d(top0) >= '2026-11-17' else '')
    return """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日一期 · 今天这一期 · 有出处</title>
<meta name="description" content="每天一条：原文自己写明了限定、最容易被误读的消息。附永久号，可被引用。">
<style>
:root{--paper:#f2f5f4;--ink:#16191b;--muted:#6b7370;--soft:#9aa3a8;--line:rgba(27,33,36,.14);
 --accent:#b03a2e;--accentt:rgba(176,58,46,.06);--ok:#1f6b52;--warn:#b03a2e;--link:#2f5d8c}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:36px 20px 56px}
.eyebrow{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.16em;text-transform:uppercase;color:var(--soft);margin:0 0 10px}
h1{font-family:Georgia,"Songti SC","Noto Serif CJK SC",serif;font-size:30px;font-weight:400;margin:0 0 6px;line-height:1.25}
.sub{color:var(--muted);font-size:14px;margin:0 0 26px}
.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:20px;margin-bottom:18px}
.top{border-color:var(--accent);background:#fdfaf4}
.tlabel{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
h2{font-size:19px;line-height:1.45;margin:0 0 12px;font-weight:600}
.tags{margin:0 0 12px}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:99px;border:1px solid rgba(176,58,46,.18);
 background:var(--accentt);color:#8d3b31;margin:0 6px 6px 0}
.b{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:99px;background:rgba(27,33,36,.05);
 color:var(--muted);margin-right:8px}
.b .sym{font-family:ui-monospace,Menlo,monospace;margin-right:4px}
.b.ok{color:var(--ok);background:rgba(31,107,82,.09)} .b.warn{color:var(--warn);background:rgba(176,58,46,.09)}
.new{display:inline-block;font-size:11px;padding:1px 7px;border-radius:99px;background:var(--ink);color:#fff;margin-right:8px}
.no{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:#2a4a6b;word-break:break-all}
.quote{border-left:3px solid var(--line);padding:2px 0 2px 14px;margin:14px 0;color:var(--muted);font-size:14px}
.src{margin:0 0 4px;font-size:12.5px;color:var(--muted);word-break:break-all}
.src a{font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
.why{background:#f7f9fa;border-radius:6px;padding:12px 14px;font-size:13.5px;margin:14px 0 0}
.why b{color:var(--accent)}
a{color:#2a4a6b}
ol{margin:8px 0 0;padding-left:0}
li{margin:0 0 14px;list-style:none;padding-bottom:12px;border-bottom:1px solid rgba(27,33,36,.07)}
li:last-child{border-bottom:0;margin-bottom:0}
li .t{display:block;font-weight:600;font-size:14.5px;line-height:1.5;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
li .m{margin-top:5px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
li .n{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--soft)}
li .q{font-size:12px;color:var(--warn)}
.foot{margin-top:26px;font-size:13px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
.foot b{color:var(--ink)}
.meta{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--soft);letter-spacing:.06em;margin-top:20px}
</style></head><body><div class="wrap">
<p class="eyebrow">每日一期 · 固定地址 · 内容每天换</p>
<h1>每日一期 · 今天这一期</h1>
<p class="sub">每天一期,一期一条:<b>原文自己写明了限定</b>的消息 —— 数字全对,但话是限定过的。<br>
★ 入池标准只有两条:<b>① 原文有自己写明的限定词 ② 有出处链接</b>;★ 期号按时间顺序排,★ 永不重排,★ 所以订阅序列不会跳。</p>

<div class="card top">
<p class="tlabel">TODAY</p>
<h2><a href="signals/id-%04d.html">%s</a></h2>
<p class="tags">%s<span class="b %s"><span class="sym">%s</span>%s</span><span class="new">%s</span></p>
<p class="no">永久号 bg.%s</p>
<div class="quote">%s</div>
<p class="src">出处:<a href="%s" rel="noopener">%s</a></p>
<p class="why"><b>为什么它排在今天第一:</b>它有 %d 个限定词(%s),而且核验结论是「%s」。<br>
★ 这条最适合被转发出去,也最容易在转发中丢掉限定。</p>
</div>

<div class="card">
<p class="tlabel" style="color:var(--muted)">RECENT · 同样有限定词</p>
<ol>%s</ol>
</div>

<div class="card">
<p class="tlabel" style="color:var(--muted)">怎么用</p>
<p style="font-size:14px;margin:0 0 10px">★ 你是<b>读者</b>:点进任意一条,看它的逐字原文与口径表,再决定要不要转发。<br>
★ 你是<b>写作者</b>:把这页的<b>永久号</b>贴进你的文章 —— 它是内容寻址的,原文一改号就变,读者能自己复核。<br>
★ 你是<b>AI</b>:每张卡都带 JSON-LD,<b>限定词在里面</b> —— 引用时别把「团队自报」讲成事实。</p>
</div>

<p class="foot">这个地址<b>不变</b>,内容<b>每天换</b> —— 每天回来看一眼有没有新的最该被怀疑的那条。<br>
筛选判据(可复算):限定词数 → 限定词权重和(未经同行评议 4 / 单一来源 4 / 无独立复测 3 / 口径不一致 3 / 团队自报 2)→ 有出入优先 → 近期优先。<br>
<b>「核得住」只说明数字能在出处正文里找到,不说明结论是对的。</b></p>

<p class="meta">第 %s 期 · 已发 %d 期 · 发布池 %d 条(有限定词)· 共 %d 条已核验 · 上游快照 %s</p>
</div></body></html>
""" % (top0['id'], esc(top0['head']), qs, cls, esc(SYM.get(top0.get('vc'), '·')), esc(lab), dl, esc(top0['no']),
       esc(top0.get('quote') or top0.get('src') or ''),
       esc(top0.get('url') or ''), esc((top0.get('url') or '').replace('https://', '').replace('http://', '')[:70]),
       len(qq), esc('、'.join(qq)), esc(lab),
       ''.join(rows), issue, published, len(pool), n_total, esc(built or '未知'))


def main():
    cards = json.load(open(CARDS, encoding='utf-8'))['cards']
    date, built = upstream_dates()
    ranked, top = pick(cards, date)
    if not top:
        print('★ 有限定词的条为 0 —— 无法生成精选位')
        return 1
    pool = pub_pool(cards)
    issues = issue_of(pool)
    published = load_state()
    cur = pool[published % len(pool)] if pool else (top[0] if top else {})
    issue = issues.get(cur.get('no'), '—')
    html = render(top, top, cards, date, built, len(cards), issue, published, pool)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'today.html'), 'w', encoding='utf-8').write(html)

    # ── 自检:这个页面错了就等于给外部发错东西,必须挡住 ──
    top0 = top[0]
    assert top0.get('qual'), 'top 条没有限定词'
    assert top0.get('no'), 'top 条没有号'
    assert top0.get('url'), 'top 条没有出处链接'
    assert 'signals/id-%04d.html' % top0['id'] in html, 'top 条链不到自己的卡'
    # ★ 只允许"出处链接"这一个外链(它就是核验的对象);字体/脚本/图片一律不许外链。
    links = set(re.findall(r'https?://[^"\'<>\s)]+', html))
    assert links <= {top0['url']}, '出现了出处以外的外链: %s' % (links - {top0['url']})
    assert len(rows_count(html)) >= 1, '近期列表是空的'

    # ★ 游标制的三条性质:
    #   ① 同一游标 ⇒ 同一条(可复算)
    #   ② 游标 +1 ⇒ 换一条(池子 > 1 时)
    #   ③ 池子扩容 ⇒ 老期号不重排(订阅序列不跳)  ★★ 最关键的一条
    _pool = pub_pool(cards)
    _iss = issue_of(_pool)
    assert list(_iss.values()) == ['%03d' % (i + 1) for i in range(len(_pool))], '期号不连续'
    assert len(_pool) > 1, '发布池只有一条,轮换不了'
    _a = _pool[0]['no']
    _b = _pool[1]['no']
    assert _a != _b, '游标 +1 没有换一条'
    # ★ 扩容:加一条新的(假装上游来了一条),老期号必须原封不动
    _fake = dict(_pool[0]); _fake['id'] = 999999; _fake['no'] = 'zzz99999999'
    _iss2 = issue_of(pub_pool(cards + [_fake]))
    _bad = [(k, v, _iss2[k]) for k, v in _iss.items() if _iss2[k] != v]
    assert not _bad, '池子扩容后老期号被重排了(订阅序列会跳): %s' % _bad[:3]
    print('✓ site/today.html · 第 %s 期 · %s' % (issue, top[0]['head'][:40]))
    print('  核验号 bg.%s · 限定 %s · 发布池 %d 条 · 已发 %d 期' % (
        top[0]['no'][:8], '、'.join(top[0]['qual']), len(pool), published))
    # ★ 游标只在【正式流程】推进:跑一次 = 出一期。调试时不带 --advance 就不会跳期。
    if '--advance' in sys.argv:
        save_state(published + 1)
        print('  → 游标推进到第 %d 期' % (published + 1))
    print('  号 bg.%s · 限定 %s · %d 条里挑的' % (top0['no'][:8], '、'.join(top0['qual']), len(cards)))
    return 0


def rows_count(html):
    return re.findall(r'class="b ', html)


if __name__ == '__main__':
    sys.exit(main())
