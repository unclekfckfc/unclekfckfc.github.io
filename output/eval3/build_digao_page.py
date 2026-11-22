#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 /tmp/digao_data.json 渲染成单文件《底稿》。"""
import json, os

DATA = json.load(open('/workspace/output/eval3/digao_data.json', encoding='utf-8'))
OUT = '/workspace/output/底稿-结论可查的地方.html'

HTML = r'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>底稿 · 结论可查的地方</title>
<style>
*{box-sizing:border-box}
:root{
 --paper:#f4f3ef; --card:#fff; --ink:#1b1e1d; --ink2:#4e5654; --dim:#868e8a;
 --line:#e2e0d9; --line2:#efeDE7; --seal:#2a4a6b; --seal-bg:#eef2f6;
 --ochre:#8a6a3a; --ochre-bg:#fdfaf4; --ok:#4e6b5c; --ok-bg:#eef3f0;
 --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
 --serif:Georgia,"Songti SC","Source Han Serif SC","Noto Serif CJK SC",serif;
}
body{margin:0;background:var(--paper);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:var(--seal)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 90px}
header{background:var(--paper);border-bottom:1px solid var(--line);padding:26px 20px 0;margin-bottom:22px}
.hdwrap{max-width:1080px;margin:0 auto}
.brand{display:flex;align-items:baseline;gap:13px;flex-wrap:wrap}
.brand h1{font-family:var(--serif);font-size:30px;font-weight:400;margin:0;letter-spacing:.02em}
.brand .sub{color:var(--ink2);font-size:14px}
.nav{display:flex;gap:2px;margin-top:16px;flex-wrap:wrap}
.nav button{font:14px/1 inherit;background:none;border:0;border-bottom:2px solid transparent;
 padding:9px 2px;margin-right:20px;color:var(--dim);cursor:pointer}
.nav button.on{color:var(--ink);border-bottom-color:var(--ink)}
.nav button:hover{color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--line);
 border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-bottom:20px}
@media(max-width:760px){.kpis{grid-template-columns:repeat(3,1fr)}}
.kpi{background:var(--card);padding:11px 13px}
.kpi .lb{font-size:11.5px;color:var(--dim)}
.kpi .v{font-family:var(--mono);font-size:23px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:1px}
.kpi .v.s{color:var(--seal)}.kpi .v.o{color:var(--ochre)}.kpi .v.d{color:var(--ink2)}
.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.toolbar input[type=search]{font:14px/1 inherit;padding:9px 12px;border:1px solid var(--line);
 border-radius:7px;background:var(--card);min-width:230px;flex:1;max-width:380px;color:var(--ink)}
.toolbar input[type=search]:focus{outline:2px solid var(--seal);outline-offset:1px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font:12.5px/1 inherit;padding:6px 11px;border:1px solid var(--line);border-radius:20px;
 background:var(--card);color:var(--ink2);cursor:pointer}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.chip:hover{border-color:var(--dim)}
.rows{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card)}
.row{display:grid;grid-template-columns:88px 1fr auto;gap:13px;padding:12px 15px;
 border-bottom:1px solid var(--line2);cursor:pointer;align-items:start}
.row:last-child{border-bottom:0}
.row:hover{background:#faf9f6}
@media(max-width:680px){.row{grid-template-columns:1fr;gap:5px}}
.no{font-family:var(--mono);font-size:11.5px;color:var(--seal);background:var(--seal-bg);
 border-radius:4px;padding:2px 6px;display:inline-block;letter-spacing:.03em;white-space:nowrap}
.row .claim{font-size:15.5px;line-height:1.55}
.row .claim .cm{color:var(--dim);font-size:13px;display:block;margin-top:2px}
.badges{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.b{font-size:11px;padding:2px 7px;border-radius:4px;border:1px solid;white-space:nowrap}
.b-unc{color:var(--ochre);border-color:#e2d4b8;background:var(--ochre-bg)}
.b-fin{color:#8a3f3f;border-color:#e8cfcf;background:#fbf0f0}
.b-norun{color:var(--dim);border-color:var(--line);background:#faf9f6}
.b-link{color:var(--ok);border-color:#cdded4;background:var(--ok-bg)}
.b-dis{color:#7a5aa0;border-color:#ded0ea;background:#f7f3fb}
.b-num{color:var(--seal);border-color:#ccd9e5;background:var(--seal-bg)}
.stamp2d{margin-top:12px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;
 background:#fbfaf7;font-size:12.5px;line-height:1.85;display:inline-block}
.stamp2d .s2{display:block}
.stamp2d .ok{color:#3f6b52}.stamp2d .no{color:#8a6a3a}
.stamp2d .warn{color:#8a5a2a}.stamp2d .none{color:#8a6a3a}
/* ── 详情 ── */
.detail{background:var(--card);border:1px solid var(--line);border-radius:11px;overflow:hidden}
.dh{padding:22px 24px 18px;border-bottom:1px solid var(--line)}
.dh .no{font-size:13px;padding:3px 9px;margin-bottom:11px}
.dh h2{font-family:var(--serif);font-size:23px;font-weight:400;margin:0 0 12px;line-height:1.45}
.blk{padding:16px 24px;border-bottom:1px solid var(--line2)}
.blk:last-child{border-bottom:0}
.blk h3{font-size:11.5px;letter-spacing:.12em;color:var(--dim);margin:0 0 9px;font-weight:600}
.qt{font-family:var(--mono);font-size:13px;line-height:1.75;color:#2b3330;
 border-left:2px solid #c6ccc8;padding-left:13px;white-space:pre-wrap}
.note{background:var(--ochre-bg);border-left:2px solid #d3bb8c;padding:11px 14px;
 font-size:14px;color:#4a4238;border-radius:0 5px 5px 0}
.note .lb{font-size:11px;letter-spacing:.09em;color:#9a8560;margin-bottom:4px}
.warn{background:var(--ochre-bg);border:1px solid #e6d4b4;border-radius:8px;padding:12px 15px;
 font-size:14px;color:#6b4306;margin-bottom:12px}
.warn b{color:#5a37005}
.fx{border:1px solid var(--line);border-radius:8px;padding:11px 13px;margin-bottom:9px;background:#fbfaf7}
.fx .lane{font-size:11px;letter-spacing:.09em;color:var(--seal);margin-bottom:4px}
.fx .c{font-size:14px;line-height:1.6}
.fx .r{font-size:13px;color:var(--ink2);margin-top:4px}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{text-align:left;font-size:11px;letter-spacing:.09em;color:var(--dim);font-weight:600;
 padding:6px 9px;border-bottom:1px solid var(--line)}
.tbl td{padding:8px 9px;border-bottom:1px solid var(--line2);vertical-align:top;line-height:1.6}
.tbl tr:last-child td{border-bottom:0}
.tbl .mono{font-family:var(--mono);font-size:12.5px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:13px}
@media(max-width:680px){.two{grid-template-columns:1fr}}
.lab{font-size:11px;letter-spacing:.09em;color:var(--dim);margin-bottom:5px}
.btn{font:13px/1 inherit;padding:8px 13px;border:1px solid var(--line);border-radius:7px;
 background:var(--card);color:var(--ink2);cursor:pointer}
.btn:hover{border-color:var(--dim);color:var(--ink)}
.btn.p{background:var(--ink);color:#fff;border-color:var(--ink)}
.btn:focus-visible{outline:2px solid var(--seal);outline-offset:2px}
.gray{color:var(--dim)}
.mono{font-family:var(--mono)}
.hint{font-size:13px;color:var(--dim);line-height:1.7}
.big{display:flex;gap:11px;align-items:center;flex-wrap:wrap}
.recon-in{width:100%;font:13.5px/1.65 inherit;padding:10px 12px;border:1px solid var(--line);
 border-radius:7px;background:#fbfaf7;color:var(--ink);resize:vertical}
.recon-in:focus{outline:2px solid var(--seal);outline-offset:1px;background:#fff}
.empty{padding:44px 20px;text-align:center;color:var(--dim);font-size:14px}
footer{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);
 font-size:12.5px;color:var(--dim);line-height:1.9}
@media print{.nav,.toolbar{display:none}}
</style></head><body>
<header><div class="hdwrap">
 <div class="brand"><h1>底稿</h1><span class="sub">这一页只回答一件事:<b>这条我核到哪儿了 —— 包括我没核的部分</b>。<br>每个结论一份底稿,每个底稿一个号;<b>号变了,就是内容变了</b>。</span></div>
 <nav class="nav">
  <button data-v="list" class="on">档案流</button>
  <button data-v="num">数字查</button>
  <button data-v="recon">对账台</button>
  <button data-v="rules">规则集</button>
  <button data-v="mine">我的底稿</button>
 </nav>
</div></header>
<div class="wrap" id="app"></div>
<script>
const DATA = __DATA__;
const E = DATA.entries;
// ★ 号 → id:号是内容寻址,拿号就能直达一条(卡片上的号和这里的号同一套口径)
const NO2ID={}; E.forEach(function(e){NO2ID[e.no]=e.id;});

/* ── 编号：内容寻址。必须与 build_digao.py 的 FNV-1a32 完全一致 ── */
function fnv1a32(str){
  let h=2166136261;
  const b=new TextEncoder().encode(str);
  for(let i=0;i<b.length;i++){ h=Math.imul(h^b[i],16777619)>>>0; }
  return h>>>0;
}
function noFor(claim,quote){
  return (fnv1a32(claim+'\x00'+quote+'\x00'+DATA.ruleset.version)>>>0).toString(16).padStart(8,'0');
}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
const $=s=>document.querySelector(s);

/* ── 状态徽章 ── */
function badges(e){
  const b=[];
  if(e.uncovered) b.push('<span class="b b-unc">落在未覆盖区</span>');
  if(!e.lane_run) b.push('<span class="b b-norun">只跑了机械路</span>');
  if(e.findings.length) b.push('<span class="b b-fin">判据路 '+e.findings.length+' 条</span>');
  if(e.nums && e.nums.length) b.push('<span class="b b-num">口径 '+e.nums.length+' 条</span>');
  if(e.url) b.push('<span class="b b-link">有链接</span>');
  if(e.dual_disagree) b.push('<span class="b b-dis">双标注分歧</span>');
  return b.join(' ');
}

/* ★ S1:章从 1 维改成 2 维 —— 来源层 × 内容核验层
   ★ 关键:「未核验」必须显示成「未核验」,绝不能显示成「没问题」。
   ★ 一个只表示"有出处"的 ✓,长得像"核过了" —— 这是 15.4% 的不信任来源。 */
function stamp2d(e){
  const src = e.url
    ? '<span class="s2 ok">来源层 · 有出处</span>'
    : '<span class="s2 no">来源层 · 没出处</span>';
  let cont;
  if(e.uncovered){ cont='<span class="s2 none">内容核验层 · 未核验(机器路没看它)</span>'; }
  else if(!e.lane_run){ cont='<span class="s2 none">内容核验层 · 未核验(只跑了机械路)</span>'; }
  else if(e.dual_disagree){ cont='<span class="s2 warn">内容核验层 · 已核验,但两位标注员不一致</span>'; }
  else { cont='<span class="s2 ok">内容核验层 · 已核验</span>'; }
  return '<div class="stamp2d">'+src+'<br>'+cont+'</div>';
}

/* ── 屏 1：档案流 ── */
let state={q:'',f:'all'};
function listView(){
  const s=DATA.stat;
  const chips=[['all','全部'],['link','有链接'],['nums','有口径说明'],['unc','落在未覆盖区'],
              ['fin','有判据 finding'],['dis','双标注分歧'],['norun','内容未核验']];
  let rows=E.filter(e=>{
    if(state.f==='link'&&!e.url) return false;
    if(state.f==='nums'&&!(e.nums&&e.nums.length)) return false;
    if(state.f==='unc'&&!e.uncovered) return false;
    if(state.f==='fin'&&!e.findings.length) return false;
    if(state.f==='dis'&&!e.dual_disagree) return false;
    if(state.f==='norun'&&e.lane_run) return false;
    if(state.q){
      const q=state.q.toLowerCase();
      const hay=(e.id+' '+e.no+' '+e.claim+' '+e.note+' '+e.quote+' '+
                 (e.nums||[]).map(n=>n.n+' '+n.d).join(' ')).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
  const kpi=(lb,v,c)=>'<div class="kpi"><div class="lb">'+lb+'</div><div class="v '+(c||'')+'">'+v+'</div></div>';
  return '<div class="kpis">'
   +kpi('底稿',s.n_total,'s')
   +kpi('跑过判据路',s.n_lane_run,'s')
   +kpi('落在未覆盖区',s.n_uncovered,'o')
   +kpi('判据 finding',s.n_findings)
   +kpi('有口径说明',s.n_with_nums,'d')
   +kpi('双标注分歧',s.n_dual_disagree,'o')
   +'</div>'
   +'<div class="toolbar"><input type="search" id="q" placeholder="搜结论 / 原文 / 编号 / 数字 / 口径" value="'+esc(state.q)+'">'
   +'<div class="chips">'+chips.map(c=>'<button class="chip'+(state.f===c[0]?' on':'')+'" data-f="'+c[0]+'">'+c[1]+'</button>').join('')+'</div></div>'
   +(rows.length? '<div class="rows">'+rows.map(e=>
     '<div class="row" data-go="'+esc(e.id)+'">'
     +'<span class="no">'+esc(e.no)+'</span>'
     +'<div class="claim">'+esc(e.claim)
       +(e.note?'<span class="cm">'+esc(e.note.slice(0,60))+(e.note.length>60?'…':'')+'</span>':'')
       +'</div>'
     +'<div class="badges">'+badges(e)+'</div></div>').join('')+'</div>'
     : '<div class="rows"><div class="empty">没有匹配的底稿。</div></div>')
   +'<p class="hint" style="margin-top:12px">显示 '+rows.length+' / '+E.length+' 条。'
   +'其中「只跑了机械路」的 '+(DATA.stat.n_total-DATA.stat.n_lane_run)+' 条,大部分没进判据路 —— 它们<b>不是没问题,是没被查</b>。</p>';
}

/* ── 屏 2：单条详情 ── */
function detailView(id){
  const e=E.find(x=>x.id===id);
  if(!e) return '<div class="empty">没有这条底稿。<button class="btn" data-v="list">回档案流</button></div>';
  const laneOf=f=>'<div class="fx"><div class="lane">'+esc(f.lane)+'</div>'
    +(f.claim?'<div class="c">'+esc(f.claim)+'</div>':'')
    +(f.reason?'<div class="r">'+esc(f.reason)+'</div>':'')
    +(f.quote?'<div class="r mono" style="margin-top:6px">'+esc(f.quote)+'</div>':'')
    +'</div>';
  let h='<div class="toolbar"><button class="btn" data-v="list">← 回档案流</button>'
    +'<span class="gray">'+esc(e.id)+' · '+esc(e.day||'未入 daily 流水线')+'</span></div>'
   +'<div class="detail">'
   +'<div class="dh"><div class="no">'+esc(e.no)+'</div>'
   +'<h2>'+esc(e.claim)+'</h2>'
   +stamp2d(e)
   +'<div class="badges">'+badges(e)+'</div></div>';
  if(e.uncovered)
    h+='<div class="blk"><div class="warn"><b>这条落在未覆盖区</b> —— 机器路没查它。所以下面「判据路」是空的,'
      +'那意味着<b>没被查</b>,不是<b>没问题</b>。</div></div>';
  if(e.note)
    h+='<div class="blk"><h3>我自己的判断</h3><div class="note"><div class="lb">不参与核对</div>'+esc(e.note)+'</div></div>';
  h+='<div class="blk"><h3>逐字原文</h3><div class="qt">'+esc(e.quote||'（无）')+'</div>'
    +(e.url?'<p style="margin:10px 0 0;font-size:13.5px">出处：<a href="'+esc(e.url)+'" target="_blank" rel="noopener">'+esc(e.url)+'</a></p>'
      :'<p class="hint" style="margin:10px 0 0">这一条<b>没有链接</b> —— 没有出处,就只是一段说法。</p>')
    +'</div>';
  if(e.nums&&e.nums.length){
    h+='<div class="blk"><h3>口径说明（跟着数字一起存的,别让它丢）</h3><table class="tbl"><tr><th style="width:26%">数字</th><th>口径 / 来源</th></tr>'
      +e.nums.map(n=>'<tr><td class="mono">'+esc(n.n)+'</td><td>'+esc(n.d)+'</td></tr>').join('')+'</table></div>';
  }
  /* ★ 出处全文核验：把「查不了」和「不成立」分开。
     纪律：status!=ok（没抓到正文）时，只能说「查不了」，不能说「出处里没有」。 */
  const sc=e.src_check;
  if(sc){
    const stTxt={ok:'抓到了出处全文',stub:'只抓到空壳页（正文没拿到）',blocked:'被反爬挡了（403）',
                 timeout:'没抓到（超时/网络不通）',none:'没有链接'}[sc.status]||sc.status;
    const bTxt={hit:'查到',unit_mismatch:'表述/单位对不上，要人判',miss:'正文里没找到这个写法',
                unknown:'查不了（没抓到正文）',quoted:'引文已盖住'};
    let rows='';
    if((sc.nums||[]).length){
      rows='<table class="tbl"><tr><th style="width:26%">数字</th><th>出处全文核验</th></tr>'
        +sc.nums.map(n=>'<tr><td class="mono">'+esc(n.n)+'</td><td>'
          +'<span class="b '+(n.b==='hit'?'b-ok':n.b==='miss'?'b-bad':n.b==='unknown'?'b-dis':'b-dis')+'">'
          +esc(bTxt[n.b]||n.b)+'</span> <span class="gray">'+esc(n.ev||'')+'</span></td></tr>').join('')+'</table>';
    } else if(sc.status==='ok'){
      rows='<p class="hint">这条没有登记数字口径,没法用数字去核出处全文。</p>';
    }
    h+='<div class="blk"><h3>出处全文核验</h3>'
      +'<p class="hint" style="margin:0 0 10px">抓取状态：<b>'+esc(stTxt)+'</b>'
      +(sc.len?('　正文 '+sc.len+' 字符'+(sc.via?('　（'+esc(sc.via)+'）'):'')):'')
      +(sc.fetched_at?('　抓于 '+esc(sc.fetched_at)):'')+'</p>'
      +rows
      +(sc.status!=='ok'&&sc.status!=='none'
        ?'<div class="warn" style="margin-top:10px"><b>所以这里只能说「查不了」</b> —— 没拿到正文就不能说「出处里没有」。'
        +'把「没查到」说成「不存在」是这个体系反复强调不能犯的错。</div>':'')
      +(sc.status==='ok'&&(sc.nums||[]).some(n=>n.b==='miss')
        ?'<div class="warn" style="margin-top:10px">上面标「正文里没找到这个写法」的,<b>不等于出处里没有这个数</b>。'
        +'实测:同一个数在英文原文里写成 "8.2 million"、在中文原文里写成「三倍」、或单位不同(亿美元/亿加元),'
        +'都会被这一栏记成「没找到」。所以这一栏是<b>线索</b>,不是结论 —— 要判"没有",得人看过原页。</div>':'')
      +'</div>';
  }
  h+='<div class="blk"><h3>判据路（真实流水线跑出来的）</h3>'
    +(e.lane_run? (e.findings.length? e.findings.map(laneOf).join('')
        :'<p class="hint">跑过了,没报 finding。<b>但"没报"不等于"没问题"</b> —— 规则层抓的是「某个词没了」,抓不到「某个词还在但适用范围变了」。</p>')
      :'<p class="hint">这条<b>没跑过判据路</b>。它只跑过机械比对(数字对不对、实体词有没有)。</p>')
    +'</div>';
  if(e.flags&&e.flags.length){
    h+='<div class="blk"><h3>线索</h3>'+e.flags.map(f=>'<div class="fx"><div class="c">'+esc(f.claim)+'</div></div>').join('')+'</div>';
  }
  if(e.dual_a||e.dual_b){
    h+='<div class="blk"><h3>两个标注员各标一遍</h3><table class="tbl"><tr><th>标注员 1</th><th>标注员 2</th><th>一致吗</th></tr>'
      +'<tr><td>'+esc(e.dual_a||'—')+'</td><td>'+esc(e.dual_b||'—')+'</td>'
      +'<td>'+(e.dual_disagree?'<span class="b b-dis">分歧</span>':'一致')+'</td></tr></table></div>';
  }
  if(e.gt&&e.gt.length){
    h+='<div class="blk"><h3>人工真值（判为真问题）</h3>'+e.gt.map(g=>'<div class="fx"><div class="lane">'+esc(g.type)+'</div><div class="c">'+esc(g.desc)+'</div></div>').join('')+'</div>';
  }
  if(e.gt_unclear){
    h+='<div class="blk"><h3>人工复核</h3><div class="fx"><div class="c">'+esc(e.gt_unclear)+'</div></div></div>';
  }
  const same=E.filter(x=>x.id===e.id&&x.no!==e.no);
  h+='<div class="blk"><h3>这个号</h3>'
   +'<p class="hint" style="margin:0 0 9px">号 = 内容寻址：<span class="mono">'+esc(DATA.ruleset.version)
   +'｜结论｜原文</span> 的哈希。<b>内容一改,号就变。</b>所以"这条后来被改过没有"不用查版本表 —— 同一个 '
   +esc(e.id)+' 出现两个不同的号,就说明改过。</p>'
   +'<div class="big"><span class="no" style="font-size:13px">'+esc(e.no)+'</span>'
   +'<button class="btn" data-copy="'+esc(e.no)+'">复制号</button>'
   +'<button class="btn" data-dl="'+esc(e.id)+'">下载这条底稿 JSON</button>'
   +'<button class="btn" data-save="'+esc(e.id)+'">'+(mine().indexOf(e.id)>=0?'✓ 已在我的底稿':'存进我的底稿')+'</button>'
   +'<button class="btn" data-recon="'+esc(e.id)+'">拿去对账</button></div>'
   +(same.length? '<p class="hint" style="margin:11px 0 0">⚠ 这个 id 另有 '+same.length+' 个号：'
       +same.map(x=>esc(x.no)).join('、')+' —— <b>说明这条被改过</b>。</p>'
     : '<p class="hint" style="margin:11px 0 0">目前这个 id 只有一个号。<b>没有历史版本,不是"没被改过"</b> —— '
       +'只是还没有第二个号出现。</p>')
   +'</div></div>';
  return h;
}

/* ── 屏 3：数字查 ── */
let numq='';
function numView(){
  const q=numq.trim();
  let out='<div class="toolbar"><input type="search" id="nq" placeholder="输入一个数字或一段话,看它在哪些底稿里出现过" value="'+esc(numq)+'"></div>';
  if(!q){ out+='<div class="rows"><div class="empty">输入一个数字 —— 比如 <span class="mono">8.6%</span>、<span class="mono">870 million</span>、<span class="mono">37</span>。<br>'
    +'这是给"我 PPT 里那个数,是谁给的、后来改过没有"准备的。</div></div>'; return out; }
  const ql=q.toLowerCase();
  const hits=E.filter(e=>{
    const hay=[e.claim,e.note,e.quote,e.id,e.no].concat((e.nums||[]).map(n=>n.n+' '+n.d)).join(' ').toLowerCase();
    return hay.includes(ql);
  });
  out+='<div class="rows">'+(hits.length? hits.map(e=>{
    const nums=(e.nums||[]).filter(n=>(n.n+' '+n.d).toLowerCase().includes(ql));
    return '<div class="row" data-go="'+esc(e.id)+'"><span class="no">'+esc(e.no)+'</span>'
      +'<div class="claim">'+esc(e.claim)
      +(nums.length?'<span class="cm">'+nums.map(n=>esc(n.n)+' —— '+esc(n.d)).join('；')+'</span>':'')
      +'</div><div class="badges">'+badges(e)+'</div></div>';
  }).join('') : '<div class="empty">没找到。</div>')+'</div>';
  out+='<p class="hint" style="margin-top:12px">命中 '+hits.length+' 条底稿。'
    +'<b>同一个数在几条底稿里出现、口径不一样 —— 那才是要盯的地方。</b></p>';
  return out;
}

/* ── 屏 4：对账台 ── */
let rc={claim:'',quote:'',res:null};
function reconView(){
  const r=rc.res;
  let out='<p class="hint" style="margin:0 0 13px">贴一段<b>结论</b>和一段<b>逐字原文</b>,本地算一个号。'
    +'号跟档案里的对上了,就说明这份底稿在你手里没被改过;对不上,说明内容跟档案里那份不一样。</p>'
   +'<div class="two" style="margin-bottom:12px">'
   +'<div><div class="lab">结论</div><textarea class="recon-in" id="rc-claim" rows="4" placeholder="例：某模型完成 8.7 亿美元 A 轮，估值 75 亿">'+esc(rc.claim)+'</textarea></div>'
   +'<div><div class="lab">逐字原文</div><textarea class="recon-in" id="rc-quote" rows="4" placeholder="例：TypeSafe Inc. ... raised $870 million in funding at a $7.5 billion valuation.">'+esc(rc.quote)+'</textarea></div>'
   +'</div><button class="btn p" id="rc-go">算号并对账</button>';
  if(r){
    out+='<div class="detail" style="margin-top:15px"><div class="dh">'
      +'<div class="no">'+esc(r.no)+'</div>'
      +'<h2 style="font-size:19px">'+(r.hit?'对上了 —— 档案里就有这一份':'档案里没有这一份')+'</h2>'
      +'<p class="hint" style="margin:0">'
      +(r.hit? '匹配到 <b>'+esc(r.hit.id)+'</b>（号 <span class="mono">'+esc(r.hit.no)+'</span>）。'
               +'内容和档案里那份<b>逐字一致</b>。'
        : '这个号不在档案里。两种可能：<b>这是新的一条</b>，或者<b>它跟档案里那条不一样</b>（被改过、或从来不是同一份）。')
      +'</p></div></div>';
  }
  return out;
}
function doRecon(){
  const c=$('#rc-claim').value.trim(), q=$('#rc-quote').value.trim();
  rc.claim=c; rc.quote=q;
  if(!c||!q){ rc.res={no:'—',hit:null,err:'结论和原文都要填'}; render(); return; }
  const no=noFor(c.split('\n')[0].trim(),q);
  const hit=E.find(e=>e.no===no);
  rc.res={no,hit:hit||null};
  render();
}

/* ── 屏 6：我的底稿 ── */
function mine(){ try{ return JSON.parse(localStorage.getItem('digao.mine')||'[]'); }catch(e){ return []; } }
function setMine(a){ try{ localStorage.setItem('digao.mine',JSON.stringify(a)); }catch(e){} }
function mineView(){
  const ids=mine();
  const es=E.filter(e=>ids.indexOf(e.id)>=0);
  const refs=0;   // ★ 引用数目前真的是 0 —— 还没有别人引用过
  return '<div class="kpis" style="grid-template-columns:repeat(3,1fr)">'
   +'<div class="kpi"><div class="lb">我存过的底稿</div><div class="v s">'+es.length+'</div></div>'
   +'<div class="kpi"><div class="lb">我的号被引用</div><div class="v o">'+refs+'</div></div>'
   +'<div class="kpi"><div class="lb">存了但没跑判据路的</div><div class="v d">'+es.filter(e=>!e.lane_run).length+'</div></div>'
   +'</div>'
   +(es.length? '<div class="rows">'+es.map(e=>
       '<div class="row" data-go="'+esc(e.id)+'"><span class="no">'+esc(e.no)+'</span>'
       +'<div class="claim">'+esc(e.claim)+'</div><div class="badges">'+badges(e)+'</div></div>').join('')+'</div>'
     : '<div class="rows"><div class="empty">还没存过。<br>核完一条,在详情页点「存进我的底稿」。<br>'
       +'<span class="gray">存了之后,它就一直在 —— 这是这个产品唯一能积累的东西。</span></div></div>')
   +'<p class="hint" style="margin-top:13px">'
   +'<b>「我的号被引用 0 次」是真的 0</b> —— 目前还没有人引用过谁的号。'
   +'这个数字要靠别人把你的号贴进自己的卡里才会涨。'
   +'<br><b>★ 这就是「持续关注」的真实机制:</b>不是靠你天天更新内容,是靠<b>你的号被别人用</b>。'
   +'内容型产品靠 DAU,这个靠<b>被引用次数</b>。</p>'
   +'<div class="big" style="margin-top:12px"><button class="btn" data-mineexport="1">导出我的底稿 JSON</button>'
   +'<button class="btn" data-mineclear="1">清空</button></div>';
}

/* ── 屏 5：规则集 ── */
function rulesView(){
  const r=DATA.ruleset;
  return '<div class="detail"><div class="dh"><div class="no">'+esc(r.version)+'</div>'
   +'<h2>判定用的是哪套规则</h2>'
   +'<p class="hint" style="margin:0">号里含规则版本号 —— 换规则,号就变。所以号不只标内容,也标了<b>用什么尺子量的</b>。</p></div>'
   +'<div class="blk"><h3>校验和（sha256）</h3><div class="qt">'+esc(r.sha256)+'</div>'
   +'<div class="big" style="margin-top:11px"><button class="btn" data-copy="'+esc(r.sha256)+'">复制校验和</button>'
   +'<button class="btn" data-dlrule="1">下载规则集</button></div></div>'
   +'<div class="blk"><h3>三条判据路</h3><table class="tbl">'
   +'<tr><th style="width:22%">路</th><th>查什么</th></tr>'
   +'<tr><td>N 数字无出处</td><td>转述里的数字,原文里找不到</td></tr>'
   +'<tr><td>S 限定与口径</td><td>原文的地域/人群/榜单/时间窗被丢掉或放大</td></tr>'
   +'<tr><td>T 主体与术语</td><td>说的人和原文说的不是同一件事</td></tr></table>'
   +'<p class="hint" style="margin:11px 0 0"><b>规则层抓的是「某个词没了」,抓不到「某个词还在但适用范围变了」。</b>'
   +'所以"没报 finding"不等于"没问题"。</p></div>'
   +'<div class="blk"><h3>每条都要人看的 3 类</h3><ol style="margin:0;padding-left:1.3em;font-size:14px">'
   +'<li>结论比证据强多少 —— 要人判</li><li>适用范围有没有被放大（地域/人群/榜单/时间窗）</li>'
   +'<li>有没有把两件并列的事说成因果</li></ol>'
   +'<p class="hint" style="margin:11px 0 0">这 3 类<b>每条都一样</b> —— 是这台机器原理上核不了的,不是某条结论的扣分项。</p></div>'
   +'<div class="blk"><h3>怎么重跑</h3><ol style="margin:0;padding-left:1.3em;font-size:14px;line-height:1.9">'
   +'<li>下载这条底稿的 JSON（结论 / 原文 / 编号）</li>'
   +'<li>下载规则集（带版本号和校验和）</li>'
   +'<li>对 <span class="mono">'+esc(r.version)+'</span> 这套规则重跑一遍</li>'
   +'<li>算出来的号跟底稿上的号一致 → 这份没被改过</li></ol></div></div>';
}

/* ── 渲染 ── */
let view='list', cur='';
function render(){
  const app=$('#app');
  let h='';
  if(view==='list') h=listView();
  else if(view==='detail') h=detailView(cur);
  else if(view==='num') h=numView();
  else if(view==='recon') h=reconView();
  else if(view==='rules') h=rulesView();
  else if(view==='mine') h=mineView();
  app.innerHTML=h;
  document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('on',b.dataset.v===view));
}
document.addEventListener('click',function(ev){
  const t=ev.target.closest('[data-v],[data-go],[data-f],[data-copy],[data-dl],[data-dlrule],[data-recon]');
  if(ev.target.id==='rc-go'){ doRecon(); return; }
  if(!t) return;
  if(t.dataset.v){ location.hash=(t.dataset.v==='list')?'#/':'#/'+t.dataset.v; return; }
  if(t.dataset.f){ state.f=t.dataset.f; render(); return; }
  if(t.dataset.go){ location.hash='#/e/'+t.dataset.go; return; }
  if(t.dataset.copy){ navigator.clipboard&&navigator.clipboard.writeText(t.dataset.copy);
    const o=t.textContent; t.textContent='已复制 ✓'; setTimeout(function(){t.textContent=o},1300); return; }
  if(t.dataset.dl){
    const e=E.find(x=>x.id===t.dataset.dl);
    dl('底稿-'+e.id+'.json',JSON.stringify(e,null,1)); return;
  }
  if(t.dataset.dlrule){ dl('规则集-'+DATA.ruleset.version+'.json',DATA.ruleset.body); return; }
  if(t.dataset.save){
    const id=t.dataset.save, a=mine();
    if(a.indexOf(id)>=0){ const k=a.indexOf(id); a.splice(k,1); } else { a.push(id); }
    setMine(a); render(); return;
  }
  if(t.dataset.mineexport){
    const ids=mine();
    dl('我的底稿-'+ids.length+'条.json',JSON.stringify(E.filter(e=>ids.indexOf(e.id)>=0),null,1)); return;
  }
  if(t.dataset.mineclear){ setMine([]); render(); return; }
  if(t.dataset.recon){ view='recon'; rc={claim:E.find(x=>x.id===t.dataset.recon).claim,quote:E.find(x=>x.id===t.dataset.recon).quote,res:null};
    render(); return; }
});
function dl(name,body){
  const a=document.createElement('a');
  a.download=name; a.href='data:application/json;charset=utf-8,'+encodeURIComponent(body);
  document.body.appendChild(a); a.click(); a.remove();
}
document.addEventListener('input',function(ev){
  if(ev.target.id==='q'){ state.q=ev.target.value; const p=ev.target.selectionStart; render();
    const n=$('#q'); if(n){n.focus(); n.setSelectionRange(p,p);} return; }
  if(ev.target.id==='nq'){ numq=ev.target.value; const p=ev.target.selectionStart; render();
    const n=$('#nq'); if(n){n.focus(); n.setSelectionRange(p,p);} return; }
});
function fromHash(){
  const h=location.hash||'';
  if(h.startsWith('#/e/')){ view='detail'; cur=h.slice(4); }
  else if(h.startsWith('#/go/')){
    const no=h.slice('#/go/'.length), id=NO2ID[no];   // ★ 按前缀长度切,别写死 4 —— '#/go/' 是 5 个字符
    // ★ 号没收录 → 回列表并把它当搜索词(不静默失败,也不假装有这条)
    if(id){ view='detail'; cur=id; } else { view='list'; state.q=no; }
  }
  else if(h.startsWith('#/num')){ view='num'; }
  else if(h.startsWith('#/recon')){ view='recon'; }
  else if(h.startsWith('#/rules')){ view='rules'; }
  else if(h.startsWith('#/mine')){ view='mine'; }
  else { view='list'; }
  render();
}
window.addEventListener('hashchange',fromHash);
// ★ ?no=<号>：二维码里带的就是这个。query 参数扛得住重定向追加的参数（微信会加 tracking 参数），hash 片段扛不住
const qno=new URLSearchParams(location.search).get('no');
if(qno && NO2ID[qno]) location.hash='#/e/'+NO2ID[qno];
fromHash();
</script></body></html>'''

open(OUT, 'w', encoding='utf-8').write(HTML.replace('__DATA__', json.dumps(DATA, ensure_ascii=False)))
print('已生成 %s (%.1f KB)' % (OUT, os.path.getsize(OUT) / 1024))
print('条目 %d | 跑过判据路 %d | 未覆盖 %d | finding %d | 有口径 %d | 分歧 %d'
      % (DATA['stat']['n_total'], DATA['stat']['n_lane_run'], DATA['stat']['n_uncovered'],
         DATA['stat']['n_findings'], DATA['stat']['n_with_nums'], DATA['stat']['n_dual_disagree']))
