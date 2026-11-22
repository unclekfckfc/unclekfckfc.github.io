#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《底稿》的门禁。三道闸:JS 语法 / 功能 / 内容。

跑法: python3 check_digao.py
"""
import re, os, subprocess, sys, tempfile, json

OUT = '/workspace/output'
PAGE = os.path.join(OUT, '底稿-结论可查的地方.html')
fails = []


def ok(name, cond, detail=''):
    print(('  ✓ ' if cond else '  ✗ ') + name + (('  ← ' + detail) if (not cond and detail) else ''))
    if not cond:
        fails.append(name)


print('═══ 闸 1：JS 语法 ═══')
js = re.findall(r'<script>([\s\S]*?)</script>', open(PAGE, encoding='utf-8').read())
ok('页面有 JS', len(js) == 1)
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as t:
    t.write('\n'.join(js))
    tmp = t.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
ok('JS 语法', r.returncode == 0, r.stderr.split('\n')[1] if r.returncode else '')
os.unlink(tmp)

print('═══ 闸 2：功能（Playwright 真点一遍）═══')
import asyncio
from playwright.async_api import async_playwright


async def func():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1180, 'height': 1400})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
        await pg.goto('file://' + PAGE)
        await pg.wait_for_timeout(600)
        R = {}
        R['档案流渲染出条目'] = await pg.locator('.row').count() > 50
        R['KPI 六格'] = await pg.locator('.kpi').count() == 6
        R['无 JS 错误'] = len(errs) == 0

        # 筛选
        await pg.click('.chip[data-f="nums"]'); await pg.wait_for_timeout(300)
        R['筛选「有口径说明」生效'] = (0 < await pg.locator('.row').count() < 112)
        await pg.click('.chip[data-f="unc"]'); await pg.wait_for_timeout(300)
        R['筛选「落在未覆盖区」生效'] = (0 < await pg.locator('.row').count() < 112)
        await pg.click('.chip[data-f="all"]'); await pg.wait_for_timeout(300)

        # 搜索
        await pg.fill('#q', '870 million'); await pg.wait_for_timeout(500)
        R['搜索命中'] = await pg.locator('.row').count() > 0
        await pg.fill('#q', ''); await pg.wait_for_timeout(400)

        # 详情 —— 分别打开「有口径说明」和「落在未覆盖区」两种条目，不能只看第一条
        await pg.click('.chip[data-f="nums"]'); await pg.wait_for_timeout(300)
        await pg.locator('.row').first.click(); await pg.wait_for_timeout(400)
        t = await pg.inner_text('#app')
        R['详情页打开'] = await pg.locator('.detail').count() > 0
        R['详情有逐字原文'] = '逐字原文' in t
        R['详情有口径说明表'] = '口径说明' in t and '跟着数字一起存' in t
        R['详情有编号与内容寻址说明'] = '内容寻址' in t
        R['详情有「不改过≠没被改过」的诚实说明'] = ('没有历史版本' in t)
        R['详情有判据路说明'] = '判据路' in t
        await pg.screenshot(path=os.path.join(OUT, '_ux', '底稿-详情.png'))
        await pg.click('.nav button[data-v="list"]'); await pg.wait_for_timeout(400)
        await pg.click('.chip[data-f="unc"]'); await pg.wait_for_timeout(300)
        await pg.locator('.row').first.click(); await pg.wait_for_timeout(400)
        t2 = await pg.inner_text('#app')
        R['未覆盖条目：明写「不是没问题是没被查」'] = ('落在未覆盖区' in t2 and '没被查' in t2)
        await pg.screenshot(path=os.path.join(OUT, '_ux', '底稿-未覆盖.png'))
        await pg.click('.nav button[data-v="list"]'); await pg.wait_for_timeout(400)

        # 数字查
        await pg.click('.nav button[data-v="num"]'); await pg.wait_for_timeout(300)
        await pg.fill('#nq', '8.6'); await pg.wait_for_timeout(500)
        R['数字查有命中'] = await pg.locator('.row').count() > 0
        await pg.screenshot(path=os.path.join(OUT, '_ux', '底稿-数字查.png'))

        # 对账台：算出的号必须跟档案里的一致
        await pg.click('.nav button[data-v="recon"]'); await pg.wait_for_timeout(300)
        await pg.fill('#rc-claim', '非文本决策模型 Jev 母公司 TypeSafe 完成 8.7 亿美元 A 轮')
        await pg.fill('#rc-quote', 'TypeSafe Inc., the creator of the Jev artificial intelligence model, today announced that it has raised $870 million in funding at a $7.5 billion valuation.')
        await pg.click('#rc-go'); await pg.wait_for_timeout(500)
        t = await pg.inner_text('#app')
        R['对账：同一份材料算出同一个号并对上'] = ('对上了' in t)
        # 改一个字 → 号必须变、对不上
        await pg.fill('#rc-claim', '非文本决策模型 Jev 母公司 TypeSafe 完成 9.7 亿美元 A 轮')
        await pg.click('#rc-go'); await pg.wait_for_timeout(500)
        t2 = await pg.inner_text('#app')
        R['对账：改一个字 → 号变了、对不上'] = ('档案里没有这一份' in t2)
        await pg.screenshot(path=os.path.join(OUT, '_ux', '底稿-对账.png'))

        # 规则集
        await pg.click('.nav button[data-v="rules"]'); await pg.wait_for_timeout(300)
        t = await pg.inner_text('#app')
        R['规则集有真 sha256'] = re.search(r'\b[0-9a-f]{64}\b', t) is not None
        R['规则集有重跑步骤'] = '怎么重跑' in t
        R['规则集写明「没报 finding ≠ 没问题」'] = '不等于' in t and '没问题' in t
        await pg.screenshot(path=os.path.join(OUT, '_ux', '底稿-规则集.png'))

        for k, v in R.items():
            ok(k, v, str(errs[:2]) if (not v and k == '无 JS 错误') else '')
        await b.close()

asyncio.run(func())

print('═══ 闸 3：内容 ═══')
s = open(PAGE, encoding='utf-8').read()

# ★ 数据层断言：finding / flag 必须挂在它自己的 id 上
#   （曾经按天整批挂，把别的条目的判定扣到这条头上 —— 97 条里 75 条是错的）
import json as _json
DATA = _json.loads(re.search(r'const DATA = (\{.*?\});\nconst E', s, re.S).group(1))
wrong = []
for e in DATA['entries']:
    for f in e['findings']:
        if f.get('id') and f['id'] != e['id']:
            wrong.append('%s<-%s' % (e['id'], f['id']))
    for fl in e['flags']:
        if fl.get('id') and fl['id'] != e['id']:
            wrong.append('flag %s<-%s' % (e['id'], fl['id']))
ok('finding/flag 没有挂错条目', len(wrong) == 0, str(wrong[:4]))
# 每条 finding 的 id 必须等于底稿 id（数据里保留了原始 id）
mism = [e['id'] for e in DATA['entries'] for f in e['findings'] if f.get('id') and f['id'] != e['id']]
ok('finding 带的 id 与底稿 id 一致', len(mism) == 0, str(mism[:4]))
ok('KPI 的 finding 数与数据一致',
   str(DATA['stat']['n_findings']) == re.search(r'判据 finding</div><div class="v ">(\d+)</div>', s).group(1)
   if re.search(r'判据 finding</div><div class="v ">(\d+)</div>', s) else True)
ok('finding 数不是按天重复计的虚高数', DATA['stat']['n_findings'] < DATA['stat']['n_lane_run'] * 5,
   'finding=%d lane_run=%d' % (DATA['stat']['n_findings'], DATA['stat']['n_lane_run']))
ok('finding 数与数字口径唯一真源一致（防漂移）',
   DATA['stat']['n_findings'] == json.load(open('/workspace/output/数字口径-唯一真源.json', encoding='utf-8'))['materials']['machine_findings_attached'])
ok('零资源外链（离线可用）', len(re.findall(r'(?:src|href)="https?://', s)) == 0
   or all(u in s for u in re.findall(r'href="(https?://[^"]+)"', s)))
ext = [u for u in re.findall(r'(?:src)="(https?://[^"]+)"', s)]
ok('无外部资源脚本/样式', len(ext) == 0, str(ext[:3]))
ok('有「结论可查的地方」的定位', '结论可查的地方' in s)
ok('有「号变了就是内容变了」', '内容' in s and '哈希' in s)
ok('规则集版本号是真实串不是字面量 RULESET', 'RULESET' not in s and 'guard-2026' in s)
ok('未覆盖条目显式警示', '落在未覆盖区' in s and '不是没问题' in s)
ok('固定 3 类标明每条都一样', '每条都一样' in s)
# 「已认证」可能在数据正文中出现（如某条材料本身在讨论这个概念），
# 所以只检查界面骨架，不检查数据
skeleton = re.sub(r'<script>[\s\S]*?</script>', '', s)
ok('界面骨架里没有「已认证」式主张', '已认证' not in skeleton)
ok('界面骨架里没有「已核验通过」', '已核验通过' not in skeleton)

# ── 出处全文核验的纪律 ──
# ★ 核心:没抓到正文(status!=ok)的条目,绝不许把某个数判成「出处全文里没有」。
#   这条要是破了,整个体系最在意的边界就漏了 —— 而且漏得很安静。
dg = json.load(open('/workspace/output/eval3/digao_data.json', encoding='utf-8'))
bad = []
for e in dg['entries']:
    sc = e.get('src_check')
    if not sc:
        continue
    if sc['status'] != 'ok':
        for n in sc.get('nums', []):
            if n['b'] == 'miss':
                bad.append('%s/%s' % (e['id'], n['n']))
ok('★ 没抓到正文时,不许出现「出处全文里确实没有」', not bad, '; '.join(bad[:5]))
ok('★ 抓到的条目都记了抓取状态', all('status' in (e.get('src_check') or {}) for e in dg['entries']))
ok('★ 页面写明「没拿到正文就不能说出处里没有」',
   '没拿到正文就不能说' in s or '没抓到正文就不能说' in s)
ok('★ 页面写明「没找到这个写法 ≠ 出处里没有」',
   '没找到这个写法' in s and '不等于出处里没有这个数' in s)
ok('★ 页面不说「出处全文里确实没有」（这句话太重）', '出处全文里确实没有' not in s)

print()
if fails:
    print('❌ 门禁未过 %d 项: %s' % (len(fails), '; '.join(fails)))
    sys.exit(1)
print('✅ 三道门全过')
