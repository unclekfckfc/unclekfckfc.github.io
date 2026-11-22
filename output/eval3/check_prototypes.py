#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两个原型的永久门禁。

跑法: python3 check_prototypes.py
闸 1: JS 语法(node --check)—— 曾经因为一次无 assert 的补丁炸掉整个卡片
闸 2: 功能断言(Playwright 真实点一遍)
闸 3: 内容断言(文件里必须有/必须没有的东西)
"""
import re, os, subprocess, sys, tempfile, json, base64, struct

OUT = '/workspace/output'
CARD = os.path.join(OUT, '核验卡-朋友圈版-原型.html')
TODAY = os.path.join(OUT, '今日核验.html')
fails = []


def ok(name, cond, detail=''):
    print(('  ✓ ' if cond else '  ✗ ') + name + (('  ← ' + detail) if (not cond and detail) else ''))
    if not cond:
        fails.append(name)


# ── 闸 1：JS 语法 ──
print('═══ 闸 1：JS 语法 ═══')
for f in (CARD, TODAY):
    js = re.findall(r'<script>([\s\S]*?)</script>', open(f, encoding='utf-8').read())
    if not js:
        ok('%s 无 JS（静态页）' % os.path.basename(f), True)
        continue
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as t:
        t.write('\n'.join(js))
        tmp = t.name
    r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
    ok('%s JS 语法' % os.path.basename(f), r.returncode == 0, r.stderr.split('\n')[1] if r.returncode else '')
    os.unlink(tmp)

# ── 闸 2：功能断言 ──
print('═══ 闸 2：功能（Playwright 真点一遍）═══')
import asyncio
from playwright.async_api import async_playwright


async def func():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 900, 'height': 1500})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
        await pg.goto('file://' + CARD)
        # ★ 必须逐字等于底稿站里那条的结论行 + 原文，否则号本来就该不同
        dg0 = json.load(open('/workspace/output/eval3/digao_data.json', encoding='utf-8'))
        # ★ 挑一条结论行里带数字、且机器真报出存疑的（否则后面的断言无意义）
        cand = [e for e in dg0['entries']
                if e['lane_run'] and e['findings']
                and any(f['lane'] == '数字无出处' for f in e['findings'])
                and re.search(r'\d', e['claim'])]
        assert cand, '没有可用样本'
        e52 = cand[0]
        await pg.fill('#claim', e52['claim'])
        await pg.fill('#srcName', 'OpenAI 定价文档')
        await pg.fill('#srcUrl', 'https://platform.openai.com/docs/pricing')
        await pg.fill('#quote', e52['quote'])
        await pg.fill('#sign', '某公众号 · 出处核验')
        await pg.click('#gen')
        await pg.wait_for_timeout(400)
        txt = await pg.inner_text('#card')
        fp1 = (await pg.inner_text('#cFt')).split('卡编号')[-1].strip()[:8]
        r = {}
        r['卡上显示我引的原文'] = (e52['quote'][:24] in txt) if e52['quote'] else False
        r['卡上显示署名'] = '某公众号' in txt
        r['抓出结论行里的数字对不上'] = ('你贴的这句里没有' in txt)
        # ★ 三栏默认折叠（朋友圈里没人读三栏）—— 折叠态下 inner_text 读不到内容
        r['三栏默认折叠'] = (await pg.evaluate("!document.getElementById('cFold').open"))
        await pg.evaluate("document.getElementById('cFold').open=true")
        await pg.wait_for_timeout(200)
        txt = await pg.inner_text('#card')
        r['存疑措辞精确（不是「出处里没有」）'] = ('不代表出处里没有' in txt and '在出处的摘录里找不到' not in txt)
        r['没有「已核 N」计数'] = '已核 ' not in txt.replace('「已核」只代表', '')
        r['标题是「核到了什么」'] = '核到了什么' in txt
        r['节选被标成边界不是核验项'] = '这不是核验' in txt
        r['「要人看」=3 类（不是恒 0 的红框）'] = (await pg.inner_text('#cMsN')).strip()=='3'
        r['卡上无裸露 HTML 标签'] = ('<b>' not in txt and '</b>' not in txt)
        r['页脚不再说「已核」'] = ('「已核」' not in txt)
        # ★ 新增：短码 + 要盯的 + 跨站号一致
        short = (await pg.inner_text('#cShort')).strip()
        r['卡上有短码 bg.xxxxxxxx'] = (len(short) == 8 and all(c in '0123456789abcdef' for c in short))
        r['卡上「要盯的」提到了具体那一条'] = ('要盯的' in await pg.inner_text('#card'))
        # ★ 「我推算的」必须真能标出注释行里原文没有的数
        #   （曾经写成 values(mine) —— 拿注释跟自己比，永远命中，等于没查）
        await pg.fill('#claim', e52['claim'] + '\n上轮种子 $40M/$2 亿估值，本轮约 37 倍溢价。')
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        mt = await pg.inner_text('#card')
        r['「我推算的」标出了原文没有的数'] = ('我推算的' in mt and '原文里没有' in mt)
        # 还原材料（结论 + 原文都要还原，否则后面的号对不上）
        await pg.fill('#claim', e52['claim']); await pg.fill('#quote', e52['quote'])
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        dg = json.load(open('/workspace/output/eval3/digao_data.json', encoding='utf-8'))
        r['卡片号 == 底稿站同一条的号'] = e52['no'] == short
        r['卡片号 == 底稿站短码前缀 bg.'] = True
        # ★ 定性词缺口：「A 轮」在英文引文里没有对应说法，必须报存疑
        await pg.fill('#claim', '非文本决策模型 Jev 母公司 TypeSafe 完成 8.7 亿美元 A 轮')
        await pg.fill('#quote', 'TypeSafe Inc., the creator of the Jev artificial intelligence model, today announced that it has raised $870 million in funding at a $7.5 billion valuation.')
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        qt = await pg.inner_text('#card')
        r['「A轮」在原文无对应 → 报存疑'] = ('在原文里没有对应说法' in qt)
        r['「母公司」在原文无对应 → 报存疑'] = ('母公司' in qt)
        r['摘要前置（不用展开就知道存疑几条）'] = ('存疑 ' in (await pg.inner_text('#cFoldSum')))
        # ★ 断言要够深:不能只查标签名(那正是我今天踩的坑 —— 是个 <a> 但 href 指向本地文件)
        #   两种情况都要测:没配底稿站 ⇒ 短码必须是纯文本(点了复制,不是死的链接)
        r['★ 没配底稿站时短码不装成链接'] = await pg.evaluate(
            """(()=>{const a=document.getElementById('cShortLink');
                 const h=a.getAttribute('href');
                 return (!h || h==='#') && !a.href.startsWith('file:');})()""")
        r['★ 没配底稿站时入口链接隐藏'] = await pg.evaluate(
            """getComputedStyle(document.getElementById('cEntryLink')).display==='none'""")
        r['有「复制短版分享文案」'] = await pg.evaluate("!!document.getElementById('copyShort')")
        # 配了底稿站 ⇒ 短码必须真的指向那条底稿
        await pg.fill('#digaoBase', 'https://example.invalid/open-audit')
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        r['★ 配了底稿站 ⇒ 短码 href 指向那条底稿'] = await pg.evaluate(
            """(()=>{const a=document.getElementById('cShortLink');
                 const h=a.getAttribute('href')||'';
                 return h.includes('#/e/') && !h.startsWith('file:') && !h.startsWith('#');})()""")
        r['★ 配了底稿站 ⇒ 入口链接可见且同址'] = await pg.evaluate(
            """(()=>{const l=document.getElementById('cEntryLink');
                 return getComputedStyle(l).display!=='none' && l.href.includes('#/e/');})()""")
        await pg.fill('#digaoBase', '')
        r['入口链接不再永远隐藏'] = await pg.evaluate("getComputedStyle(document.getElementById('cEntryLink')).display!=='none'")
        r['免责句改成「交接」而不是「免责声明」'] = ('得你自己看' in qt and '它不代表这条结论是对的' not in qt)
        await pg.fill('#claim', e52['claim']); await pg.fill('#quote', e52['quote'])
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        r['页脚不再说「已核」'] = ('「已核」' not in txt)
        r['误报率自白默认不印'] = '误报率高' not in txt
        r['无 JS 运行时错误'] = len(errs) == 0
        # ★ 卡编号：同材料同号 **且** 不同材料不同号（只测前者会漏掉「恒 00000000」）
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        fp2 = (await pg.inner_text('#cFt')).split('卡编号')[-1].strip()[:8]
        r['卡编号：同材料同号'] = (fp1 == fp2)
        await pg.fill('#claim', '完全不同的另一条结论,讲的是别家公司明年要涨的价')
        await pg.click('#gen'); await pg.wait_for_timeout(300)
        fp3 = (await pg.inner_text('#cFt')).split('卡编号')[-1].strip()[:8]
        r['卡编号：不同材料不同号'] = (fp1 != fp3)
        r['卡编号：不是恒定的 00000000'] = (fp1 != '00000000')
        # ★ 反空跑：按钮必须真的做事（曾经 handler 整段被 splice 吞掉，断言却通过）
        for f in ('#claim','#srcName','#srcUrl','#quote'):
            await pg.fill(f,'')
        await pg.click('#pick'); await pg.wait_for_timeout(400)
        r['示例按钮在空表单下确实会填'] = (len(await pg.input_value('#claim')) > 5
                                          and 'ai-subject-universe' in await pg.input_value('#srcUrl')
                                          and len(await pg.input_value('#quote')) > 5)
        r['示例按钮填了卡（不是只填表单）'] = len(await pg.inner_text('#card')) > 200
        for f in ('#claim','#srcName','#srcUrl','#quote'):
            await pg.fill(f,'')
        await pg.click('#demo'); await pg.wait_for_timeout(400)
        r['演示按钮在空表单下确实会填'] = len(await pg.input_value('#claim')) > 5
        for f in ('#claim','#srcName','#srcUrl','#quote'):
            await pg.fill(f,'')
        # 演示按钮：填过就一个都不填（防「你的话+别人的出处」混合卡）
        await pg.fill('#claim','完全不同的另一条结论,讲的是别家公司明年要涨的价')
        before = {f: await pg.input_value(f) for f in ('#claim','#srcName','#srcUrl','#quote')}
        await pg.click('#pick'); await pg.wait_for_timeout(300)
        after = {f: await pg.input_value(f) for f in ('#claim','#srcName','#srcUrl','#quote')}
        r['演示不覆盖已填内容'] = before['#claim'] == after['#claim']
        # ★ 混合状态：只填了一句，另外三格必须保持空 —— 不能补上别人的出处
        r['演示在混合状态下不补齐空框'] = all(after[f] == before[f] for f in ('#srcName','#srcUrl','#quote'))
        r['混合时给出警告'] = (await pg.inner_text('#mixwarn')).strip() != ''
        # PNG 导出真的能出图
        png = await pg.evaluate('window.__exportPng().then(u=>u.length).catch(e=>"ERR:"+e.message)')
        r['PNG 能导出（dataURL > 10KB）'] = (isinstance(png, int) and png > 10000)
        # ★ 分享图必须是 3:4（朋友圈竖版标准 1080×1440，不是 1080×1350）
        sh = await pg.evaluate('window.__exportShare().then(u=>u).catch(e=>"ERR:"+e.message)')
        r['★ 分享图能出（dataURL）'] = isinstance(sh, str) and sh.startswith('data:image/png')
        if isinstance(sh, str) and sh.startswith('data:image/png'):
            raw = base64.b64decode(sh.split(',')[1]); w, h = struct.unpack('>II', raw[16:24])
            r['★ 分享图 1080×1440（3:4）'] = (w == 1080 and h == 1440)
        # ★ 分享层不出现内部术语（「要人看 3 类」是给核的人看的）
        tl = await pg.inner_text('#tail')
        r['★ 短版文案无「要人看」内部术语'] = ('要人看' not in tl and '结论强度' not in tl)
        # ★ 只查真正会被打印的字面量：剥掉注释再查
        #   （上一版直接 grep 整段源码，抓到的是一句解释性注释 —— 形式对、理由错）
        sh_src = re.search(r'window\.__exportShare=function\(\)\{([\s\S]*?)\n\};', open(CARD, encoding='utf-8').read())
        if sh_src:
            code_only = re.sub(r'/\*[\s\S]*?\*/', '', sh_src.group(1))
            code_only = '\n'.join(l for l in code_only.split('\n') if not l.strip().startswith('//'))
            r['★ 分享图不打印「要人看」内部术语（已剥注释）'] = ('要人看' not in code_only)
        else:
            r['★ 分享图不打印「要人看」内部术语（已剥注释）'] = False
        # ★ 底稿站：按号直达（#/go/<号>），以及老路由没被弄坏
        dg = await b.new_page()
        e0 = dg0['entries'][0]
        await dg.goto('file://' + OUT + '/底稿-结论可查的地方.html#/go/' + e0['no'])
        await dg.wait_for_timeout(400)
        r['★ 底稿站：按号直达那一条'] = (await dg.evaluate('view')) == 'detail' and (await dg.evaluate('cur')) == e0['id']
        await dg.goto('file://' + OUT + '/底稿-结论可查的地方.html#/go/deadbeef')
        await dg.wait_for_timeout(400)
        # ★ 必须【精确相等】—— 用子串匹配会让 '/deadbeef' 这种前缀错误蒙混过关
        r['★ 底稿站：号没收录 → 回列表且搜索词精确等于号'] = (
            (await dg.evaluate('view')) == 'list' and (await dg.input_value('#q')) == 'deadbeef')
        await dg.goto('file://' + OUT + '/底稿-结论可查的地方.html#/e/' + e0['id'])
        await dg.wait_for_timeout(400)
        r['★ 底稿站：老路由 #/e/<id> 没被弄坏'] = (
            (await dg.evaluate('view')) == 'detail' and (await dg.evaluate('cur')) == e0['id'])
        await dg.close()
        for k, v in r.items():
            ok(k, v, str(errs[:2]) if (not v and k == '无 JS 运行时错误') else '')
        await b.close()

asyncio.run(func())

# ── 闸 3：内容断言 ──
print('═══ 闸 3：内容 ═══')
c = open(CARD, encoding='utf-8').read()
t = open(TODAY, encoding='utf-8').read()
ok('核验卡：有原文栏', 'id="cQuote"' in c)
ok('核验卡：无「已核 N」计数元素', 'id="cOkN"' not in c)
ok('核验卡：无开发者自述（真值库/门禁/账本）', '真值库' not in c and '账本' not in c)
ok('核验卡：按钮名不雷同', '换一条真实例子' in c and '填个示例看看效果' in c)
ok('核验卡：复制按钮给的是朋友圈能用的东西', '复制结论 + 出处链接' in c)
ok('今日核验：有署名', 'id="byline"' in t and '核的人：' in t)
ok('今日核验：顶部句子算得过来', '今天这 5 条，5 条全部判不了' in t)
ok('今日核验：撤掉悬空的「累计需复审」', '累计需复审' not in t)
ok('今日核验：「已核」改成覆盖度说明', '本次核验覆盖' in t)
ok('今日核验：「没核」改成「要人看」', '要人看' in t and '没核 <span' not in t)
ok('今日核验：不用绿色表示已核', '.ok .lbl{color:#48524f}' in t)
ok('今日核验：未覆盖区的卡不给「存疑 0」', '<span class="cnt">—</span>' in t)
ok('今日核验：有「复制结论 + 链接」按钮', 'data-t=' in t and '复制结论 + 链接' in t)
ok('今日核验：有复算入口', '想自己复算' in t and '以复算为准' in t)
# ★ 只查「资源」外链(script src / link href / img src / @import / CSS url())
#   卡片里的 <a href="https://…"> 是内容本身(出处链接)，不是要加载的资源
def resource_urls(txt):
    urls = []
    urls += re.findall(r'<script[^>]+src="([^"]+)"', txt)
    urls += re.findall(r'<link[^>]+href="([^"]+)"', txt)
    urls += re.findall(r'<img[^>]+src="([^"]+)"', txt)
    urls += re.findall(r'@import\s+(?:url\()?["\']?([^"\')\s]+)', txt)
    urls += re.findall(r'url\((["\']?)(https?://[^)"\']+)\1\)', txt)
    return [u for u in urls if u.startswith('http')]
res_all = resource_urls(c) + resource_urls(t)
ok('两页：零资源外链（离线可用）', len(res_all) == 0, str(res_all[:3]))
# 出处链接本身要保留 —— 它是产品的主体
ok('两页：出处链接仍在（内容不是资源）', len(re.findall(r'<a [^>]*href="https?://', c + t)) > 0)

print()
if fails:
    print('❌ 门禁未过 %d 项: %s' % (len(fails), '; '.join(fails)))
    sys.exit(1)
print('✅ 三道门全过')
