#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 给免码静态站生成每卡的 og:image（1200×630，链接预览用）。

跑法: python3 eval3/build_og.py
输出: output/site/assets/og/id-XXXX.png（227 张）

★ og:image 和朋友圈分享图不是同一张东西:
  og:image = 别人在聊天/社交里贴链接时的预览图（横版 1200×630）
  分享图   = 发朋友圈时自己配的图（竖版 1080×1440，在 output/种子卡-分享图/）
"""
import json, os, base64

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'site', 'assets', 'og')
CARDS = json.load(open(os.path.join(HERE, 'seed_cards.json'), encoding='utf-8'))['cards']

PAT = {
    '团队自报': r'自报|厂商自|官方口径|官方称|自称|宣称',
    '未经同行评议': r'未(经)?(同行评议|peer)|预印本|preprint|投稿',
    '无独立复测': r'无独立复测|无独立(复现|验证|复核)|未见独立|尚无独立|无第三方|无独立审计',
    '单一来源': r'仅(有|见)|单一来源|唯一来源|尚无其他|未获.{0,4}印证',
    '口径不一致': r'两口径|口径不|口径分列|≠|不等于|约合|换算',
}
VC = {'ok': ('核得住', '#1f7a5a'), 'warn': ('有出入，要盯', '#a8551f'),
      'x': ('查不了', '#6b7370'), 'u': ('没核过', '#6b7370')}

HTML = '''<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0}</style></head><body>
<canvas id="cv" width="1200" height="630"></canvas>
<script>
const CARDS=__CARDS__;
const VC=__VC__;
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function wrap(ctx,t,x,y,maxw,lh,maxl){
  let line='',lines=[]; const s=String(t);
  for(const ch of s){ if(ctx.measureText(line+ch).width>maxw){lines.push(line);line=ch;if(lines.length>=maxl)break;} else line+=ch; }
  if(lines.length<maxl&&line)lines.push(line);
  if(lines.length>=maxl&&s.length>lines.join('').length)lines[lines.length-1]=lines[lines.length-1].slice(0,-1)+'…';
  lines.forEach((l,i)=>ctx.fillText(l,x,y+i*lh)); return y+lines.length*lh;
}
function draw(cv,c){
  const x=cv.getContext('2d'), W=cv.width, H=cv.height, P=64; let y=142;
  x.fillStyle='#ffffff'; x.fillRect(0,0,W,H);
  x.fillStyle='#fafbf9'; x.fillRect(0,0,W,8);
  x.fillStyle='#8b938f'; x.font='600 24px -apple-system,"PingFang SC",sans-serif';
  x.fillText('有出处 · 这条我核到哪儿了',P,62);
  x.fillStyle='#14181a'; x.font='700 46px -apple-system,"PingFang SC",sans-serif';
  y=wrap(x,c.head,P,y,W-P*2,62,3)+16;
  const lab=VC[c.vc][0], col=VC[c.vc][1];
  x.fillStyle=col; x.font='700 30px -apple-system,"PingFang SC",sans-serif';
  x.fillText((c.vc==='ok'?'✓ ':'⚠ ')+lab,P,y); y+=44;
  if(c.qual.length){
    x.fillStyle='#a8551f'; x.font='500 24px -apple-system,"PingFang SC",sans-serif';
    x.fillText('原文自己写明：'+c.qual.join('、'),P,y); y+=40;
  }
  // 底部：号 + 域名
  x.fillStyle='#e3e7e5'; x.fillRect(P,H-104,W-P*2,2);
  x.fillStyle='#2a4a6b'; x.font='600 28px ui-monospace,Menlo,monospace';
  x.fillText('bg.'+c.no,P,H-58);
  x.fillStyle='#8b938f'; x.font='400 22px -apple-system,"PingFang SC",sans-serif';
  const host=(c.url||'').split('/')[2]||'';
  x.textAlign='right'; x.fillText(host||'有出处',W-P,H-58); x.textAlign='left';
}
</script></body></html>'''

JS = """(c)=>{const cv=document.getElementById('cv');
const x=cv.getContext('2d'); x.fillStyle='#fff'; x.fillRect(0,0,cv.width,cv.height);
draw(cv,c); return cv.toDataURL('image/png');}"""


def main():
    import re
    cards = []
    for c in CARDS:
        blob = ' '.join([(n.get('d') or '') for n in (c.get('nums') or [])]) + ' ' + (c.get('src') or '')
        q = [k for k, p in PAT.items() if re.search(p, blob)]
        cards.append({'id': c['id'], 'no': c['no'], 'head': c['head'],
                      'url': c.get('url') or '', 'vc': c['vc'], 'qual': q})
    os.makedirs(OUT, exist_ok=True)
    # ★★ 效率:og:image 是整条自迭代里最慢的一步(playwright 画 270 张)。
    #   ★ 卡集没变 ⇒ 图也没变 ⇒ 不画。★ 指纹 = 全部 (卡 id, 核验号, 限定词) 序列。
    import hashlib as _h
    _fp = _h.sha256('|'.join('%s:%s:%s' % (c.get('id'), c.get('no'), ','.join(c.get('qual') or [])) for c in CARDS).encode()).hexdigest()[:16]
    _fpfile = os.path.join(HERE, 'og_fingerprint.txt')
    try:
        _old = open(_fpfile, encoding='utf-8').read().strip()
    except Exception:
        _old = ''
    if _old == _fp and len([f for f in os.listdir(OUT) if f.endswith('.png')]) >= len(CARDS):
        print('  · 卡集没变,og:image 跳过(省掉最慢的一步)')
        return
    for f in os.listdir(OUT):
        if f.endswith('.png'):
            os.remove(os.path.join(OUT, f))
    hp = os.path.join(OUT, '_gen.html')
    vcs = {k: list(v) for k, v in VC.items()}
    open(hp, 'w', encoding='utf-8').write(
        HTML.replace('__CARDS__', json.dumps(cards, ensure_ascii=False))
            .replace('__VC__', json.dumps(vcs, ensure_ascii=False)))

    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={'width': 1200, 'height': 630})
            await pg.goto('file://' + hp)
            for i, c in enumerate(cards):
                u = await pg.evaluate(JS, c)
                open(os.path.join(OUT, 'id-%04d.png' % c['id']), 'wb').write(
                    base64.b64decode(u.split(',')[1]))
                if (i + 1) % 50 == 0:
                    print('  %d/%d' % (i + 1, len(cards)))
            await b.close()
    import asyncio
    asyncio.run(run())
    os.remove(hp)
    print('✓ %d 张 og:image → %s' % (len(cards), OUT))
    with open(_fpfile, 'w', encoding='utf-8') as _f:
        _f.write(_fp)


if __name__ == '__main__':
    main()
