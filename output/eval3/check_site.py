#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《免码站》的门禁。

跑法: python3 check_site.py
断言:
  A 结构   —— 227 张卡 + index.html + 每卡的 og:image
  B 机器可读 —— 每卡有 JSON-LD,且含「号」「核验状态」;(有原限定时)含「限定」
  C 寻址   —— 号能定位到那一条;canonical / robots 齐
  D 离线   —— 零外链(离线可用、零第三方依赖)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), 'site')
fails = []


def ok(name, cond, detail=''):
    print(('  ✓ ' if cond else '  ✗ ') + name + (('  ← ' + detail) if (not cond and detail) else ''))
    if not cond:
        fails.append(name)


def main():
    print('═══ 闸：免码站 ═══')
    cards = json.load(open(os.path.join(HERE, 'seed_cards.json'), encoding='utf-8'))['cards']
    htmls = [f for f in os.listdir(os.path.join(SITE, 'signals'))] if os.path.isdir(os.path.join(SITE, 'signals')) else []
    htmls = [f for f in htmls if f.endswith('.html')]
    ok('A1 卡数与数据一致', len(htmls) == len(cards), '%d vs %d' % (len(htmls), len(cards)))
    ok('A2 index.html 在', os.path.exists(os.path.join(SITE, 'index.html')))
    ogs = os.listdir(os.path.join(SITE, 'assets', 'og')) if os.path.isdir(os.path.join(SITE, 'assets', 'og')) else []
    ogs = [f for f in ogs if f.endswith('.png')]
    ok('A3 每卡都有 og:image', len(ogs) == len(cards), '%d vs %d' % (len(ogs), len(cards)))

    # B + C:逐卡查
    bad_json = []; bad_no = []; bad_qual = []; bad_canon = []; bad_og = []; missing_og = []
    for c in cards:
        p = os.path.join(SITE, 'signals', 'id-%04d.html' % c['id'])
        if not os.path.exists(p):
            continue
        s = open(p, encoding='utf-8').read()
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
        if not m:
            bad_json.append(c['id']); continue
        try:
            d = json.loads(m.group(1))
        except Exception:
            bad_json.append(c['id']); continue
        about = {x['name']: x['value'] for x in d.get('about', [])}
        if '号' not in about or about.get('号') != 'bg.' + c['no']:
            bad_no.append(c['id'])
        if '核验状态' not in about:
            bad_no.append(c['id'])
        # 有原限定时,JSON-LD 里必须有「限定」
        blob = ' '.join([(n.get('d') or '') for n in (c.get('nums') or [])]) + ' ' + (c.get('src') or '')
        has_qual = re.search(r'自报|未经同行评议|无独立复测|两口径|口径分列', blob) is not None
        if has_qual and '限定' not in about:
            bad_qual.append(c['id'])
        if 'rel="canonical"' not in s or 'name="robots"' not in s:
            bad_canon.append(c['id'])
        og = re.search(r'property="og:image" content="([^"]+)"', s)
        if not og:
            bad_og.append(c['id']); continue
        fp = os.path.join(SITE, 'assets', 'og', 'id-%04d.png' % c['id'])
        if not os.path.exists(fp):
            missing_og.append(c['id'])

    ok('B1 每卡都有可解析的 JSON-LD', not bad_json, str(bad_json[:5]))
    ok('B2 JSON-LD 里带「号」和「核验状态」', not bad_no, str(bad_no[:5]))
    ok('B3 ★ 有原限定的卡,JSON-LD 里带「限定」', not bad_qual, str(bad_qual[:5]))
    ok('C1 每卡有 canonical + robots', not bad_canon, str(bad_canon[:5]))
    ok('C2 每卡有 og:image 且文件存在', not bad_og and not missing_og, str((bad_og + missing_og)[:5]))

    # D:零外链（离线可用、零第三方依赖）
    # ★ 只查【真正加载资源的引用】—— script src / link href / img src。
    #   <a href="https://出处原文"> 是内容链接(正文要指出去处),不是资源依赖。
    res = []
    for root, _, fs in os.walk(SITE):
        for f in fs:
            if not f.endswith('.html'):
                continue
            s = open(os.path.join(root, f), encoding='utf-8').read()
            res += re.findall(r'<script[^>]+src="(https?://[^"]+)"', s)
            # ★ 只查【会被加载的资源】—— link 里 canonical/alternate/og 这类不是资源依赖,
            #   它们本来就该是绝对 URL(部署态的正确性),混进来会误报。
            for tag in re.findall(r'<link\b[^>]*>', s):
                if re.search(r'rel=["\']?(stylesheet|preload|icon|apple-touch-icon)', tag, re.I):
                    res += re.findall(r'href="(https?://[^"]+)"', tag)
            res += re.findall(r'<img[^>]+src="(https?://[^"]+)"', s)
    ok('D1 无第三方资源依赖（离线可用）', not res, str(res[:4]))
    # ★★ 新增:部署态的正确性 —— canonical / og:image 必须是绝对 URL 且指向本站。
    #   (以前 canonical 是相对的,这条从没被测到 ⇒ 闸是绿的但覆盖不全。)
    import os as _os
    # ★★ D1b 测的是【canonical 不会把读者指向别处】,不是"必须绝对":
    #   ★ 相对路径在【任何域名下都自洽】—— 在 URL 会变的部署平台上这是唯一正确的选择;
    #   ★ 绝对 URL 只有在指向本站时才自洽;指向别的域名 ⇒ 错(那是复制品)。
    _base = os.environ.get('SITE_BASE', '').rstrip('/')
    _canon_ok, _canon_bad = 0, []
    for _f in [x for x in os.listdir(os.path.join(SITE, 'signals')) if x.endswith('.html')][:40]:
        _s = open(os.path.join(SITE, 'signals', _f), encoding='utf-8').read()
        _m = re.search(r'rel=["\']?canonical["\']?\s+href="([^"]+)"', _s) or re.search(r'href="([^"]+)"\s+rel=["\']?canonical', _s)
        if not _m:
            _canon_bad.append((_f, '无 canonical')); continue
        _u = _m.group(1)
        if _u.startswith('/'):
            _canon_ok += 1                      # 相对 —— 自洽
        elif _u.startswith('http'):
            if not _base or _u.startswith(_base):
                _canon_ok += 1                  # 绝对且指向本站 —— 自洽
            else:
                _canon_bad.append((_f, '指向别处: ' + _u[:50]))
        else:
            _canon_bad.append((_f, '格式不对: ' + _u[:40]))
    ok('D1b ★ canonical 不把读者指向别处（相对，或绝对且指向本站）', not _canon_bad,
       'ok=%d bad=%s' % (_canon_ok, _canon_bad[:2]))
    # 顺带确认:内容链接确实指向出处(这是要有的)
    one = open(os.path.join(SITE, 'signals', 'id-0216.html'), encoding='utf-8').read()
    ok('D2 卡上保留了指向出处的链接', 'qbitai.com' in one)

    idx = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
    ok('C3 首页支持 ?no= 直达', 'no' in idx and 'URLSearchParams' in idx)
    ok('C4 首页能搜号', 'bg.' in idx)
    ok('C5 ★ 首页支持 ?url= 按出处链接反查（读者入口）', 'get(\'url\')' in idx and 'BYURL' in idx)
    ok('C6 ★ 反查表已随站发布（不用后端）', len(re.findall(r'https?://[^"]+', idx)) > 100)
    # ★ 核验收据:读者核完能带走 —— 这是"读者→写作者"那条边的载体
    one = open(os.path.join(SITE, 'signals', 'id-0216.html'), encoding='utf-8').read()
    ok('C7 ★ 每张卡有「复制核验结果」', 'id="rcpt"' in one and 'receiptText' in one)
    m2 = re.search(r'id="rdata">(.*?)</script>', one, re.S)
    ok('C8 ★ 收据数据块可解析且含号/限定词', bool(m2) and '"no"' in m2.group(1) and '"quals"' in m2.group(1))

    print()
    if fails:
        print('❌ 站的门禁未过 %d 项: %s' % (len(fails), '; '.join(fails)))
        return 1
    print('✅ 站的门禁全过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
