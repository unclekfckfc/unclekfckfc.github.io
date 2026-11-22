#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓出处 —— 并且诚实地区分「抓到了没有」。

★ 这条模块存在的唯一理由:把「查不了」和「不成立」分开。

反例(我自己今天踩的):抓到 cfi.net.cn 返回 HTTP 200,但正文只有 1 个字符(空壳页)。
如果照直说「全文里没有 37.15 亿元」,就是在把【没抓到】说成【不存在】——
这正是整个体系反复强调不能犯的错。

所以 fetch() 返回的不是一段文本,是三态:
  ok      —— 确实抓到了正文(有正文长度和段落数兜底)
  stub    —— HTTP 200 但正文是壳/空/只有导航(必须有证据才这么判)
  blocked —— 403/验证码/反爬
  timeout —— 超时/网络不通
  empty   —— 200 但正文长度低于阈值

★ 只有 status==ok 的结果,才允许被引用成「全文里没有」。
"""
import json, re, html, subprocess, sys, os

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# ★ 正文下限:低于这个长度就不能算"抓到了正文"。
#   依据:实测 112 条真材料里,正常新闻页正文 2k~40k;空壳页 1~300 字符。
MIN_TEXT = 1200
MIN_CJK = 200          # 中文章节至少要有这么多汉字


def _tags(x: str) -> str:
    x = re.sub(r'(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>', ' ', x)
    # ★ 块级标签的结束符换成换行 —— 否则 fallback 分支会把整页压成一行,
    #   标题和"Go to Navigation"粘成一句,给出一句没用的"原句"
    x = re.sub(r'(?i)<br\s*/?>|</(p|div|li|h[1-6]|section|article|tr|blockquote)>', '\n', x)
    return html.unescape(re.sub(r'(?s)<[^>]+>', ' ', x))


def strip_html(raw: str) -> str:
    """★ 优先抽 <p>/<article> 里的正文段落。
    原因:直接去标签会把导航栏、页脚、"扫一扫二维码"也留下来 ——
    那些不是正文,却会被"出处里最接近的一句"选中,给出一句废话。"""
    blocks = re.findall(r'(?is)<(p|article|section)[^>]*>(.*?)</\1>', raw)
    paras = [_tags(b[1]) for b in blocks]
    paras = [re.sub(r'\s+', ' ', q).strip() for q in paras]
    paras = [q for q in paras if len(q) >= 12]
    if paras:
        # ★ 用换行连接,不是空格 —— 句子切分靠换行;用空格会把导航和正文粘成一大坨
        joined = '\n'.join(paras)
        if len(joined) >= 800:
            return joined
    raw = re.sub(r'(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>', ' ', raw)
    txt = _tags(raw)
    return re.sub(r'\s+', ' ', txt).strip()


def curl_fetch(url: str, timeout: int = 40):
    """先走 curl —— 快、便宜、够用。返回 (status, text, http_code, final_url)"""
    try:
        r = subprocess.run(
            ['curl', '-sSL', '--max-time', str(timeout), '-A', UA, '-k',
             '-w', '\n###HTTP:%{http_code}\n###URL:%{url_effective}\n###SIZE:%{size_download}',
             url],
            capture_output=True, timeout=timeout + 8)
        out = r.stdout.decode('utf-8', 'ignore')
        parts = out.rsplit('###', 3)
        body = parts[0]
        meta = {}
        for p in parts[1:]:
            if ':' in p:
                k, v = p.split(':', 1)
                meta[k.strip()] = v.strip()
        code = meta.get('HTTP', '000')
        if code == '000':
            return 'timeout', '', code, url
        if code in ('403', '401', '429', '503'):
            return 'blocked', '', code, meta.get('URL', url)
        text = strip_html(body)
        return 'ok' if looks_like_article(text) else 'stub', text, code, meta.get('URL', url)
    except subprocess.TimeoutExpired:
        return 'timeout', '', '000', url
    except Exception:
        return 'timeout', '', '000', url


def looks_like_article(text: str) -> bool:
    """★ 判「这是不是正文」——不能只看 HTTP 200。
    判据两条同时成立:① 文本够长 ② 里有成段的句子(不只是导航词堆在一起)"""
    if len(text) < MIN_TEXT:
        return False
    cjk = len(re.findall(r'[\u4e00-\u9fff]', text))
    if cjk >= MIN_CJK:
        return True
    # 英文页:靠句子的空格结构判断
    words = text.split()
    if len(words) < 250:
        return False
    long_words = sum(1 for w in words if len(w) >= 6)
    return long_words / max(1, len(words)) > 0.12


def playwright_fetch(url: str, timeout_ms: int = 45000):
    """curl 不行时的兜底 —— 浏览器渲染(js 渲染页 / 反爬)。返回同样四元组"""
    try:
        import asyncio
        from playwright.async_api import async_playwright

        async def go():
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page(viewport={'width': 1280, 'height': 900},
                                      user_agent=UA)
                resp = await pg.goto(url, timeout=timeout_ms, wait_until='domcontentloaded')
                code = str(resp.status) if resp else '000'
                if code in ('403', '401', '429', '503'):
                    await b.close()
                    return 'blocked', '', code, url
                txt = await pg.evaluate('document.body ? document.body.innerText : ""')
                await b.close()
                return ('ok' if looks_like_article(txt) else 'stub'), txt or '', code, url
        return asyncio.run(go())
    except Exception:
        return 'timeout', '', '000', url


def fetch(url: str, use_browser: bool = True):
    """★ 主入口:返回 dict,status ∈ {ok, stub, blocked, timeout, empty}"""
    st, txt, code, final = curl_fetch(url)
    if st != 'ok' and use_browser and st in ('stub', 'blocked', 'timeout'):
        st2, txt2, code2, final2 = playwright_fetch(url)
        if st2 == 'ok':
            return {'status': 'ok', 'text': txt2, 'http': code2, 'final_url': final2,
                    'via': 'playwright', 'len': len(txt2)}
        # ★ 浏览器也没拿到,但要保留更"有信息"的那个状态
        if st2 == 'blocked' and st == 'stub':
            st = 'blocked'
        elif st2 == 'timeout' and st == 'stub':
            st = 'timeout'
        return {'status': st, 'text': txt, 'http': code, 'final_url': final,
                'via': 'curl', 'len': len(txt)}
    return {'status': st, 'text': txt, 'http': code, 'final_url': final,
            'via': 'curl', 'len': len(txt)}


# ── 数字判定:三桶 + 单位/语言差单独一桶 ──────────────────────────────
_CN = {'零':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
       '百':100,'千':1000,'万':10000,'亿':100000000}


def cn2num(s):
    """中文数字 → 阿拉伯数字（够用即可:一~九十九、千、万、亿）
    「三倍」→「3」;「二十」→「20」;「一百二十」→「120」"""
    if not s:
        return None
    if not any(c in _CN for c in str(s)):
        return None
    s = str(s).replace('两', '二')
    total, section, digit = 0, 0, 0
    for ch in s:
        if ch in _CN:
            v = _CN[ch]
            if v >= 10000:
                section = (section + digit) * v
                total += section
                section, digit = 0, 0
            elif v >= 1000:
                section += (digit or 1) * v
                digit = 0
            elif v >= 100:
                section += (digit or 1) * v
                digit = 0
            elif v == 10:
                section += (digit or 1) * 10
                digit = 0
            else:
                digit = v
        else:
            return None
    return str(total + section + digit)


def num2cn(s):
    """阿拉伯数字 → 中文数字（1~9999）
    3 → 三 · 20 → 二十 · 12 → 十二 · 105 → 一百零五
    用于在中文原文里找「三倍」这种写法"""
    try:
        v = int(float(s))
    except Exception:
        return None
    if v <= 0 or v > 9999:
        return None
    D = '零一二三四五六七八九'
    if v < 10:
        return D[v]
    if v < 20:
        return '十' + (D[v % 10] if v % 10 else '')
    if v < 100:
        return D[v // 10] + '十' + (D[v % 10] if v % 10 else '')
    if v < 1000:
        h, rest = divmod(v, 100)
        out = D[h] + '百'
        if rest == 0:
            return out
        if rest < 10:
            return out + '零' + D[rest]
        return out + num2cn(rest)
    q, rest = divmod(v, 1000)
    out = D[q] + '千'
    if rest == 0:
        return out
    if rest < 100:
        return out + '零' + num2cn(rest)
    return out + num2cn(rest)


def numcore(s):
    m = re.search(r'-?[0-9]+(?:\.[0-9]+)?', str(s).replace(',', '').replace('％', '%'))
    return m.group(0) if m else None


SCALE_CN = {'亿': 1e8, '万': 1e4, '千': 1e3}
SCALE_EN = {'thousand': 1e3, 'k': 1e3, 'million': 1e6, 'm': 1e6,
             'billion': 1e9, 'bn': 1e9, 'b': 1e9, 'trillion': 1e12}


def norm_values(text):
    """把一段文本里的所有数折成【同一个数值口径】—— 和核验卡的 values() 同一套。
    ★ 这是关键:「820万条」和「8.2 million pieces」是同一个数,
      纯字符串匹配会判成"没有",数值归一才判得出来。"""
    o = set()
    x = re.sub(r',', '', str(text or ''))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(thousand|million|billion|trillion|bn|[kmb])\b', x, re.I):
        o.add(float(m.group(1)) * SCALE_EN.get(m.group(2).lower(), 1))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*([亿万千])', x):
        o.add(float(m.group(1)) * SCALE_CN[m.group(2)])
    for m in re.finditer(r'\d+(?:\.\d+)?', x):
        o.add(float(m.group(0)))
    return o


def _num_value(name):
    """把「205 亿美元」「820 万条记录」这类写法折成数值（单位取中文量级词）"""
    raw = re.search(r'-?[0-9]+(?:[.,][0-9]+)?', str(name))
    if not raw:
        return None
    v = float(raw.group(0).replace(',', ''))
    rest = str(name)[raw.end():].strip()   # ★ 前面常有空格("820 万条"),不 strip 就匹配不到单位
    for unit, mul in (('亿', 1e8), ('万', 1e4), ('千', 1e3)):
        if rest.startswith(unit):
            v *= mul
            break
    else:
        m = re.search(r'(thousand|million|billion|trillion|bn)\b', rest, re.I)
        if m:
            v *= SCALE_EN.get(m.group(1).lower(), 1)
    return v


def judge_number(num: str, text: str):
    """★ 返回 (桶, 证据)。桶 ∈ hit / unit_mismatch / miss / not_a_number
    - hit:            数字和单位都对得上
    - unit_mismatch:  数字在,但单位/表述对不上(如 205亿美元 vs 20.5 billion)—— 要人换算,不是"没有"
    - miss:           数字在文本里根本找不到(前提:文本 status==ok)
    - not_a_number:   这一项压根不是数(如"全国首个""两个月")"""
    if not text:
        return 'miss', 'no_text'
    t = re.sub(r'[\s,，]', '', text)
    n = numcore(num)
    if n is None:
        # 非数字项:直接子串比
        plain = re.sub(r'[\s,，]', '', str(num))
        return ('hit' if plain and plain in t else 'miss'), 'plain'
    esc = re.escape(n)
    # ★ 第一步:数值归一比较(「820万」vs「8.2 million」这类)—— 卡的 values() 就是这么做的
    nv = _num_value(num)
    if nv is not None and text:
        for v in norm_values(text):
            if abs(v - nv) <= 1e-6 * max(1.0, abs(nv)):
                return 'hit', 'value=%g' % nv
    # ★ 所有出现位置都要看 —— 只看第一个会踩坑:数字可能先在导航/URL里裸出现,
    #   后面才是带单位的正文("205" vs "205亿美元")
    toks = list(re.finditer(r'(?<![0-9.])' + esc + r'(?![0-9.])', t))
    if not toks:
        # ★ 中文数字:中文原文写「三倍」「二十家」,不是「3倍」「20家」—— 不认就会把有的判成没有
        cn = num2cn(n)
        if cn:
            cnesc = re.escape(cn)
            toks = list(re.finditer(cnesc, t))
    if not toks:
        return 'miss', 'no_token'
    # ★ 单位:先把空白剔掉 —— 之前把空格算进单位(" 亿美元"),正文又已去过空格 ⇒ 永远判不中
    # ★ 符号不是单位 —— "+165%" 的单位是 "%",不是 "+%"
    unit_txt = ''.join(re.findall(r'[^\d]', str(num))).strip().lstrip('+-').strip()
    if not unit_txt:
        return 'hit', 'n=%s @%d处' % (n, len(toks))
    # 单位可能隔着修饰词("600多个人工智能任务"、"增长超过165%")⇒ 看窗口,不看紧邻
    for tk in toks:
        win = t[tk.end():tk.end() + 14]
        if unit_txt in win:
            return 'hit', 'n=%s unit@+%d' % (n, win.index(unit_txt))
        back = t[max(0, tk.start() - 14):tk.start()]
        if unit_txt in back:
            return 'hit', 'n=%s unit@-%d' % (n, 14 - back.rindex(unit_txt))
    return 'unit_mismatch', 'n=%s unit=%s (%d处都没有单位)' % (n, unit_txt, len(toks))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('--out', default=None, help='把正文存到文件')
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    r = fetch(a.url, use_browser=not a.no_browser)
    print(json.dumps({k: v for k, v in r.items() if k != 'text'}, ensure_ascii=False))
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(r['text'])
    else:
        print(r['text'][:600])
