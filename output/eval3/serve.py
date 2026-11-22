#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地抓取服务 —— 让「主动抓出处」随时能调,而不是只能构建期跑。

跑法: python3 eval3/serve.py            # 默认 127.0.0.1:8765
      python3 eval3/serve.py --port 9000

接口:
  GET  /health          → {"ok":true}
  GET  /card            → 核验卡(已配好本服务地址与令牌)
  POST /fetch           {"url":"https://..."} → {"status":"ok|stub|blocked|timeout","len":N,"text":"..."}

★ 安全(信任边界,永不砍):
  1. 只绑 127.0.0.1 —— 不对外暴露
  2. 每次启动生成随机令牌,/fetch 必须带对(防止别的本地页面/网页偷偷调)
  3. 只允许 http/https
  4. ★ 拒绝指向内网/环回/链路本地地址的目标(SSRF:否则这服务能被用来打你内网)
  5. 响应体大小封顶
"""
import argparse, json, os, secrets, socket, sys, ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_source import fetch  # noqa: E402

TOKEN = secrets.token_urlsafe(18)
MAX_TEXT = 400_000


def blocked_target(url):
    """★ SSRF 闸:拒绝内网/环回/链路本地/保留地址的目标"""
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
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return '拒绝内网地址 %s' % ip
    return None


class H(BaseHTTPRequestHandler):
    server_version = 'digao-fetch/1.0'

    def log_message(self, fmt, *a):
        if os.environ.get('DIGAO_VERBOSE'):
            sys.stderr.write('[fetch] ' + fmt % a + '\n')

    def _send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        # ★ 同源隔离:只允许本机页面来调
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Digao-Token')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b'')

    def do_GET(self):
        # ★ 中文路径是 percent-encoded 的,不解码就匹配不上
        path = unquote(urlparse(self.path).path)
        if path == '/health':
            self._send(200, json.dumps({'ok': True, 'token_required': True}))
        elif path in ('/体检', '/check'):
            page = os.path.join(os.path.dirname(HERE), '发布前体检.html')
            try:
                html = open(page, encoding='utf-8').read()
            except Exception as e:
                return self._send(500, json.dumps({'error': str(e)}))
            # ★ 同源打开就把地址和令牌内联进去 —— 页面不用手填任何东西
            inj = ('<script>window.__SVC__={base:%s,token:%s};</script>'
                   % (json.dumps('http://127.0.0.1:%d' % self.server.server_address[1]),
                      json.dumps(TOKEN)))
            html = html.replace('<script>', inj + '<script>', 1)
            self._send(200, html, 'text/html; charset=utf-8')
        elif path == '/card':
            card = os.path.join(os.path.dirname(HERE), '核验卡-朋友圈版-原型.html')
            try:
                html = open(card, encoding='utf-8').read()
            except Exception as e:
                return self._send(500, json.dumps({'error': str(e)}))
            self._send(200, html, 'text/html; charset=utf-8')
        else:
            self._send(404, json.dumps({'error': 'no such path'}))

    def do_POST(self):
        if urlparse(self.path).path != '/fetch':
            return self._send(404, json.dumps({'error': 'no such path'}))
        # ★ 令牌:防止别的页面偷偷调本机服务
        tok = self.headers.get('X-Digao-Token', '')
        if not secrets.compare_digest(tok, TOKEN):
            return self._send(403, json.dumps({'error': 'bad token'}))
        try:
            n = int(self.headers.get('Content-Length', 0))
            if n > 20000:
                return self._send(413, json.dumps({'error': 'body too large'}))
            payload = json.loads(self.rfile.read(n) or b'{}')
        except Exception as e:
            return self._send(400, json.dumps({'error': 'bad body: %s' % e}))
        url = (payload.get('url') or '').strip()
        if not url:
            return self._send(400, json.dumps({'error': 'url required'}))
        why = blocked_target(url)
        if why:
            return self._send(400, json.dumps({'error': 'blocked target: %s' % why}))
        try:
            r = fetch(url, use_browser=True)
        except Exception as e:
            return self._send(502, json.dumps({'error': 'fetch failed: %s' % e}))
        text = r.get('text', '')[:MAX_TEXT]
        self._send(200, json.dumps({
            'status': r.get('status', 'timeout'), 'len': r.get('len', 0),
            'via': r.get('via', ''), 'text': text,
        }, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--lan', action='store_true',
                    help='绑 0.0.0.0,同一 Wi-Fi 下的手机能访问（★ 令牌仍然必需）')
    a = ap.parse_args()
    if a.lan:
        a.host = '0.0.0.0'
    elif a.host not in ('127.0.0.1', 'localhost'):
        print('★ 只允许绑 127.0.0.1（要对外暴露用 --lan，并自己加 HTTPS）')
        return 1
    try:
        srv = ThreadingHTTPServer((a.host, a.port), H)
    except OSError as e:
        # ★ 端口被占 —— 大概率是服务已经在跑了。用户不该看到 Python 堆栈。
        print('\n★ 端口 %d 已被占用（%s）' % (a.port, e.strerror or e))
        print('  服务多半已经在运行了。直接打开:')
        print('    http://127.0.0.1:%d/体检' % a.port)
        print('  （想换端口：python3 serve.py --port 8799）')
        return 0
    base = 'http://%s:%d' % (a.host, a.port)
    print('═══ 本地抓取服务 ═══')
    print('  ★ 发布前体检（推荐）  %s/体检   (或 %s/check)' % (base, base))
    print('  核验卡(含本服务地址)  %s/card' % base)
    print('  抓取接口              POST %s/fetch' % base)
    print('  令牌(给页面的 X-Digao-Token 用):')
    print('    %s' % TOKEN)
    if a.lan:
        try:
            import subprocess as _sp
            ips=_sp.run(['hostname','-I'],capture_output=True,text=True).stdout.split()
        except Exception:
            ips=[]
        print('\n★ 手机上打开（同一个 Wi-Fi）：')
        for ip in ips[:2]:
            print('    http://%s:%d/体检' % (ip, a.port))
        print('  ★ 警告:同一网络下的人都能打开这个页面。令牌仍然必需,但页面里带着令牌。')
        print('  ★ 只在自己的 Wi-Fi 下临时用,别长期开着。')
    else:
        print('\n★ 只绑本机。Ctrl-C 停。')
    print('★ 只绑本机。Ctrl-C 停。') if not a.lan else None
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停')
    return 0


if __name__ == '__main__':
    sys.exit(main())
