#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前体检 · 独立本地服务。

跑法: python3 eval3/check_service.py            # 默认 127.0.0.1:18760
      python3 eval3/check_service.py --port 18900

形态说明:★ 这是「脱离宿主、浏览器管理 + 提供 API」那一档 ——
          装上就能用,不用登录、不用注册、不用 API Key。
          (和 EAC-Pack / dsh-our-free-model 的「独立本地服务」同一档)

接口:
  GET  /            体检页(同源打开,地址与令牌自动带上)
  GET  /health      {"ok":true}
  POST /check       {"url":"...","claim":"...","quote":"..."}
                    → {"status":"ok|warn|x","lines":[...],"no":"...","quals":[...],"bad":[...]}

★ 安全(信任边界,永不砍):
  1. 只绑 127.0.0.1 —— 不对外暴露
  2. 每次启动生成随机令牌,/check 必须带对(否则任何本地网页都能调它抓内网)
  3. 拒绝指向内网/环回/链路本地/保留地址的目标(SSRF 闸)
  4. 只允许 http/https
"""
import argparse, json, os, secrets, sys, ipaddress, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# ★ 核验逻辑的唯一真源是 prepublish-check skill 里的脚本 —— 复用,不要复制一份
def _find_skill_scripts():
    """从当前目录往上找 .skills/prepublish-check/scripts —— 不写死相对层数"""
    d = HERE
    for _ in range(5):
        cand = os.path.join(d, '.skills', 'prepublish-check', 'scripts')
        if os.path.isdir(cand):
            return cand
        d = os.path.dirname(d)
    return os.path.join(HERE, '_missing_skill_scripts')


SKILL = _find_skill_scripts()
sys.path.insert(0, SKILL)
from fetch_source import fetch, judge_number, numcore  # noqa: E402
from check import no_for, pick_nums, in_text, qualifiers_of, split_sentences, RULESET  # noqa: E402

TOKEN = secrets.token_urlsafe(18)
PORT = 18760


def blocked_target(url):
    """★ SSRF 闸:拒绝内网/环回/链路本地/保留地址"""
    try:
        p = urlparse(url)
    except Exception:
        return 'url 解析失败'
    if p.scheme not in ('http', 'https'):
        return '只允许 http/https'
    host = p.hostname
    if not host:
        return '没有主机名'
    if host.lower() in ('localhost', 'localhost.localdomain'):
        return '拒绝环回主机'
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return '域名解析失败'
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except Exception:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return '拒绝内网地址 %s' % ip
    return None


def run_check(url, claim, quote=''):
    res = {'url': url, 'claim': claim, 'status': 'x', 'detail': '', 'lines': [],
           'no': no_for(claim, quote), 'quals': [], 'bad': [], 'nums': [], 'src_len': 0}
    r = fetch(url, use_browser=True)
    res['src_len'] = r.get('len', 0)
    res['via'] = r.get('via', '')
    if r.get('status') != 'ok':
        res['detail'] = {'stub': '只抓到空壳页（HTTP 200 但正文没拿到）',
                         'blocked': '被反爬挡了（403）',
                         'timeout': '没抓到（超时 / 网络不通）'}.get(r.get('status'), r.get('status'))
        res['lines'] = [
            ('能不能发', '查不了 —— 这次给不了结论'),
            ('哪几句不行', '没拿到出处正文，所以什么都比不了。「查不了」不等于「有问题」，也不等于「没问题」。'),
            ('怎么改', '这一条只能你自己开原页核。要不要把链接直接贴给读者，并标一句“出处见原文”？')]
        return res
    text = r.get('text', '')
    res['quals'] = qualifiers_of(text)
    claim_nums = pick_nums(claim)
    res['nums'] = [{'n': n['key'], 'found': in_text(n, text)} for n in claim_nums]
    bad_sents = []
    for i, s in enumerate(split_sentences(claim), 1):
        bad = [n['key'] for n in pick_nums(s) if not in_text(n, text)]
        if bad:
            bad_sents.append({'i': i, 'text': s, 'bad': bad})
    bad_all = [x['n'] for x in res['nums'] if not x['found']]
    res['status'] = 'ok' if not bad_all else 'warn'
    res['bad'] = bad_all
    res['detail'] = ('抓到出处正文，每个数字都能找到' if not bad_all
                     else '抓到出处正文，但 %d 个数字在正文里没找到' % len(bad_all))
    if res['status'] == 'ok':
        res['lines'] = [
            ('能不能发', '可以发 —— 你写的 %d 个数，出处正文里都能找到' % len(res['nums'])),
            ('哪几句不行', '没找到对不上的句子。'),
            ('怎么改', '数字这关过了。但我没核：限定词有没有被放大、两件事是不是被说成因果、结论比证据强多少 —— 那三件是机器原理上核不了的，得你看。')]
    else:
        res['lines'] = [
            ('能不能发', '先别发 —— %d 句里有数对不上' % len(bad_sents)),
            ('哪几句不行', '\n'.join('第 %d 句：%s\n  里面的 %s —— 出处正文里没找到这个数'
                                  % (s['i'], s['text'], '、'.join(s['bad'])) for s in bad_sents)),
            ('怎么改', '\n'.join('第 %d 句（%s）：① 打开原页找到这个数，换成原文的说法（原文的口径最稳）；或 ② 把这个数删掉，只留结论；或 ③ 保留，但标一句「这个数我没在出处里找到」。'
                                  % (s['i'], '、'.join(s['bad'])) for s in bad_sents))]
    if res['quals']:
        res['lines'].append(('额外提示', '原文自己写明：%s —— 数字对得上，但这话是限定过的' % '、'.join(res['quals'])))
    res['lines'].append(('我核了什么', '抓到出处正文 %d 字符（%s）· 比对了 %d 个数'
                          % (res['src_len'], res['via'], len(res['nums']))))
    return res


class H(BaseHTTPRequestHandler):
    server_version = 'digao-check/1.0'

    def log_message(self, fmt, *a):
        if os.environ.get('DIGAO_VERBOSE'):
            sys.stderr.write('[check] ' + fmt % a + '\n')

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Digao-Token')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b'')

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/health':
            return self._send(200, json.dumps({'ok': True, 'ruleset': RULESET}))
        if path in ('/', '/check'):
            page = os.path.join(os.path.dirname(HERE), '发布前体检.html')
            try:
                html = open(page, encoding='utf-8').read()
            except Exception as e:
                return self._send(500, json.dumps({'error': str(e)}))
            # ★ 同源打开:把服务地址与令牌内联进页面,用户不用手填任何东西
            inj = ('<script>window.__SVC__={base:%s,token:%s,mode:"check"};</script>'
                   % (json.dumps('http://127.0.0.1:%d' % self.server.server_address[1]),
                      json.dumps(TOKEN)))
            html = html.replace('<script>', inj + '<script>', 1)
            return self._send(200, html, 'text/html; charset=utf-8')
        self._send(404, json.dumps({'error': 'no such path'}))

    def do_POST(self):
        if unquote(urlparse(self.path).path) != '/check':
            return self._send(404, json.dumps({'error': 'no such path'}))
        tok = self.headers.get('X-Digao-Token', '')
        if not secrets.compare_digest(tok, TOKEN):
            return self._send(403, json.dumps({'error': 'bad token'}))
        try:
            n = int(self.headers.get('Content-Length', 0))
            if n > 20000:
                return self._send(413, json.dumps({'error': 'body too large'}))
            p = json.loads(self.rfile.read(n) or b'{}')
        except Exception as e:
            return self._send(400, json.dumps({'error': 'bad body: %s' % e}))
        url = (p.get('url') or '').strip()
        if not url:
            return self._send(400, json.dumps({'error': 'url required'}))
        why = blocked_target(url)
        if why:
            return self._send(400, json.dumps({'error': 'blocked target: %s' % why}))
        try:
            self._send(200, json.dumps(run_check(url, p.get('claim') or '', p.get('quote') or ''),
                                      ensure_ascii=False))
        except Exception as e:
            self._send(502, json.dumps({'error': 'check failed: %s' % e}))


def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=PORT)
    a = ap.parse_args()
    PORT = a.port
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    except OSError as e:
        print('★ 端口 %d 被占用（%s）—— 服务多半已经在跑了,直接打开就行。' % (PORT, e.strerror or e))
        print('  http://127.0.0.1:%d/' % PORT)
        return 0
    print('═══ 发布前体检 · 本地服务 ═══')
    print('  体检页    http://127.0.0.1:%d/' % PORT)
    print('  接口      POST %s/check' % ('http://127.0.0.1:%d' % PORT))
    print('  令牌      %s   （同源打开页面时自动带上,不用手填）' % TOKEN)
    print('\n★ 只绑本机。Ctrl-C 停。')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停')
    return 0


if __name__ == '__main__':
    sys.exit(main())
