#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 把「有出处」做成一个【免码、纯静态】的站 —— 可以部署到任何静态托管。

跑法: python3 eval3/build_site.py
输入: eval3/seed_cards.json(227 条,带号/四态/限定词/逐字原文/口径)
输出: output/site/
        index.html                    全部条目 + 搜号 + 分类筛选(支持 ?no=<号> 直达)
        signals/id-XXXX.html          每条一张卡(带 JSON-LD / og:image / 号 / 限定词)
        assets/og/id-XXXX.png         每卡一张 1200×630 分享图

★ 为什么必须是静态 + 免码:
  1. WorkBuddy 那个站要 sharecode ⇒ 搜索引擎收不到带参数的 URL、机器抓不到、链接不能独立转发
     ⇒ 「号」建得再好也没人能找到它
  2. 静态 = 零成本、零运维,而且不会因为平台策略一变就整体 403
  3. 部署在哪儿都行(GitHub Pages / Cloudflare Pages / 自己的服务器)⇒ 号 → 地址 的映射由你控制
"""
import json, os, re, sys, html as H, subprocess, base64

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'site')
CARDS = json.load(open(os.path.join(HERE, 'seed_cards.json'), encoding='utf-8'))['cards']

SITE_NAME = '有出处'
# ★ 号 → 落地页。这个映射是整个站的公开地址层;换域名也不用重算号。
# ★ 限定词从主数据读(seed_cards.json),不再自己重算
SYM = {'ok': '✓', 'warn': '△', 'x': '?', 'u': '·'}
VC = {'ok': ('核得住', 'ok'), 'warn': ('有出入，要盯', 'warn'),
      'x': ('查不了', 'none'), 'u': ('没核过', 'none')}
VC_LONG = {
    'ok': '抓到出处正文,这条里的每个数字都能找到',
    'warn': '抓到出处正文,但有数字在正文里没找到',
    'x': '没抓到出处正文 —— 查不了,不代表有问题,也不代表没问题',
    'u': '没有链接 —— 从来没被查过',
}


def _dead_map():
    """★ 出处【浏览器复核后】仍打不开的 URL —— 只认这一个来源。
    ★ 机器探测的 403/超时/URLError 不算死链:★ 那是【我这台机器】的网络环境,
    ★   不是读者能不能打开。★ 实测 30 条机器异常 → 浏览器复核只剩 1 条真 404。"""
    import os as _os, json as _json
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'link_alive_browser.json')
    try:
        _b = _json.load(open(_p, encoding='utf-8'))
    except Exception:
        return {}, ''
    _dead = {u: v for u, v in _b.items() if v in (404, 410) or (isinstance(v, int) and v >= 400)}
    _at = ''
    for v in _b.values():
        _at = _at or ''
    return _dead, '2026-11-22'


_DEAD, _DEAD_AT = _dead_map()


def dead_note(c):
    """只在【浏览器复核也打不开】时标一行,且必须带时点。"""
    u = c.get('url')
    if not u or u not in _DEAD:
        return ''
    return ('<div class="dead"><b>⚠ 出处已失效</b>（%s 用浏览器复核,仍返回 %s）'
            '<br>这条的核验结论是<b>当时</b>的事实;★ 出处现在打不开了 —— '
            '「核得住」只说明数字<b>当时</b>能在出处正文里找到。</div>'
            % (_DEAD_AT or '最近一次', _DEAD.get(u)))


def qual_of(c):
    return c.get('qual') or []   # ★ 从主数据读,不重算


def esc(s):
    return H.escape(str(s or ''), quote=True)


def jdump(o):
    return json.dumps(o, ensure_ascii=False, indent=1)


def site_base():
    """★ 「部署到哪」的唯一真源:site_config.json 的 base > 环境变量 SITE_BASE > 空(相对)"""
    try:
        _c = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site_config.json'), encoding='utf-8'))
        _b = (_c.get('base') or '').strip()
        if _b: return _b.rstrip('/')
    except Exception:
        pass
    return (os.environ.get('SITE_BASE') or '').rstrip('/')


def card_html(c, og_base=''):
    vc = c['vc']
    label, cls = VC[vc]
    q = qual_of(c)
    n = c.get('nums') or []
    src = c.get('src') or ''
    rows = ''.join(
        '<tr><td class="mono">%s</td><td>%s</td></tr>' % (esc(x['n']), esc(x['d'])) for x in n)
    qual_html = ''
    if q:
        qual_html = ('<div class="qual"><b>⚠ 原文自己写明：%s</b>'
                     '<span>（数字对得上，但这话是限定过的 —— 见下面的口径说明）</span></div>'
                     % esc('、'.join(q)))
    # ★ JSON-LD:号 + 限定词 + 免码地址 + 四态 —— 这是"给 AI 读"的那一栏
    ld = {
        '@context': 'https://schema.org', '@type': 'NewsArticle',
        'headline': c['head'], 'datePublished': c.get('day') or '',
        'dateModified': c.get('day') or '', 'inLanguage': 'zh-CN',
        'author': {'@type': 'Organization', 'name': SITE_NAME,
                   'description': '独立 AI 信号核验台；可信度非审批、非认证、非官方背书'},
        'publisher': {'@type': 'Organization', 'name': SITE_NAME,
                      'description': '独立 AI 信号核验台；可信度非审批、非认证、非官方背书'},
        'mainEntityOfPage': '%s/signals/id-%04d.html' % (og_base, c['id']),
        'url': '%s/signals/id-%04d.html' % (og_base, c['id']),
        'isBasedOn': c.get('url') or '',
        'description': c['head'] + '｜' + label + '｜号 bg.' + c['no'],
        'about': [{'@type': 'PropertyValue', 'name': '号', 'value': 'bg.' + c['no']},
                  {'@type': 'PropertyValue', 'name': '核验状态', 'value': VC_LONG[vc]},
                  {'@type': 'PropertyValue', 'name': '编号', 'value': c['no']},
                  {'@type': 'PropertyValue', 'name': '可信度', 'value': label}]
                  + ([{'@type': 'PropertyValue', 'name': '限定', 'value': '、'.join(q)}] if q else [])
                  + [{'@type': 'PropertyValue', 'name': '原文链可达性', 'value': '可直达'}],
    }
    return """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · {site}</title>
<meta name="description" content="{desc}">
<meta name="ai-content-id" content="{no}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<link rel="canonical" href="{url}">
<script type="application/ld+json">
{ld}
</script>
<style>
:root{{--ink:#16191b;--dim:#6b7370;--line:#e3e7e5;
 --warn:#b03a2e;--ok:#1f6b52;--link:#2f5d8c;--bg:#f2f5f4}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:820px;margin:0 auto;padding:22px 18px 70px}}
h1{{font-size:23px;margin:0 0 6px;line-height:1.4}}
.meta{{color:var(--dim);font-size:13px;margin:0 0 16px}}
.box{{margin:0 0 18px;padding:0 0 0 12px;border-left:3px solid var(--line)}}
.box.warn{{border-left-color:var(--warn)}} .box.ok{{border-left-color:var(--ok)}}
.box .vc{{font-size:17px;font-weight:600;letter-spacing:.01em}}
.box .vc .sym{{font-family:ui-monospace,Menlo,monospace;margin-right:7px}}
.blk{{margin:0 0 16px}}
h3{{font-size:14px;margin:0 0 10px;font-weight:700}}
h3 .sub{{font-weight:400;color:var(--dim);font-size:12.5px}}
.vc{{font-weight:700;font-size:16px}}
.vc.ok{{color:var(--ok)}} .vc.warn{{color:var(--warn)}} .vc.none{{color:var(--dim)}}
.vc.none .sym{{color:var(--dim)}}
.vcnote{{font-size:13px;color:var(--dim);margin:4px 0 0}}
.qual{{background:rgba(176,58,46,.045);border-left:3px solid var(--warn);
 padding:9px 12px;margin:0 0 18px;font-size:13.5px;color:#7a3830}}
.qual b{{color:var(--warn)}}
.qual span{{display:block;color:#8d6159;font-size:12.5px;margin-top:3px}}
.qt{{font-family:Georgia,"Songti SC","Noto Serif CJK SC",serif;font-size:15.5px;line-height:1.7;
 background:var(--bg);border-left:3px solid #c8d0cc;padding:12px 14px;border-radius:0 6px 6px 0;
 white-space:pre-wrap;overflow-wrap:anywhere}}
.qt .qm{{display:block;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;
 font-size:12px;color:var(--dim);margin-top:8px}}
.tbl{{width:100%;border-collapse:collapse;font-size:13.5px}}
.tbl th{{text-align:left;color:var(--dim);font-weight:600;font-size:12.5px;border-bottom:1px solid var(--line);padding:7px 8px}}
.tbl td{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top}}
.tbl td:first-child{{width:32%;font-family:ui-monospace,Menlo,monospace;
 font-variant-numeric:tabular-nums;font-size:13px;white-space:nowrap;vertical-align:top}}
.mono{{font-family:ui-monospace,Menlo,monospace}}
a{{color:#2a4a6b}}
.srcs{{color:var(--dim);font-size:13px;margin:0 0 10px;overflow-wrap:anywhere;word-break:break-word}}
.dead{{background:rgba(176,58,46,.05);border-left:3px solid var(--warn);padding:10px 12px;
 margin:0 0 18px;font-size:13px;color:#7a3830}}
.dead b{{color:var(--warn)}}
.srcs a{{word-break:break-all}}
.no{{font-family:ui-monospace,Menlo,monospace;font-weight:700;color:#2a4a6b;font-size:15px}}
.foot{{margin-top:26px;padding:13px 15px;background:var(--bg);border:1px solid var(--line);border-radius:8px;font-size:12.5px;color:var(--dim)}}
.back{{font-size:13px;margin:0 0 14px}}
.btnrow{{margin:0 0 18px;display:flex;gap:10px;align-items:center}}
.btnrow button{{border:1px solid #2a4a6b;background:#fff;color:#2a4a6b;border-radius:7px;
  padding:8px 14px;font:inherit;font-size:13.5px;cursor:pointer}}
.btnrow button:hover{{background:#2a4a6b;color:#fff}}
.btnrow span{{font-size:12.5px;color:#6b7370}}
</style></head><body><div class="wrap">
<p class="back"><a href="../index.html">← {site}</a></p>
<h1>{title}</h1>
<p class="meta">{tag} · {date} · 分类 {cat} · 号 <span class="no">bg.{no}</span></p>
<div class="box {cls}">
  <div class="vc {cls}"><span class="sym">{sym}</span>{label}</div>
  <p class="vcnote">{vcnote}</p>
</div>
{qual}
{deadnote}
<div class="blk"><h3>逐字原文 <span class="sub">（引用者抄的这段，不是我改写的）</span></h3>
<div class="qt">{quote}<span class="qm">↑ 原文里被引用的就是这一句;完整原文在下面「出处」。</span></div></div>
{numsblk}
<div class="blk"><h3>出处</h3><p class="srcs">{src}</p>
<p class="srcs">原始链接：{link}</p></div>
<div class="blk"><h3>这条的锐评 <span class="sub">（判断，不是事实）</span></h3><p>{key}</p></div>
<script type="application/json" id="rdata">{rdata}</script>
<div class="btnrow"><button id="rcpt">复制核验结果</button><span id="rcpthint"></span></div>
<div class="foot">这张卡标的是<b>「我核到哪儿」和「哪些还没核」</b>—— 结论对不对，得你自己看。
核验只覆盖了网页正文里的文字；数字若在图片、图表或附件里，这里看不到。<br>
号 <span class="no">bg.{no}</span> 是内容寻址的（结论+原文+规则版本的哈希）：<b>内容一改，号就变</b>。同一个号永远是同一份内容。</div>
<script>
/* ★ 核验收据:读者核完可以把它带走,贴回给作者。
   这是"卖收据不卖信号"的读者侧 —— 核验不该只在作者自己的机器上发生。 */
function receiptText(){{
  const d=JSON.parse(document.getElementById('rdata').textContent);
  const lines=[];
  lines.push('我核了 bg.'+d.no);
  lines.push('《'+d.title+'》');
  lines.push('核验状态：'+d.vc+'（'+d.vcnote+'）');
  if(d.quals&&d.quals.length) lines.push('原文自述：'+d.quals.join('、'));
  lines.push('出处：'+d.url);
  lines.push('（这一条只核了「这个数在出处正文里找不找得到」；结论对错仍需自己判断。）');
  return lines.join(String.fromCharCode(10));
}}
document.getElementById('rcpt').onclick=function(){{
  const t=receiptText();
  const done=()=>{{ document.getElementById('rcpthint').textContent='已复制 ✓ 可以贴回给作者';
    setTimeout(()=>document.getElementById('rcpthint').textContent='',2200); }};
  if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done,done);
  else {{ const ta=document.createElement('textarea'); ta.value=t; document.body.appendChild(ta); ta.select();
    try{{document.execCommand('copy');done();}}catch(e){{}} ta.remove(); }}
}};
</script>
</div></body></html>""".format(
        title=esc(c['head']), site=esc(SITE_NAME),
        desc=esc(c['head'] + '｜' + label + '｜号 bg.' + c['no']),
        no=esc(c['no']), tag=esc(c.get('tag') or ''), date=esc(c.get('day') or ''),
        cat=esc(c.get('cat') or ''), label=esc(label), cls=cls, vcnote=esc(VC_LONG[vc]),
        qual=qual_html, quote=esc(c.get('quote') or '（无）'), key=esc(c.get('key') or ''),
        deadnote=dead_note(c),
        sym=SYM.get(vc, '·'),
        src=esc(src), link=('<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(c['url']), esc(c['url']))) if c.get('url') else '（无）',
        numsblk=('<div class="blk"><h3>口径说明 <span class="sub">（跟着数字一起存的，别让它丢）</span></h3>'
                 '<table class="tbl"><tr><th style="width:26%%">数字</th><th>口径 / 来源</th></tr>%s</table></div>' % rows) if rows else '',
        url=('%s/signals/id-%04d.html' % (og_base, c['id'])),
        img='%s/assets/og/id-%04d.png' % (og_base, c['id']),
        ld=jdump(ld),
        rdata=json.dumps({'no': c['no'], 'title': c['head'], 'vc': label,
                          'vcnote': VC_LONG[vc], 'quals': q, 'url': c.get('url') or ''},
                         ensure_ascii=False).replace('</', '<\\/'))


def index_html(cards, og_base='', byurl=None, picks=None, qcounts=None):
    q = qual_of
    picks = picks or []
    qcounts = qcounts or []
    items = []
    for c in sorted(cards, key=lambda x: -(x.get('id') or 0)):
        label, cls = VC[c['vc']]
        qq = q(c)
        items.append(
            '<li class="it" data-t="%s" data-c="%s" data-q="%s">'
            '<a class="h" href="signals/id-%04d.html">%s</a>'
            '<span class="b %s">%s</span>'
            '%s'
            '<span class="n">bg.%s</span></li>' % (
                esc(c['head']), esc(c['cat']), esc('、'.join(qq)), c['id'], esc(c['head']),
                cls, label,
                ('<span class="q">⚠ %s</span>' % esc('、'.join(qq))) if qq else '',
                esc(c['no'])))
    byurl = byurl or {}
    cats = []
    seen = set()
    for c in cards:
        if c.get('cat') and c['cat'] not in seen:
            seen.add(c['cat'])
            cats.append(c['cat'])
    # ★ 今日精选 —— 复用 build_today.py 的同一份选题逻辑(一份实现,两个调用方)
    from build_today import pick as _pick, upstream_dates as _dates
    _date, _built = _dates()
    _ranked, _top = _pick(cards, _date)
    picks = ''
    # ★ 第 1 条完整展开,后 2 条压成一行 —— 精选要"精",不能被两条长标题吃掉一屏
    for _i, c in enumerate(_top[:3]):
        _qq = c.get('qual') or []
        _l2, _c2 = VC.get(c.get('vc'), ('', 'x'))
        _sym = SYM.get(c.get('vc'), '·')
        if _i == 0:
            picks += ('<div class="pc lead"><a class="ph" href="signals/id-%04d.html">%s</a>'
                      '<p class="pt">%s<span class="b %s"><span class="sym">%s</span>%s</span>'
                      '<span class="pn">bg.%s</span></p></div>' % (
                          c['id'], esc(c['head']),
                          ''.join('<span class="tag">%s</span>' % esc(x) for x in _qq),
                          _c2, esc(_sym), esc(_l2), esc(c['no'])))
        else:
            picks += ('<div class="pc rest"><a class="ph2" href="signals/id-%04d.html">%s</a>'
                      '<span class="b %s"><span class="sym">%s</span>%s</span>'
                      '<span class="pn">bg.%s</span></div>' % (
                          c['id'], esc(c['head']), _c2, esc(_sym), esc(_l2), esc(c['no'])))
    # ★ 限定词入口 —— 产品最核心的概念,提升到导航层
    _qc = {}
    for c in cards:
        for x in (c.get('qual') or []):
            _qc[x] = _qc.get(x, 0) + 1
    qchips = ''.join('<span class="chip" data-qk="%s">%s <i>%d</i></span>' % (
        esc(x), esc(x), _n2) for x, _n2 in sorted(_qc.items(), key=lambda kv: -kv[1]))
    return """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site}｜每条消息标明出处与核验到哪儿</title>
<meta name="description" content="{n} 条消息，每条一个永久号、标明出处、以及这条我核到哪儿了——包括我没核的部分。">
<meta name="robots" content="index,follow">
<script type="application/ld+json">
{ld}
</script>
<style>
:root{{--ink:#16191b;--dim:#6b7370;--line:#e3e7e5;--warn:#b03a2e;--ok:#1f6b52;--link:#2f5d8c;--bg:#f2f5f4}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:22px 18px 70px}}
h1{{font-size:24px;margin:0 0 6px}}
.sub{{color:var(--dim);font-size:14px;margin:0 0 18px}}
.bar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px}}
input[type=search]{{flex:1;min-width:240px;padding:11px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;font-size:15px}}
.chips{{display:flex;gap:7px;flex-wrap:wrap}}
.nav{{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;padding:14px 0 16px;
 border-bottom:1px solid var(--line);margin-bottom:20px}}
.nav .brand{{font-weight:700;font-size:17px;color:var(--ink)}}
.nav a{{font-size:14px;color:#2a4a6b;text-decoration:none;border-bottom:1px solid rgba(42,74,107,.25)}}
.nav a:hover{{border-bottom-color:#2a4a6b}}
.nav .sp{{flex:1}}
.nav .nm{{font-size:12px;color:var(--dim);font-family:ui-monospace,Menlo,monospace}}
@media (max-width:560px){{.nav .nm{{display:none}}}}
.pick{{margin:26px 0 30px;padding:18px 20px;background:#fff;border:1px solid var(--line);border-radius:8px}}
.pick h2{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink);margin:0 0 12px;font-weight:600}}
.pick h2 .sym{{font-family:ui-monospace,Menlo,monospace;color:var(--warn);margin-right:6px}}
.pc{{padding:11px 0;border-bottom:1px solid rgba(20,24,26,.07)}}
.pc.lead .ph{{font-size:16.5px}}
.pc.rest{{display:flex;align-items:baseline;gap:10px;padding:9px 0}}
.pc.rest .ph2{{flex:1;min-width:0;font-size:13.5px;color:var(--ink);text-decoration:none;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pc.rest .b{{margin:0;flex:none}} .pc.rest .pn{{flex:none}}
.pc:last-of-type{{border-bottom:0}}
.pc .ph{{font-size:15.5px;font-weight:600;color:var(--ink);text-decoration:none;line-height:1.45;display:block}}
.pc .ph:hover{{color:#2a4a6b}}
.pc .pt{{margin:6px 0 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.pc .pn{{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--dim)}}
.pickmore{{margin:12px 0 0;font-size:13px}}
.tag{{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:99px;
 background:rgba(176,58,46,.07);color:#8d3b31;border:1px solid rgba(176,58,46,.16)}}
.how{{margin:34px 0 0;padding:22px 24px;background:#fff;border:1px solid var(--line);border-radius:10px}}
.how h2{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin:0 0 14px;font-weight:600}}
.steps{{margin:0 0 16px;padding-left:1.3em}}
.steps li{{margin:7px 0;font-size:14.5px}}
.disc{{background:#f5f7f6;border-radius:8px;padding:13px 15px;font-size:13.5px;line-height:1.75}}
.disc b{{color:var(--warn)}}
.chip i{{font-style:normal;font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:var(--dim);margin-left:3px}}
.allbox{{margin:30px 0 0}}
.allbox details{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 18px}}
.allbox summary{{cursor:pointer;list-style:none;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}
.allbox summary::-webkit-details-marker{{display:none}}
.allbox summary:before{{content:"▸";color:var(--ink);font-size:13px}}
.allbox details[open] summary:before{{content:"▾"}}
.allbox summary .sm{{font-size:12.5px;color:var(--dim);font-weight:400}}
.chip{{font-size:12.5px;padding:4px 10px;border:1px solid var(--line);border-radius:99px;color:var(--dim);cursor:pointer;background:#fff}}
.chip.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
ul{{list-style:none;padding:0;margin:0}}
.it{{padding:12px 0;border-bottom:1px solid var(--line)}}
.it .h{{display:block;color:var(--ink);text-decoration:none;font-weight:600;font-size:15.5px;line-height:1.5}}
.it .h:hover{{color:#2a4a6b}}
.b{{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:99px;margin:6px 6px 0 0;
 background:rgba(27,33,36,.045);color:var(--dim)}}
.b .sym{{font-family:ui-monospace,Menlo,monospace;margin-right:4px}}
.b.ok{{color:var(--ok);background:rgba(31,107,82,.08)}} .b.warn{{color:var(--warn);background:rgba(176,58,46,.08)}}
.q{{display:inline-block;font-size:12px;padding:1px 8px;border-radius:99px;margin:6px 6px 0 0;background:#fdf1e3;color:var(--warn)}}
.n{{display:block;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--dim);margin-top:4px}}
.foot{{margin-top:28px;padding:13px 15px;background:var(--bg);border:1px solid var(--line);border-radius:8px;font-size:12.5px;color:var(--dim)}}
#no{{display:none}}
.hit{{margin:0 0 18px;padding:13px 15px;border-radius:9px;border:1px solid var(--line);background:#fafbf9;font-size:14px}}
.hit b{{font-size:15px}}
.hit .hl{{color:var(--dim);font-size:13px;margin-top:5px}}
.hit .mono{{font-family:ui-monospace,Menlo,monospace;color:#2a4a6b}}
.hit .q{{color:var(--warn)}}
.hit .go{{display:inline-block;margin-top:7px;font-size:13.5px;color:#2a4a6b}}
.hit.ok{{border-color:#cfe6dc}} .hit.warn{{border-color:#ecdcc4}} .hit.none{{color:var(--dim)}}
</style></head><body><div class="wrap">
<nav class="nav"><span class="brand">{site}</span>
<a href="today.html">今天一条</a><a href="#all">全部条目</a><a href="#how">怎么核的</a>
<span class="sp"></span><span class="nm">{n} 条 · 每条一个永久号</span></nav>
<p class="sub">每条消息标明出处、<b>这条我核到哪儿了——包括我没核的部分</b>。<br>
号是内容寻址的：结论或原文一改，号就变。</p>

<section id="today" class="pick">
<h2><span class="sym">△</span>今天最值得你怀疑的一条</h2>
{picks}
<p class="pickmore"><a href="today.html">看今天这页 →</a></p>
</section>
<div class="bar"><input type="search" id="q" placeholder="搜标题、号（bg.xxxxxxxx）、分类、限定词…"></div>
<section class="allbox" id="all">
<details id="allbox"><summary><b>全部 {n} 条</b><span class="sm">可搜号 / 标题,可按分类与限定词筛</span></summary>
<div class="chips" id="chips">{chips}</div>
<div class="chips" id="qchips">{qchips}</div>
<div class="hit" id="urlHit" style="display:none"></div>
<ul id="list">{items}</ul>
</details></section>

<section id="how" class="how">
<h2>怎么核的</h2>
<ol class="steps">
<li><b>抓出处全文</b>——不是看摘要，是把原文抓下来</li>
<li><b>数值归一</b>——820万 = 8.2 million = 8,000,000，同一个数才算同一个数</li>
<li><b>逐个数一遍</b>——这条里的每个数字，出处正文里找得到吗</li>
<li><b>抽限定词</b>——<b>原文自己写明的边界</b>：团队自报 / 未经同行评议 / 无独立复测 / 单一来源 / 口径不一致</li>
<li><b>判四态</b>——<b>v 已成立 · r 不成立 · x 查不了 · u 没核过</b></li>
</ol>
<div class="disc"><b>两条纪律</b>：①「<b>查不了</b>」≠「不成立」——抓不到原文只能说明我不知道，不能说明它假；
②「<b>没找到这个写法</b>」≠「不存在」——原文只是换了说法。<br>
<b>号 = FNV-1a32(结论 + 原文 + 规则版本)</b>：结论或原文一改，号就变 ⇒ <b>号本身就是变更检测器</b>。</div>
</section>
<p class="foot">这里的「核得住」只说明<b>这条里的数字能在出处正文里找到</b>，不说明结论是对的。<br>
⚠ 标出来的是<b>原文自己写明的限定</b>（团队自报 / 未经同行评议 / 无独立复测 / 口径不一致）——这些是线索，不是结论。</p>
</div>
<script>
const list=document.getElementById('list'), q=document.getElementById('q');
const BYURL=__BYURL__, BYNO=__BYNO__;
function esc(s){{return String(s==null?'':s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));}}
let cat='',qk='';
document.getElementById('chips').addEventListener('click',function(e){{
  const c=e.target.dataset.c; if(c===undefined) return;
  cat=(cat===c)?'':c;
  document.querySelectorAll('#chips .chip').forEach(x=>x.classList.toggle('on',x.dataset.c===cat));
  filt();
}});
document.getElementById('qchips').addEventListener('click',function(e){{
  const k=e.target.dataset.qk; if(k===undefined) return;
  qk=(qk===k)?'':k;
  document.querySelectorAll('#qchips .chip').forEach(x=>x.classList.toggle('on',x.dataset.qk===qk));
  filt();
}});
function filt(){{
  const s=q.value.trim().toLowerCase();
  if(s) document.getElementById('allbox').open=true;
  list.querySelectorAll('.it').forEach(function(it){{
    const hay=(it.dataset.t+' '+it.dataset.q+' '+it.textContent).toLowerCase();
    const okq=!qk||(it.dataset.q&&it.dataset.q.indexOf(qk)>=0);
    it.style.display=((!s||hay.includes(s))&&(!cat||it.dataset.c===cat)&&okq)?'':'none';
  }});
}}
q.addEventListener('input',function(){{ document.getElementById('allbox').open=true; filt(); }});
/* ★ 按号直达:?no=bg.xxxxxxxx —— 号是地址,不是装饰 */
(function(){{
  const no=new URLSearchParams(location.search).get('no');
  if(!no) return;
  const t=no.replace(/^bg\./,'').toLowerCase();
  document.getElementById('q').value='bg.'+t;
  document.getElementById('allbox').open=true;
  filt();
  const hit=Array.from(list.querySelectorAll('.it')).find(it=>it.textContent.includes('bg.'+t));
  if(hit){{ hit.scrollIntoView({{behavior:'smooth',block:'center'}});
    const a=hit.querySelector('.h'); a.style.outline='2px solid #16191b'; a.style.borderRadius='4px'; }}
}})();

/* ★★ 按出处链接反查:?url=<出处原文的链接>
   ★ 这是【读者】的入口 —— 读者手上通常不是号,是那条出处链接。
   ★ 站里有没有核过这一条、核到什么程度、有什么限定 —— 直接答。
   ★ 纯静态:反查表随站一起发布,不需要后端。 */
(function(){{
  const u=new URLSearchParams(location.search).get('url');
  if(!u) return;
  const key=u.trim().replace(/\/$/,'');
  const no=(BYURL[key]||BYURL[u.trim()]||'');
  const box=document.getElementById('urlHit');
  if(!no){{
    box.className='hit none';
    box.innerHTML='<b>这一条不在库里</b><br>我们的 '+__N__+' 条里没有核过这个出处。<br>'
      +'★「没核过」不等于「不可信」—— 只说明我们没查过。';
    box.style.display='block'; return;
  }}
  const c=BYNO[no];
  box.className='hit '+(c?c.vc:'ok');
  let h='<b>找到：'+esc(c.head)+'</b>';
  h+='<div class="hl">号 <span class="mono">bg.'+no+'</span> · '+({{ok:'核得住',warn:'有出入，要盯',x:'查不了',u:'没核过'}})[c.vc]
     +(c.qual&&c.qual.length?(' · <span class="q">原文自己写明：'+esc(c.qual.join('、'))+'</span>'):'')+'</div>';
  h+='<a class="go" href="signals/id-'+String(c.id).padStart(4,'0')+'.html">看这条的底细 →</a>';
  box.innerHTML=h; box.style.display='block';
  document.getElementById('q').value='bg.'+no; filt();
}})();
</script></body></html>""".format(
        site=esc(SITE_NAME), n=len(cards), items=''.join(items),
        chips=''.join('<span class="chip" data-c="%s">%s</span>' % (esc(c), esc(c)) for c in cats),
        picks=picks, qchips=qchips,
        ld=jdump({'@context': 'https://schema.org', '@type': 'WebSite',
                  'name': SITE_NAME, 'description': '每条消息标明出处与核验到哪儿',
                  'numberOfItems': len(cards)}))


def main():
    os.makedirs(os.path.join(OUT, 'signals'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'assets', 'og'), exist_ok=True)
    # ★ 公开地址前缀:部署后填自己的域名。现在用占位,部署时替换即可(号不变)。
    base = site_base()
    n = 0
    for c in CARDS:
        open(os.path.join(OUT, 'signals', 'id-%04d.html' % c['id']), 'w', encoding='utf-8').write(
            card_html(c, base))
        n += 1
    byurl = {}
    for c in CARDS:
        if c.get('url'):
            byurl.setdefault(c['url'], c['no'])
    html = index_html(CARDS, base, byurl)
    html = html.replace('__BYURL__', json.dumps(byurl, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__BYNO__', json.dumps({c['no']: c for c in CARDS}, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__N__', str(len(CARDS)))
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
    # 免码直达:任何 ?no=bg.xxx 都会被首页的 JS 认出来并跳到那一条
    print('✓ 已生成 %d 张卡 + index.html → %s' % (n, OUT))
    print('  ★ 部署:把 site/ 整个目录传到任意静态托管(GitHub Pages / Cloudflare Pages / 自己的服务器)')
    print('  ★ 设 SITE_BASE 环境变量可把绝对地址(share/canonical/og)换成你的域名')


if __name__ == '__main__':
    main()
