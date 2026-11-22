#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 给站点的 217 条真卡,真核一遍,并给每一条算号。

跑法: python3 eval3/seed_cards.py            # 抓(有缓存)
      python3 eval3/seed_cards.py --refresh

输入:线上 https://<站>/data/signals.js（今天的冻结快照,217 条）
输出:
  eval3/seed_cache.json      每条的抓取结果缓存
  eval3/seed_cards.json      每条:号 + 核验状态 + 哪些数对不上 + 分享图文件名

★ 为什么要自己核一遍:站点的 stamp=ok 是「有出处」,不是「核过」。
  母公司自己统计过:212 张 ✓ 卡里 29 条(15.4%)被自己判为转述失真。
  ⇒ 种子必须是【真核得住的】,不能是 stamp=ok 的。

★ 核验状态只有四态,和站点要加的 vc 一致:
  ok   —— 抓到出处正文,且每个数字都找得到
  warn —— 抓到出处正文,但有数字找不到（要盯）
  x    —— 没抓到正文（查不了）
  u    —— 没有链接(从来没被查过)
"""
import json, os, re, sys, time, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_source import fetch

SITE = 'https://ai-subject-universe.app.workbuddy.host'
# ★ 站点必须带 sharecode 才能访问(不带就是 403「链接不完整」)
#   ⇒ 分享图里的二维码必须带上它,否则扫过去是死链
SC = os.environ.get('SITE_SHARECODE', 'LA4PX3544L')
SUF = ('?sharecode=' + SC) if SC else ''
SIG = os.path.join(HERE, 'seed_cache.json')
OUT = os.path.join(HERE, 'seed_cards.json')
RULESET = 'guard-2026.11.11'


def fnv(s):
    h = 2166136261
    for b in s.encode('utf-8'):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


# ★ 限定词的【唯一实现】—— 分享图、免码站、livepage 页全部从这里读,不再各自重算。
#   (之前三处各算一遍,口径可能不一致;今天已经被咬过一次。)
# ★ 2026-11-22 增补:校准集从 138 条扩到 270 条(上游 11-22 出了 28 条新料)。
#   新增两类漏检,都在 #263「Anthropic 数学家称与 Claude 证明黎曼猜想」上暴露:
#     「个人声明」= 非机构来源的单一自证  → 归入「单一来源」
#     「待…核验」 = 明说还没被任何人核过  → 归入「未经同行评议」
#   两条规则在全部 270 条真出处上【各只命中 #263 一条、零误标】才加进来 —— 不是拍脑袋加词。
QUALIFIERS = [
    ('团队自报', r'自报|厂商自|官方口径|官方称|自述|自称[^。；]{0,8}(第一|最|领先|唯一|最多|最大|最好|首个|首次)|据[^。；]{0,8}(方|团队|公司)(称|表示)'),
    ('未经同行评议', r'未(经)?(同行评议|peer)|预印本|preprint|待[^。；]{0,6}(核验|验证|复现)'),
    ('无独立复测', r'无独立复测|无独立(复现|验证|复核)|未见独立|尚无独立|无第三方|无独立审计'),
    ('单一来源', r'仅(有|见)[^。；]{0,10}(来源|印证|报道|出处)|单一来源|唯一来源|尚无其他[^。；]{0,8}(印证|报道|来源)|未获[^。；]{0,6}印证|个人(声明|宣称|通报)|自行(宣布|声明)'),
    ('口径不一致', r'两口径|口径分列|口径不一|口径差异|统计口径[^。；]{0,10}不同|约合\s*[\d$€£¥]|折合\s*[\d$€£¥]|(?<=\d)\s*(?:≠|!=|~=|≈)\s*(?=\d)'),
]


def qual_of(nums, src):
    blob = ' '.join([(n.get('d') or '') for n in (nums or [])]) + ' ' + (src or '')
    return [k for k, p in QUALIFIERS if re.search(p, blob)]


def no_for(head, quote):
    return '%08x' % fnv(head + '\x00' + quote + '\x00' + RULESET)


def norm_values(text):
    SC = {'亿': 1e8, '万': 1e4, '千': 1e3}
    SE = {'thousand': 1e3, 'k': 1e3, 'million': 1e6, 'm': 1e6,
          'billion': 1e9, 'bn': 1e9, 'b': 1e9, 'trillion': 1e12}
    o = set(); x = re.sub(r',', '', str(text or ''))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(thousand|million|billion|trillion|bn|[kmb])\b', x, re.I):
        o.add(float(m.group(1)) * SE.get(m.group(2).lower(), 1))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*([亿万千])', x):
        o.add(float(m.group(1)) * SC[m.group(2)])
    for m in re.finditer(r'\d+(?:\.\d+)?', x):
        o.add(float(m.group(0)))
    return o


def numcore(s):
    m = re.search(r'-?[0-9]+(?:\.[0-9]+)?', str(s).replace(',', '').replace('％', '%'))
    return m.group(0) if m else None


def main():
    refresh = '--refresh' in sys.argv
    import urllib.request
    raw = urllib.request.urlopen(SITE + '/data/signals.js' + SUF, timeout=30).read().decode('utf-8', 'ignore')
    data = json.loads(re.search(r'=\s*(\{.*\});?\s*$', raw, re.S).group(1))
    items = data['items']
    meta = data['meta']
    print('═══ 种子卡核验（%d 条 · 快照 %s）═══' % (len(items), meta.get('built_at')))

    try:
        cache = json.load(open(SIG, encoding='utf-8'))
    except Exception:
        cache = {}

    todo = [it for it in items if it.get('u')]
    need = [it for it in todo if refresh or str(it['id']) not in cache]
    print('有链接 %d 条 · 需抓取 %d 条' % (len(todo), len(need)))

    def get(it):
        r = fetch(it['u'], use_browser=True)
        r.pop('final_url', None)
        r['fetched_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        return str(it['id']), r

    if need:
        with cf.ThreadPoolExecutor(6) as ex:
            for k, v in ex.map(get, need):
                cache[k] = v
        json.dump(cache, open(SIG, 'w', encoding='utf-8'), ensure_ascii=False)
        print('缓存已写 %s' % SIG)

    cards = []
    from collections import Counter
    cnt = Counter()
    for it in items:
        iid = str(it['id'])
        head = (it.get('h') or '').strip()
        quote = (it.get('q') or '').strip()
        no = no_for(head, quote)
        r = cache.get(iid, {})
        status = 'u'
        detail = '没有链接（从来没被查过）'
        bad = []
        n_tot = 0
        if it.get('u'):
            st = r.get('status', 'timeout')
            if st == 'ok':
                src = norm_values(r.get('text', ''))
                nums = [n['n'] for n in (it.get('n') or [])]
                n_tot = len(nums)
                miss = []
                for nm in nums:
                    core = numcore(nm)
                    if core is None:
                        continue
                    v = float(core)
                    for suf, mul in (('亿', 1e8), ('万', 1e4), ('千', 1e3)):
                        if nm.replace(' ', '').startswith(core + suf):
                            v *= mul
                            break
                    else:
                        mm = re.search(r'(thousand|million|billion|trillion|bn)', str(nm), re.I)
                        if mm:
                            v *= {'thousand': 1e3, 'k': 1e3, 'million': 1e6, 'm': 1e6,
                                  'billion': 1e9, 'bn': 1e9, 'trillion': 1e12}[mm.group(1).lower()]
                    if not any(abs(sv - v) <= 1e-6 * max(1.0, abs(v)) for sv in src):
                        miss.append(nm)
                if miss:
                    status, bad = 'warn', miss
                    detail = '抓到出处正文，但 %d 个数字没找到' % len(miss)
                else:
                    status = 'ok'
                    detail = '抓到出处正文，每个数字都找得到'
            else:
                status = 'x'
                detail = {'stub': '只抓到空壳页（正文没拿到）', 'blocked': '被反爬挡了（403）',
                          'timeout': '没抓到（超时/网络不通）'}.get(st, st)
        cnt[status] += 1
        cards.append({
            'id': it['id'], 'no': no, 'url': it.get('u'), 'head': head, 'quote': quote,
            'tag': it.get('tg', ''), 'cat': it.get('c', ''), 'stamp': it.get('s', ''),
            'stamp_text': it.get('st', ''), 'src': it.get('src', ''),
            'key': it.get('k', ''), 'nums': it.get('n') or [],
            'vc': status, 'vc_detail': detail, 'bad': bad, 'n_total': n_tot,
            'qual': qual_of(it.get('n') or [], it.get('src') or ''),
            'site_url': (SITE + '/signals/id-%04d.html' % it['id'] + SUF) if it.get('u') else '',
        })

    json.dump({'built_at': meta.get('built_at'), 'n': len(cards), 'cards': cards},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n【四态分布】')
    for k, v in cnt.most_common():
        print('  %-4s %d 条' % (k, v))
    okc = [c for c in cards if c['vc'] == 'ok']
    print('\n★ 核得住的种子（vc=ok）: %d 条' % len(okc))
    for c in okc[:12]:
        print('  %-4d %-9s %s' % (c['id'], c['no'], (c['head'] or '')[:46]))
    print('\n已写 %s' % OUT)


if __name__ == '__main__':
    main()
