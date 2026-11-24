#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 给核得住的种子卡批量生成朋友圈分享图(1080×1440)。

跑法: python3 eval3/make_seed_shares.py
输入: eval3/seed_cards.json
输出: output/种子卡-分享图/id-XXXX-bg.<号>.png  (79 张)
      output/种子卡-分享图/INDEX.md          (一张表,能直接贴到站上)

★ 每张图的构成(和核验卡同一套):
  标题 · 核验结论 · 要盯的(有才显示) · 逐字原文 · 号 · 二维码(编静态页 URL)
★ 二维码编的是【静态页 URL】不是号 —— 因为真站点的静态页还不带号,
  编 URL 才能真打开;号印在旁边,等人搜(补丁第 6 步上线后就能搜到)。
"""
import json, os, re, subprocess, sys, tempfile, base64

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = '/workspace/output'
SRC = os.path.join(HERE, 'seed_cards.json')
DST = os.path.join(OUT, '种子卡-分享图')
PORT = 8788

JS_LIB = open(os.path.join(HERE, '_ux', 'qr', 'qrcode.min.js'), encoding='utf-8').read() \
    if os.path.exists(os.path.join(HERE, '_ux', 'qr', 'qrcode.min.js')) \
    else open(os.path.join(OUT, '_ux', 'qr', 'qrcode.min.js'), encoding='utf-8').read()

HTML = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#fff}
canvas{display:block}
</style></head><body>
<script>__QRLIB__</script>
<canvas id="cv" width="1080" height="1440"></canvas>
<script>
const CARDS=__CARDS__;
const BASE=__BASE__;
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function wrap(ctx,text,x,y,maxw,lh,maxl){
  const words=String(text).split(''); let line='',lines=[];
  for(const ch of words){
    if(ctx.measureText(line+ch).width>maxw){ lines.push(line); line=ch; if(lines.length>=maxl){break;} }
    else line+=ch;
  }
  if(lines.length<maxl&&line) lines.push(line);
  if(lines.length>=maxl&&String(text).length>lines.join('').length) lines[lines.length-1]=lines[lines.length-1].slice(0,-1)+'…';
  lines.forEach((l,i)=>ctx.fillText(l,x,y+i*lh));
  return y+lines.length*lh;
}
function roundRect(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);
 ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}
function draw(cv,card,W,H){
  const c=card; const ctx=cv.getContext('2d'); const PAD=64; let y=PAD+6;
  ctx.fillStyle='#ffffff'; ctx.fillRect(0,0,W,H);
  ctx.fillStyle='#f2f5f4'; ctx.fillRect(0,0,W,6);
  // kicker
  ctx.fillStyle='#6b7370'; ctx.font='600 21px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('有出处 · 这条我核到哪儿了',PAD,y); y+=52;
  // 标题
  ctx.fillStyle='#16191b'; ctx.font='700 42px -apple-system,"PingFang SC",sans-serif';
  y=wrap(ctx,c.head,PAD,y+30,W-PAD*2,58,3); y+=22;
  // 标签
  if(c.tag){ ctx.fillStyle='#8d3b31'; ctx.font='500 22px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('〔'+c.tag+'〕',PAD,y); y+=40; }
  // 结论
  const okc = c.vc==='ok';
  // ★ 核验章:形状 = 状态(方=核得住 / 三角=要盯 / 圆=查不了 / 虚线方=没核过)
  const BS=36, bx=PAD, by2=y-26;
  const vc=c.vc||'u';
  if(vc==='ok'){ ctx.fillStyle='#1f6b52'; roundRect(ctx,bx,by2,BS,BS,8); ctx.fill();
    ctx.strokeStyle='#fff'; ctx.lineWidth=3; ctx.lineCap='round'; ctx.lineJoin='round';
    ctx.beginPath(); ctx.moveTo(bx+9,by2+18); ctx.lineTo(bx+15,by2+25); ctx.lineTo(bx+27,by2+11); ctx.stroke();
  } else if(vc==='warn'){ ctx.fillStyle='#b03a2e';
    ctx.beginPath(); ctx.moveTo(bx+BS/2,by2+1); ctx.lineTo(bx+BS-1,by2+BS-2); ctx.lineTo(bx+1,by2+BS-2); ctx.closePath(); ctx.fill();
    ctx.strokeStyle='#fff'; ctx.lineWidth=3; ctx.lineCap='round';
    ctx.beginPath(); ctx.moveTo(bx+BS/2,by2+11); ctx.lineTo(bx+BS/2,by2+23); ctx.stroke();
    ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(bx+BS/2,by2+29,2,0,7); ctx.fill();
  } else if(vc==='x'){ ctx.strokeStyle='#8b959b'; ctx.lineWidth=2.4;
    ctx.beginPath(); ctx.arc(bx+BS/2,by2+BS/2,BS/2-2,0,7); ctx.stroke();
    ctx.fillStyle='#8b959b'; ctx.font='700 22px -apple-system,sans-serif'; ctx.textAlign='center';
    ctx.fillText('?',bx+BS/2,by2+27); ctx.textAlign='left';
  } else { ctx.strokeStyle='#a8b1b6'; ctx.lineWidth=2.2; ctx.setLineDash([5,4]);
    roundRect(ctx,bx,by2,BS,BS,8); ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle='#a8b1b6'; ctx.lineWidth=2.6; ctx.beginPath(); ctx.moveTo(bx+11,by2+BS/2); ctx.lineTo(bx+BS-11,by2+BS/2); ctx.stroke();
  }
  const tx=PAD+BS+14;
  ctx.fillStyle= okc?'#1f6b52':'#b03a2e'; ctx.font='700 30px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText(okc?'核得住 —— 这条里的每个数，出处正文里都能找到':('要盯 —— '+c.vc_detail),tx,y); y+=44;
  if(!okc){
    ctx.fillStyle='#6b7370'; ctx.font='400 20px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('「没找到」只说明正文里没找到这个写法，不等于出处里没有。',PAD,y); y+=34;
  }
  // ★ 限定词:和绿章同级 —— 「数字都对上」不等于「这话牢靠」
  if(c.qual && c.qual.length){
    ctx.fillStyle='#b03a2e'; ctx.font='600 24px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('⚠ 原文自己写明：'+c.qual.join('、'),PAD,y); y+=38;
    ctx.fillStyle='#8b938f'; ctx.font='400 19px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('（数字对得上，但这话是限定过的 —— 见底稿里的口径说明）',PAD,y); y+=36;
  }
  // 逐字原文
  if(c.quote){
    ctx.fillStyle='#8b938f'; ctx.font='600 21px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('引用的原文（逐字）',PAD,y); y+=36;
    ctx.fillStyle='#48524f'; ctx.font='400 23px ui-monospace,Menlo,monospace';
    y=wrap(ctx,c.quote,PAD,y,W-PAD*2,36,4); y+=24;
  }
  // ★ 口径说明:跟着数字一起存的东西 —— 填掉空白,也让人知道这条的数是怎么来的
  if(c.nums && c.nums.length){
    ctx.fillStyle='#6b7370'; ctx.font='600 20px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('口径说明（跟着数字一起存的）',PAD,y); y+=32;
    const show=c.nums.slice(0,3);
    for(const nn of show){
      ctx.fillStyle='#16191b'; ctx.font='600 21px ui-monospace,Menlo,monospace';
      ctx.fillText(String(nn.n||''),PAD,y);
      ctx.fillStyle='#6b7370'; ctx.font='400 19px -apple-system,"PingFang SC",sans-serif';
      y=wrap(ctx,String(nn.d||''),PAD+220,y,W-PAD*2-220,28,2); y+=10;
    }
    y+=14;
  }
  // 底部:号 + 二维码
  const by=Math.max(y+70,H-250);   // ★ 内容短时别留 700px 空白
  ctx.fillStyle='#cfd6d2'; ctx.fillRect(PAD,by,W-PAD*2,2);
  const QS=150, qx=W-PAD-QS, qy=by+14;
  if(BASE){
    // ★ 二维码指向【我自己站里的这一张卡】,不是上游的原消息页 ——
    //   读者扫码要看到的是「我核到哪儿了」,不是原文。
    const qr=qrcode(0,'M');
    qr.addData(BASE+'/signals/id-'+String(c.id).padStart(4,'0')+'.html'); qr.make();
    const mn=qr.getModuleCount(), sc=Math.floor(QS/(mn+8)), sz=mn*sc;
    const ox=qx+Math.floor((QS-sz)/2), oy=qy+Math.floor((QS-sz)/2);
    ctx.fillStyle='#ffffff'; ctx.fillRect(qx,qy,QS,QS); ctx.fillStyle='#16191b';
    for(let r=0;r<mn;r++)for(let k=0;k<mn;k++) if(qr.isDark(r,k)) ctx.fillRect(ox+k*sc,oy+r*sc,sc,sc);
  }
  ctx.fillStyle='#2f5d8c'; ctx.font='600 29px ui-monospace,Menlo,monospace';
  ctx.fillText('bg.'+c.no,PAD,by+52);
  ctx.fillStyle='#6b7370'; ctx.font='400 19px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('在「有出处」搜这个号，可见底稿与更正记录',PAD,by+92);
  ctx.fillStyle='#8b938f'; ctx.font='400 19px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('这张卡标的是「我核到哪儿」和「哪些还没核」—— 结论对错要你自己看。',PAD,by+126);
}
function render(){
  const cv=document.getElementById('cv');
  draw(cv,CARDS[0],cv.width,cv.height);
  return cv.toDataURL('image/png');
}
render();
</script></body></html>'''


def main():
    d = json.load(open(SRC, encoding='utf-8'))
    # ★ 只画【核得住 且 原文有自述限定】的卡:★ 「限定词与章同级」是这个产品的主张,
    #   ★ 一张看不出它被限定过的卡,分享出去是在削弱自己。★ ★★ 而无限定的卡留在站内底稿里,★ ★★ 不进传播面。
    cards = [c for c in d['cards'] if c['vc'] == 'ok' and c.get('qual')]
    # ★ 限定词从主数据读(seed_cards.json 里那一份)—— 不在这里重算。
    #   (旧版这里有一份更宽松的正则,带着「宣称|仅有|投稿」三个在真语料上验过的假阳性词。)
    for c in cards:
        c['qual'] = c.get('qual') or []
    print('种子卡(vc=ok): %d 条' % len(cards))
    os.makedirs(DST, exist_ok=True)
    # ★ 先清掉旧图 —— 卡片数变了(79→78)时上轮的孤儿会留在目录里,
    #   INDEX.md 只有 78 行而目录里有 85 个 PNG,谁也不知道哪张是当前的
    import glob as _g
    for _f in _g.glob(os.path.join(DST, '*.png')):
        os.remove(_f)
    # ★ 落点从 site_config.json 读(唯一真源);没有则退回 SITE_BASE,再没有就不画二维码
    try:
        _cfg = json.load(open(os.path.join(HERE, 'site_config.json'), encoding='utf-8'))
        # ★ 二维码用 share_base(当前活的地址);★ canonical/og/feed 用 base(永久落点)。
        _base = (_cfg.get('share_base') or '').strip().rstrip('/') or (_cfg.get('base') or '').strip().rstrip('/')
    except Exception:
        _base = ''
    _base = _base or (os.environ.get('SITE_BASE') or '').strip().rstrip('/')
    print('  二维码落点: %s' % (_base or '★ 无 —— 二维码不画(没有指向自己站的地址)'))
    html = (HTML.replace('__QRLIB__', JS_LIB)
                .replace('__CARDS__', json.dumps(cards, ensure_ascii=False))
                .replace('__BASE__', json.dumps(_base)))
    hp = os.path.join(DST, '_gen.html')
    open(hp, 'w', encoding='utf-8').write(html)

    from playwright.async_api import async_playwright

    async def run():
        out = []
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={'width': 1080, 'height': 1440})
            await pg.goto('file://' + hp)
            for i, c in enumerate(cards):
                url = await pg.evaluate("""(c)=>{const cv=document.getElementById('cv');
                    const ctx=cv.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,cv.width,cv.height);
                    draw(cv,c,cv.width,cv.height);return cv.toDataURL('image/png');}""", c)
                fn = 'id-%04d-bg.%s.png' % (c['id'], c['no'])
                open(os.path.join(DST, fn), 'wb').write(base64.b64decode(url.split(',')[1]))
                out.append(fn)
                if (i + 1) % 20 == 0:
                    print('  %d/%d' % (i + 1, len(cards)))
            await b.close()
        return out

    files = __import__('asyncio').run(run())
    os.remove(hp)

    # INDEX.md
    md = ['# 种子卡分享图（%d 张）' % len(cards), '',
          '> 生成于 %s · 数据源:线上 signals.js（%s · %d 条）' % (
              __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'), d.get('built_at'), d['n']),
          '> 每张卡都**真核过出处正文**:所有数字都能在原文里找到,才算种子。',
          '> 二维码编的是静态页 URL;号印在旁边(等站点支持「按号搜」后就能搜)。', '',
          '| id | 号 | 标题 | 标签 | 分享图 |', '|---|---|---|---|---|']
    for c, f in zip(cards, files):
        md.append('| %d | `bg.%s` | %s | %s | [%s](%s) |' % (
            c['id'], c['no'], (c['head'] or '').replace('|', '／')[:60],
            c.get('tag', ''), f, f))
    open(os.path.join(DST, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(md))
    print('★ %d 张分享图 + INDEX.md → %s' % (len(files), DST))


if __name__ == '__main__':
    main()
