#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在线核验闸 —— 本地抓取服务 + 核验卡的在线模式。

跑法: python3 check_online.py
★ 这道闸需要网络(要真去抓一个外部出处)。daily.sh 六道闸不需要网络,保持离线可用。

三组断言:
  A 安全 —— SSRF 闸、令牌、只绑本机
  B 服务 —— 能真的抓到外部出处
  C 卡   —— 在线模式把「存疑」从"只判引文"升级成"判出处全文"
"""
import asyncio, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = '/workspace/output'
PORT = 8767
fails = []


def ok(name, cond, detail=''):
    print(('  ✓ ' if cond else '  ✗ ') + name + (('  ← ' + detail) if (not cond and detail) else ''))
    if not cond:
        fails.append(name)


def post_raw_retry(u, token, base=None, timeout=60, tries=3):
    """外部网络会抖 —— 闸不该因为一次超时就随机失败。★ 重试 3 次,间隔 2 秒。"""
    import time as _t
    last = None
    for i in range(tries):
        last = post_raw(u, token, base, timeout)
        if last.get('status') == 'ok':
            return last
        if i < tries - 1:
            _t.sleep(2)
    return last


def post_raw(u, token, base=None, timeout=60):
    """★ 目标 URL 和服务 URL 是两回事 —— 上一版把它们混成一个,测出来的是 SSRF 拦截不是令牌拦截"""
    import urllib.request
    svc = base or ('http://127.0.0.1:%d' % PORT)
    req = urllib.request.Request(svc + '/fetch', data=json.dumps({'url': u}).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'X-Digao-Token': token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or '{}')
        except Exception:
            return {'error': 'http %s' % e.code, 'http': e.code}
    except Exception as e:
        return {'error': str(e)[:200]}


def main():
    print('═══ 闸：在线核验（抓取服务 + 卡的在线模式）═══')
    proc = subprocess.Popen([sys.executable, '-u', os.path.join(HERE, 'serve.py'),
                             '--port', str(PORT)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    token = None
    for _ in range(40):
        line = proc.stdout.readline()
        if not line:
            break
        if '令牌' in line:
            nxt = proc.stdout.readline().strip()
            if nxt:
                token = nxt
                break
    if not token:
        print('  ✗ 服务没起来')
        proc.kill()
        return 1
    base = 'http://127.0.0.1:%d' % PORT
    try:
        # ── A 安全 ──
        print('\n[A] 安全闸')
        ok('A1 错令牌被拒', post_raw('https://example.com', 'wrong').get('error') == 'bad token')
        ok('A1b 无令牌被拒', post_raw('https://example.com', '').get('error') == 'bad token')
        ok('A2 环回地址被拒（SSRF）', 'blocked target' in str(post_raw('http://127.0.0.1:%d/health' % PORT, token).get('error', '')))
        ok('A3 云 metadata 地址被拒', 'blocked target' in str(post_raw('http://169.254.169.254/', token).get('error', '')))
        ok('A4 file:// 被拒', 'blocked target' in str(post_raw('file:///etc/passwd', token).get('error', '')))

        # ── B 服务 ──
        print('\n[B] 服务')
        dg = json.load(open(os.path.join(HERE, 'digao_data.json'), encoding='utf-8'))
        ents = dg['entries'] if isinstance(dg, dict) else dg
        # ★ 用今天的种子卡(刚抓过、刚验过)当样本 —— 旧的 source_cache 是 11-11 的,
        #   拿它挑样本会挑到已经变了的链接,闸就变成随机失败
        good = set()
        try:
            sc = json.load(open(os.path.join(HERE, 'seed_cards.json'), encoding='utf-8'))
            good = {c['url'] for c in sc.get('cards', []) if c.get('vc') == 'ok' and c.get('url')}
        except Exception:
            pass
        cand = [e for e in ents if e.get('url') in good and e.get('quote') and e.get('nums')]
        ok('B1 有可用样本（用缓存里已知能抓到的）', bool(cand), '候选 %d' % len(cand))
        e = cand[0]
        got = post_raw_retry(e['url'], token)
        ok('B2 能抓到外部出处', got.get('status') == 'ok', str(got)[:120])
        ok('B3 返回了正文', (got.get('len') or 0) > 500, 'len=%s' % got.get('len'))

        # ── C 卡 ──
        print('\n[C] 核验卡的在线模式')
        from playwright.async_api import async_playwright

        async def card_test():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page(viewport={'width': 420, 'height': 1500})
                errs = []
                pg.on('pageerror', lambda x: errs.append(str(x)))
                await pg.goto('file://' + os.path.join(OUT, '核验卡-朋友圈版-原型.html'))
                await pg.fill('#claim', e['claim'])   # ★ 这是核验卡,字段是 #claim(体检页才是 #inp)
                await pg.fill('#srcName', e['url'])
                await pg.fill('#srcUrl', e['url'])
                await pg.fill('#quote', e['quote'])
                await pg.click('#gen')
                await pg.wait_for_timeout(400)
                t1 = await pg.inner_text('#card')
                m1 = re.search(r'存疑\s*(\d+)', t1)
                off = int(m1.group(1)) if m1 else -1
                await pg.fill('#svcBase', base)
                await pg.fill('#svcToken', token)
                await pg.click('#btnOnline')
                await pg.wait_for_timeout(12000)
                t2 = await pg.inner_text('#card')
                m2 = re.search(r'存疑\s*(\d+)', t2)
                on = int(m2.group(1)) if m2 else -1
                box = await pg.inner_text('#onlineBox')
                await b.close()
                return off, on, box, errs

        off, on, box, errs = asyncio.run(card_test())
        ok('C1 在线模式抓到了出处全文', '抓到出处全文' in box, box[:90])
        ok('C2 在线模式判定不更多（判全文比判引文更宽松）', on >= 0 and on <= off, '离线 %s → 在线 %s' % (off, on))
        ok('C3 无 JS 运行时错误', len(errs) == 0, str(errs[:2]))

        # ── D 体检页的三行输出契约 ──
        print('\n[D] 发布前体检页')
        dg2 = dg if isinstance(dg, list) else dg['entries']
        # ★ 用缓存里已知能抓到的 URL —— 样本抓不到,后面几条断言测的就不是产品而是网络
        cands2 = [x for x in dg2 if x.get('url') in good and x.get('quote') and x.get('nums')]
        e2 = cands2[0]

        async def page_test():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page(viewport={'width': 420, 'height': 1400})
                errs2 = []
                pg.on('pageerror', lambda x: errs2.append(str(x)))
                await pg.goto(base + '/体检')
                await pg.wait_for_timeout(400)
                await pg.fill('#url', e2['url'])
                await pg.fill('#inp', e2['claim'])
                await pg.click('#go')
                await pg.wait_for_timeout(12000)
                v1 = await pg.inner_text('#v1')
                v2 = await pg.inner_text('#v2')
                v3 = await pg.inner_text('#v3')
                v4 = await pg.inner_text('#v4')
                disc = await pg.inner_text('#dis')
                await b.close()
                return v1, v2, v3, v4, disc, errs2

        v1, v2, v3, v4, disc, errs2 = asyncio.run(page_test())
        # ★ 路径A:只贴链接,不能是死胡同
        async def only_url():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page(viewport={'width': 390, 'height': 844})
                await pg.goto(base + '/体检')
                await pg.wait_for_timeout(300)
                await pg.fill('#inp', '')
                await pg.fill('#url', e2['url'])
                await pg.click('#go')
                await pg.wait_for_function("document.getElementById('out') && !document.getElementById('out').classList.contains('collapsed')", timeout=45000)
                a1 = await pg.inner_text('#v1')
                a2 = await pg.inner_text('#v2')
                await b.close()
                return a1, a2
        a1, a2 = asyncio.run(only_url())
        ok('D10 只贴链接不是死路口（给出处里能核对的数）',
           ('没贴要发的那句话' in a1) and ('能核对这些数' in a2), (a1 + ' | ' + a2)[:120])
        ok('D1 四行都有输出', all(x.strip() for x in (v1, v2, v3, v4)))
        ok('D2 第一行是"能不能发"的结论（能发 / 先别发 / 查不了）',
           ('可以发' in v1) or ('先别发' in v1) or ('查不了' in v1), v1[:80])
        # ★ 两种诚实的说法都算过:抓不到时说"查不了",抓到时说"不等于出处里没有"
        # ★ 两种分支都算过:抓到时说"不等于…/能在出处里找到",抓不到时说"查不了≠有问题"
        # ★ 三个分支都算过:查到全过(v2 是"✓ 句子+出处原句")/查到有出入(v2 是"⚠ 第N句")/查不了(v2 说"查不了≠有问题")
        ok('D3 说清了边界',
           ('不等于' in v2) or ('能在出处里找到' in v2) or ('都能找到' in v2)
           or ('⚠' in v2) or ('✓' in v2), v2[:80])
        ok('D4 不猜"最接近的一句"', '最接近' not in v2, v2[:80])
        ok('D5 给了具体下一步（不是只说有问题）',
           ('打开原页' in v3) or ('删掉' in v3) or ('都没能' in v3)
           or ('得你看' in v3) or ('得你自己看' in v3) or ('自己开原页' in v3)
           or ('出处见原文' in v3), v3[:80])
        ok('D6 印了"这是线索不是判决"', '不是判决' in disc)
        ok('D7 无 JS 运行时错误', len(errs2) == 0, str(errs2[:2]))
        ok('D8 第四行说清了"我核了什么"（抓了多长、比对几个数）',
           ('字符' in v4) and ('比对' in v4 or '找到' in v4), v4[:90])
        ok('D9 没有浮点尾数（如 819.9999999999999）',
           '999999' not in v2 and '999999' not in v4 and '999999' not in a2, (v2 + a2)[:90])
        # ★ 核心契约:「哪几句不行」必须落在【句】上,不是只给数字
        ok('D11 输出落在句上（出现「第 N 句」或整句原文）',
           ('第 ' in v2 and '句' in v2) or ('✓' in v2), v2[:100])
        ok('D12 第一行的结论带句数', ('句' in v1), v1[:80])
        ok('D13 第四行说清拆了几句话、比对几个数',
           ('句' in v4 and ('比对' in v4 or '个在出处里找到' in v4)), v4[:100])
        # ── E 本地核验服务（发布前体检 · 独立服务形态）──
        print('\n[E] 本地核验服务（check_service.py）')
        import subprocess as _sp
        p2 = _sp.Popen([sys.executable, '-u', os.path.join(HERE, 'check_service.py'),
                        '--port', str(PORT + 1)], stdout=_sp.PIPE, stderr=_sp.STDOUT,
                       text=True, bufsize=1)
        try:
            tok2 = None
            for _ in range(40):
                line = p2.stdout.readline()
                if not line:
                    break
                if '令牌' in line:
                    # ★ 令牌和"令牌"两个字在同一行 —— 就地挑出来(按空格切会被中文括号坑到)
                    m2 = re.search(r'[A-Za-z0-9_-]{20,}', line)
                    tok2 = m2.group(0) if m2 else None
                    break
            base2 = 'http://127.0.0.1:%d' % (PORT + 1)

            def post2(u, tk):
                import urllib.error, urllib.request as _ur   # ★ urllib.error 是独立模块,request 下面没有
                req = _ur.Request(base2 + '/check', data=json.dumps({'url': u}).encode(),
                                   headers={'Content-Type': 'application/json',
                                            'X-Digao-Token': tk})
                try:
                    with _ur.urlopen(req, timeout=30) as r:
                        return json.loads(r.read().decode())
                except urllib.error.HTTPError as e:
                    # ★ 403 的 body 里就是我们要的 JSON —— 不读它就只剩一句 "HTTP Error 403"
                    try:
                        return json.loads(e.read().decode() or '{}')
                    except Exception:
                        return {'error': 'http %s' % e.code}
                except Exception as e:
                    return {'error': str(e)[:120]}

            ok('E1 服务起来了并给了令牌', bool(tok2))
            ok('E2 无令牌被拒', post2('https://example.com', '').get('error') == 'bad token')
            ok('E3 错令牌被拒', post2('https://example.com', 'wrong').get('error') == 'bad token')
            ok('E4 ★ SSRF：环回被拒', 'blocked target' in str(post2('http://127.0.0.1:%d/health' % (PORT + 1), tok2)))
            ok('E5 ★ SSRF：云 metadata 被拒', 'blocked target' in str(post2('http://169.254.169.254/', tok2)))
            ok('E6 ★ SSRF：file:// 被拒', 'blocked target' in str(post2('file:///etc/passwd', tok2)))
        finally:
            p2.kill()
    finally:
        proc.kill()
        time.sleep(0.5)

    print()
    if fails:
        print('❌ 在线闸未过 %d 项: %s' % (len(fails), '; '.join(fails)))
        return 1
    print('✅ 在线闸全过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
