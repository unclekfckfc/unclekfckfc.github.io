#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《今日核验》单页 —— 用交接包的真实 7 天编年史数据。

形态说明:朋友圈是「消费」场所,不是「生产」场所。
所以这一页不是流水线,是流水线的【输出物】—— 一天一条,可截图、可分享。
"""
import json, os, re, html as H

B = '/workspace/tmpwork/h2b/handoff-2026-11-02'
D = os.path.join(B, '10-skills', 'claim-audit', 'data', 'daily')
OUT = '/workspace/output/今日核验.html'

# ── 分析逻辑(与 transcription-guard 同源,朋友圈版简化) ──
SCALE_CN = {'亿': 1e8, '万': 1e4, '千': 1e3}
SCALE_EN = {'thousand': 1e3, 'k': 1e3, 'million': 1e6, 'm': 1e6,
            'billion': 1e9, 'bn': 1e9, 'b': 1e9}
ALNUM = re.compile(r'[^\W_]', re.U)

def values(t):
    o = set(); x = str(t or '').replace(',', '')
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(thousand|million|billion|trillion|bn|[kmb])\b', x, re.I):
        o.add(float(m.group(1)) * SCALE_EN.get(m.group(2).lower(), 1))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*([亿万千])', x):
        o.add(float(m.group(1)) * SCALE_CN[m.group(2)])
    for m in re.finditer(r'\d+(?:\.\d+)?', x):
        o.add(float(m.group(0)))
    return o

def toks(t):
    o = set()
    for m in re.finditer(r'[A-Za-z][A-Za-z0-9]{1,}', t or ''):
        w = m.group(0).lower(); o.add(w)
        st = re.sub(r'\d+$', '', w)          # ★ 专名尾号连写 vs 分开
        if len(st) >= 3 and st != w: o.add(st)
    return o

def grams(t, n=2):
    g = set()
    for r in re.findall(r'[一-鿿]+', t or ''):
        for i in range(len(r) - n + 1): g.add(r[i:i + n])
    return g

def analyze(claim, quote):
    ok, wn, ms = [], [], []
    ov = values(quote)
    for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)\s*(%|％|倍|万|亿)?', claim or ''):
        raw, unit = m.group(1), m.group(2) or ''
        a, b = m.start(1), m.end(1)
        if len(raw) < 2 and not unit: continue
        if raw in ('10', '100', '2024', '2025', '2026', '2027'): continue
        if re.search(r'[A-Za-z]', claim[a:b]): continue
        if re.search(r'\d{4}-\d{1,2}-\d{1,2}\s*$', claim[:a]) or re.search(r'\d{1,2}-\d{1,2}\s*$', claim[:a]): continue
        if claim.strip().endswith(('？', '?', '吗', '吧')): continue
        v = float(raw.replace(',', '')) * SCALE_CN.get(unit, 1)
        if not any(abs(v - k) <= 1e-6 * max(1, abs(k)) for k in ov):
            # ★ 措辞必须精确：只说明「你贴的这段」没覆盖它，不代表出处里没有
            wn.append('「%s%s」<b>登记的摘录里没有</b> —— 只说明这段摘录没覆盖它，<b>不代表出处里没有</b>（线索，不是结论）' % (raw, unit))
    otxt = str(quote or '').strip()
    complete = bool(re.search(r'[.!?。！？"\'”’)\]】]\s*$', otxt)) and len(otxt) >= 30
    ct, qt = toks(claim), toks(quote)
    cg, qg = grams(claim), grams(quote)
    overlap = any(x in qt for x in ct) or any(x in qg for x in cg)
    if complete and not overlap and (ct or cg) and (qt or qg):
        wn.append('说法跟摘录<b>没有共同的实体词</b> —— 可能是配错了对，不是转述掉档')
    # ★ 「已核」只报真正核到的结论要素；"摘录是节选"是边界，不是核验项
    sh = [x for x in ct if x in qt][:3] or [x for x in cg if x in qg][:3]
    cov = '引文%s，结论要素 %d 项' % ('完整，可逐句比对' if complete else '是节选，只能核到这一段',
                                    len(sh) if complete else 0)
    return ok, wn, cov

# ── 读数据 ──
idx = json.load(open(os.path.join(B, '20-产物', '报告卡与编年史', 'index.json'), encoding='utf-8'))
days = idx['days']
latest = days[-1]['day']
tot_mat = sum(d['n_material'] for d in days)
tot_prob = sum(d['n_problem'] for d in days)
tot_unc = sum(d['n_unclear'] for d in days)
tot_rev = sum(d['n_needs_review'] for d in days)

P = json.load(open(os.path.join(D, latest, 'pairs.json'), encoding='utf-8'))
PAIRS = P.get('pairs', P) if isinstance(P, dict) else P
GT = json.load(open(os.path.join(D, latest, 'gt_scope.json'), encoding='utf-8'))
GTU = {x['id']: x.get('desc', '') for x in GT.get('unclear', [])}
GTF = {x['id']: x.get('desc', '') for x in GT.get('findings', [])}
FLAGS = json.load(open(os.path.join(D, latest, 'lanes', 'flags.json'), encoding='utf-8'))
FLAGGED = {}
for f in (FLAGS if isinstance(FLAGS, list) else [FLAGS]):
    for it in f.get('items', []):
        FLAGGED.setdefault(it['id'], []).append(('线索 · ' + f.get('flag', '').split('·')[-1].strip(), it.get('claim', '')))
# ★ 判据路 N/S/T 也要并进「存疑」—— 卡必须显示真实流水线跑出来的结果，不是我重算的
for ln, lname in (('N', '数字无出处'), ('S', '限定与口径'), ('T', '主体与术语')):
    j = json.load(open(os.path.join(D, latest, 'lanes', ln + '.json'), encoding='utf-8'))
    for it in j.get('findings', []):
        FLAGGED.setdefault(it.get('id'), []).append(
            ('判据 · ' + lname, it.get('claim') or it.get('reason') or it.get('quote', '')))
UNC = json.load(open(os.path.join(D, latest, 'lanes', 'uncovered.json'), encoding='utf-8'))
UNCV = set(UNC.get('uncovered', []))
ruleset = days[-1]['ruleset']; msha = days[-1]['material_sha256']

def esc(s): return H.escape(str(s or ''))

# 署名与站点（页面上必须写清"谁在说话"）
A_BY  = '「核材料」编辑部'
A_SITE = '有出处站'

# 今日判不了的条数（从今日这批里数，不跟 7 天累计混）
def _is_unc(i):
    return (i in GTU) or (i in UNCV) or any(i in [x.get('id') for x in FLAGGED.get(k, [])] for k in [])
today_unc = sum(1 for p in PAIRS if (p['id'] in GTU) or (p['id'] in UNCV))
print('今日 %d 条: 判不了 %d 条' % (len(PAIRS), today_unc))

# ── 卡片 ──
def card_html(p):
    i = p['id']
    claim = (p.get('transmitted') or '').split('\n')
    title = claim[0]; comment = claim[1] if len(claim) > 1 else ''
    quote = p.get('original') or ''
    # ★ 只核结论行 —— 评论行是作者自己的判断，拿它比引文必然全红
    ok, wn, cov = analyze(title, quote)
    # ★ 真实流水线的命中优先（它才是权威）
    real = FLAGGED.get(i, [])
    if real:
        seen, ded = set(), []
        for lbl, clm in real:
            k = re.sub(r'\s+', '', lbl + clm)[:60]
            if k in seen: continue
            seen.add(k); ded.append('<b>' + esc(lbl) + '</b>：' + esc(clm))
        wn = ded + wn
    # ★ 再做一次全局去重：判据路和机械路常对同一处各报一次
    seen2, wn2 = set(), []
    for x in wn:
        k = re.sub(r'<[^>]+>', '', x); k = re.sub(r'\s+', '', k)[:60]
        if k in seen2: continue
        seen2.add(k); wn2.append(x)
    wn = wn2
    extra = []
    if i in GTU:
        extra.append('人工复核判为<b>引文盖不住</b>：' + esc(GTU[i].split('｜')[0])[:150])
    if i in GTF:
        extra.append('人工复核判为<b>真问题</b>：' + esc(GTF[i].split('｜')[0])[:150])
    uncovered = i in UNCV
    if uncovered:
        extra.append('本条<b>落在未覆盖区</b> —— 机器路没看它，所以下面的「存疑」不能读成"没问题"')
    # ★ 这三项是「要人看」的待办 = 机器的能力边界，不是异常 → 给数字，但不用红色
    FIXED = ''
    ms = ['结论比证据强多少 —— 要人判',
          '适用范围有没有被放大（地域/人群/榜单/时间窗）',
          '有没有把两件并列的事说成因果']
    fp = hashlib_fp = '%08x' % (abs(hash((i + quote + ruleset))) & 0xffffffff)
    lis = lambda arr: ''.join('<li>%s</li>' % x for x in arr) or '<li class="hint" style="list-style:none;margin-left:-1.1em">（无）</li>'
    wn_cnt = '—' if uncovered else str(len(wn))
    wn_hint = '机器路没看这条' if uncovered else ''
    # ★ 复制按钮：朋友圈真正能用的只有「结论 + 链接」
    copy_txt = esc(title + ('\n\n' + comment if comment else '') +
                   ('\n\n出处：' + str(p.get('url')) if p.get('url') else ''))
    return f'''<div class="card" id="card-{esc(i)}">
 <div class="hd"><div class="kicker">核验卡 · {esc(i)}</div><div class="claim">{esc(title)}</div>
  <div class="hdact"><button class="cp" data-t="{copy_txt}">复制结论 + 链接</button></div></div>
 <div class="src">出处 <b>原始链接</b> <a href="{esc(p.get('url'))}" target="_blank" rel="noopener">{esc(p.get('url') or '（无链接）')}</a></div>
 <div class="q"><b>登记的逐字摘录</b><br><span class="qm">{esc(quote)}</span></div>
 {'<div class="cm"><b>本站评论</b><br>'+esc(comment)+'</div>' if comment else ''}
 <div class="sect ok"><div class="lbl">本次核验覆盖</div><ul><li>{cov}</li></ul></div>
 {'<div class="sect unc"><div class="lbl">机器没看这条</div><ul><li>本条<b>落在未覆盖区</b> —— 下面「存疑」不能读成"没问题"</li></ul></div>' if uncovered else ''}
 <div class="sect wn"><div class="lbl">存疑 <span class="cnt">{wn_cnt}</span>{('　'+wn_hint) if wn_hint else ''}</div><ul>{lis(wn)}</ul></div>
 <div class="sect ms"><div class="lbl">要人看 <span class="cnt">{len(ms)+len(extra)}</span> 类</div><ul>{lis(ms+extra)}</ul>
  <div class="fixednote">这 {len(ms)} 类<b>每张卡都一样</b> —— 是这台机器原理上核不了的,不是这条结论的扣分项。</div></div>
 <div class="disclaimer">「核到了什么」只代表逐字比对过 —— <b>它不代表这条结论是对的</b>。对不对要人判。</div>
 <div class="ft">卡编号 <b>{fp}</b> · 规则集 <b>{ruleset}</b> · 材料 <b>{msha}</b></div>
</div>'''

cards = ''.join(card_html(p) for p in PAIRS)

# 编年史
chron = []
for d in days:
    cls = 'hot' if d['n_problem'] else ('mid' if d['n_unclear'] else 'calm')
    chron.append(f'''<div class="day {cls}"><div class="dd">{d['day'][5:]}</div>
 <div class="dm">材 {d['n_material']} · 问 <b>{d['n_problem']}</b> · 判不了 {d['n_unclear']}</div>
 <div class="dg">{d['gate_verdict']}</div></div>''')
chron = ''.join(chron)

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#eceeec;color:#14181a;
 font:14.5px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
#top{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.95);backdrop-filter:blur(8px);
 border-bottom:1px solid #e3e7e5;padding:12px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
#top h1{font-family:Georgia,"Songti SC",serif;font-size:18px;font-weight:400;margin:0}
.tag{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.1em;color:#8b938f;border:1px solid #e3e7e5;padding:2px 8px;border-radius:4px}
#wrap{max-width:820px;margin:0 auto;padding:22px 20px 80px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0 26px}
@media(max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#fff;border:1px solid #e3e7e5;border-radius:9px;padding:12px 14px}
.kpi .lb{font-size:11.5px;color:#8b938f}
.kpi .v{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;font-size:25px;font-weight:600;margin-top:2px}
.kpi .v.warn{color:#a8630a}.kpi .v.risk{color:#a8323f}.kpi .v.ok{color:#0a7d5e}
h2{font-size:16px;margin:30px 0 12px;display:flex;align-items:center;gap:9px}
.dot{width:7px;height:7px;border-radius:50%;background:#0a7d5e}
.card{background:#fff;border:1px solid #e3e7e5;border-radius:13px;overflow:hidden;margin-bottom:16px}
.card .hd{padding:16px 20px 13px;border-bottom:1px solid #e3e7e5;background:#fbfcfb}
.card .kicker{font-family:ui-monospace,Menlo,monospace;font-size:9.5px;letter-spacing:.15em;color:#8b938f;margin-bottom:7px}
.card .claim{font-size:18px;line-height:1.5;font-weight:600}
.card .src{padding:10px 20px;background:#f6f8f7;border-bottom:1px solid #e3e7e5;font-size:12.5px}
.card .src a{color:#0a7d5e;text-decoration:none;word-break:break-all}
.card .q,.card .cm{padding:11px 20px;border-bottom:1px solid #e3e7e5;font-size:13px;color:#48524f}
.card .q b,.card .cm b{color:#14181a;font-size:11.5px;letter-spacing:.05em}
.card .qm{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#48524f;line-height:1.6}
.card .sect{padding:12px 20px;border-bottom:1px solid #e3e7e5}
.card .sect:last-of-type{border-bottom:0}
.card .lbl{font-family:ui-monospace,Menlo,monospace;font-size:9.5px;letter-spacing:.13em;color:#8b938f;margin-bottom:6px;display:flex}
.card .cnt{margin-left:auto;font-size:11px;color:#48524f}
.card ul{margin:0;padding-left:1.15em;font-size:13.2px;line-height:1.7}
.card li{margin:.22em 0}
.card li b{font-weight:600}
.ok .lbl{color:#48524f}.wn .lbl{color:#a8630a}.ms .lbl{color:#8a6a3a}
/* 不用绿色表示「已核」：绿=已认证，这个工具没这个资格。
   不用红色表示「要人看」：那是常态待办，红框写 0 会被读成「没核通过」。 */
.card .ft{padding:12px 20px;background:#fbfcfb;border-top:1px solid #e3e7e5;
 font-family:ui-monospace,Menlo,monospace;font-size:10px;color:#8b938f;line-height:1.85}
.card .ft b{color:#48524f}
.chron{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px}
@media(max-width:700px){.chron{grid-template-columns:repeat(2,1fr)}}
.day{background:#fff;border:1px solid #e3e7e5;border-radius:9px;padding:10px 12px;border-left-width:4px}
.day.calm{border-left-color:#c3cbc7}.day.mid{border-left-color:#a8630a}.day.hot{border-left-color:#a8323f}
.day .dd{font-family:ui-monospace,Menlo,monospace;font-size:13px;font-weight:600}
.day .dm{font-size:11.5px;color:#8b938f;margin-top:3px}
.day .dm b{color:#a8323f}
.day .dg{font-family:ui-monospace,Menlo,monospace;font-size:9.5px;letter-spacing:.12em;color:#0a7d5e;margin-top:5px}
.note{background:#fbf2e4;border:1px solid #e6d4b4;border-radius:10px;padding:13px 16px;font-size:13.2px;color:#6b4306;margin:18px 0}
.note b{color:#5a3705}
#byline{padding:13px 22px;background:#f7f9f8;border-bottom:1px solid #e3e7e5;font-size:13px;color:#48524f;line-height:1.75}
#byline b{color:#14181a}
#byline span{color:#6b7570}
.card .hd{position:relative}
.card .hdact{position:absolute;right:18px;bottom:11px}
.cp{font:12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC",sans-serif;
 color:#0a7d5e;background:#fff;border:1px solid #bfe3d6;border-radius:6px;padding:6px 10px;cursor:pointer}
.cp:hover{background:#eaf5f1}
.cp:focus-visible{outline:2px solid #0a7d5e;outline-offset:2px}
.card .fixednote{margin-top:7px;padding-top:6px;border-top:1px dashed #e3e7e5;
 font-size:11.5px;color:#8b938f;line-height:1.6}
.card .fixednote b{color:#5d6662}
.card .disclaimer{padding:10px 20px;background:#fbf2e4;border-top:1px solid #e6d4b4;
 font-size:12.5px;color:#6b4306;line-height:1.6}
.card .disclaimer b{color:#5a3705}
.card .sect.unc{background:#fdf6ee;border-bottom-color:#f0dfc6}
.card .sect.unc .lbl{color:#a8630a}
footer{margin-top:34px;padding-top:13px;border-top:1px solid #e3e7e5;
 font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:#8b938f;line-height:1.9}
"""

page = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>今日核验 · {latest}</title><style>{CSS}</style></head><body>
<div id="top"><h1>今日核验 · {latest}</h1>
 <span class="tag">每条结论核到什么程度</span>
 <span class="tag" style="margin-left:auto">规则集 {ruleset}</span></div>
<div id="byline">
 <b>「核材料」· 每日出处的核验记录</b><br>
 <span>这一页只回答一个问题：<b>这条说法，我核到哪一步了。</b>它不告诉你结论对不对 —— 那是人判的事。<br>
 核的人：{A_BY}　·　出处的站点：{A_SITE}　·　有异议请把那条的出处链接发回来。</span>
</div>
<div id="wrap">
 <div class="kpis">
  <div class="kpi"><div class="lb">累计材料</div><div class="v">{tot_mat}</div></div>
  <div class="kpi"><div class="lb">判为问题</div><div class="v risk">{tot_prob}</div></div>
  <div class="kpi"><div class="lb">引文盖不住</div><div class="v warn">{tot_unc}</div></div>
  <div class="kpi"><div class="lb">今日判不了</div><div class="v warn">{today_unc}/{len(PAIRS)}</div></div>
  <div class="kpi"><div class="lb">门禁</div><div class="v ok">{sum(1 for d in days if d['gate_verdict']=='PASS')}/{len(days)}</div></div>
 </div>
 <div class="note"><b>7 天累计 {tot_mat} 条材料，其中 {tot_unc} 条机器判不了；今天这 {len(PAIRS)} 条，{today_unc} 条全部判不了。</b>
 逐字摘录只摘了原文的一部分,所以大部分判断机器做不了 —— 这不是它偷懒,是<b>它只会说"我核到哪儿了",不会说"这结论对不对"</b>。
 下面每张卡都把这个边界写在明面上。</div>
 <h2><span class="dot"></span>今日 {len(PAIRS)} 条</h2>
 {cards}
 <h2><span class="dot" style="background:#8b938f"></span>编年史 · {len(days)} 天</h2>
 <div class="chron">{chron}</div>
 <p style="font-size:12.5px;color:#8b938f;margin-top:4px">
 灰=安静(没有判为问题) · 橙=有「引文盖不住」 · 红=有判为问题 · 右下=PASS 是门禁(规则没退化)</p>
 <div class="note" style="background:#eaf5f1;border-color:#bfe3d6;color:#155f4b">
  <b>这一页本身也是一张核验卡。</b>每张卡页脚印着规则集 <b>{ruleset}</b> 和材料 <b>{msha}</b>；
  想自己复算，就拿同一段材料跑同一套规则，对不上的地方以复算为准。
  <b>「没核」那一栏必须一起发</b> —— 一家不敢写这一格的,读者反而不敢信它的「已核」。</div>
 <footer>数据源:「核材料」体系 10-skills/claim-audit/data/daily/{latest}/ 与 20-产物/报告卡与编年史/index.json<br>
 零外链 · 离线可用 · 每条结论一张卡,可截图可分享</footer>
</div>
<script>
document.querySelectorAll('.cp').forEach(function(b){{
  b.addEventListener('click',function(){{
    var t=b.getAttribute('data-t')||'';
    var done=function(){{var o=b.textContent;b.textContent='已复制 ✓';setTimeout(function(){{b.textContent=o}},1400)}};
    if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(done,done)}}
    else{{var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();
      try{{document.execCommand('copy')}}catch(e){{}}document.body.removeChild(ta);done()}}
  }});
}});
</script></body></html>'''

open(OUT, 'w', encoding='utf-8').write(page)
print('已生成 %s (%.1f KB)' % (OUT, os.path.getsize(OUT) / 1024))
print('今日 %s: %d 条卡片 | 累计 %d 材料 / %d 问题 / %d 判不了 / %d 需复审 / 门禁 %d/%d'
      % (latest, len(PAIRS), tot_mat, tot_prob, tot_unc, tot_rev,
         sum(1 for d in days if d['gate_verdict'] == 'PASS'), len(days)))
