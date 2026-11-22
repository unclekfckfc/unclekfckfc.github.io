#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二维码端到端闸。

链条:核验卡 → 导出分享图 PNG → 从 PNG 里扫出二维码 → 拿扫出来的 URL 打开站点 → 落到正确那条。

为什么要这么长?因为二维码最容易坏在【看不见的地方】:
画出来了不代表扫得出来;扫出来了不代表 URL 对;URL 对不代表站点认。
这四步任何一步断了,肉眼都发现不了 —— 只有真跑一遍才知道。

跑法: python3 check_qr.py
依赖: node(已有) + _ux/qr 下的 node_modules(jsQR 解码器 + pngjs)
      缺了就先 cd _ux/qr && npm install --no-audit --no-fund
"""
import asyncio, base64, json, os, subprocess, sys

OUT = '/workspace/output'
QR_DIR = os.path.join(OUT, '_ux', 'qr')
NODE_MODULES = os.path.join(QR_DIR, 'node_modules')
fails = []


def ok(name, cond, detail=''):
    print(('  ✓ ' if cond else '  ✗ ') + name + (('  ← ' + detail) if (not cond and detail) else ''))
    if not cond:
        fails.append(name)


def main():
    print('═══ 闸：二维码端到端（卡 → PNG → 扫码 → 站点）═══')

    # ── 依赖检查：缺了就大声说,不静默跳过 ──
    need = [os.path.join(NODE_MODULES, 'jsqr'), os.path.join(NODE_MODULES, 'pngjs')]
    miss = [n for n in need if not os.path.exists(n)]
    if miss:
        print('  ✗ 缺少解码器依赖 %s' % ', '.join(os.path.basename(m) for m in miss))
        print('     先跑: cd %s && npm install --no-audit --no-fund' % QR_DIR)
        return 1

    # ── 挑一条真材料 ──
    dg = json.load(open(os.path.join(OUT, 'eval3', 'digao_data.json'), encoding='utf-8'))
    cand = [e for e in dg['entries'] if e['lane_run'] and e['findings'] and e['url']]
    assert cand, '没有可用样本'
    e = cand[0]
    base = 'https://ai-subject-universe.app.workbuddy.host'

    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={'width': 390, 'height': 844})
            errs = []
            pg.on('pageerror', lambda x: errs.append(str(x)))
            await pg.goto('file://' + os.path.join(OUT, '核验卡-朋友圈版-原型.html'))
            for f, v in (('#claim', e['claim']), ('#srcName', e['url']),
                         ('#srcUrl', e['url']), ('#quote', e['quote'])):
                await pg.fill(f, v)
            await pg.fill('#digaoBase', base)
            await pg.click('#gen')
            await pg.wait_for_timeout(400)
            ok('生成卡无 JS 报错', len(errs) == 0, str(errs[:2]))
            ok('卡上二维码可见（配了底稿站地址）',
               await pg.evaluate("getComputedStyle(document.getElementById('cQr')).display") == 'block')
            # 没配地址 ⇒ 不该有二维码（没地址就没链接可编）
            await pg.fill('#digaoBase', '')
            await pg.click('#gen')
            await pg.wait_for_timeout(300)
            ok('没配底稿站地址 ⇒ 卡上二维码隐藏',
               await pg.evaluate("getComputedStyle(document.getElementById('cQr')).display") == 'none')
            # 配回去,导图
            await pg.fill('#digaoBase', base)
            await pg.click('#gen')
            await pg.wait_for_timeout(300)
            u = await pg.evaluate('window.__exportShare()')
            png_path = os.path.join(OUT, '_ux', '分享图-朋友圈.png')
            open(png_path, 'wb').write(base64.b64decode(u.split(',')[1]))
            await b.close()
            return png_path

    png_path = asyncio.run(run())

    # ── 从导出的 PNG 里扫 ──
    r = subprocess.run(['node', os.path.join(QR_DIR, 'e2e.js'), png_path],
                       capture_output=True, text=True, cwd=QR_DIR)
    scanned = ''
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if ':' in line and 'http' in line:
                scanned = line.split(':', 1)[1].strip()
    ok('★ 从导出的 PNG 里能扫出二维码（独立解码器 jsQR）', bool(scanned), r.stdout.strip() + r.stderr.strip()[:200])
    ok('★ 扫出来的 URL 编的是 ?no=<号>（query 参数抗重定向）',
       ('?no=' + e['no']) in scanned, scanned)
    ok('★ 扫出来的号与卡上那条一致', e['no'] in scanned, scanned)

    # ── 拿扫出来的 URL 打开站点,看落到对不对那条 ──
    if scanned:
        from playwright.async_api import async_playwright
        local = scanned.replace(base + '/', 'file://' + os.path.join(OUT, '底稿-结论可查的地方.html'))

        async def open_site():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page()
                await pg.goto(local)
                await pg.wait_for_timeout(700)
                v = await pg.evaluate('view')
                c = await pg.evaluate('cur')
                await b.close()
                return v, c

        v, c = asyncio.run(open_site())
        ok('★ 拿扫出来的 URL 打开站点 ⇒ 落到正确那一条',
           (v == 'detail' and c == e['id']), 'view=%s cur=%s（应为 detail / %s）' % (v, c, e['id']))

    print()
    if fails:
        print('❌ 二维码闸未过 %d 项: %s' % (len(fails), '; '.join(fails)))
        return 1
    print('✅ 二维码闸全过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
