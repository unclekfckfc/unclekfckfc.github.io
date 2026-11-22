#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「出处全文核验结果」注入核验卡(单文件 HTML,零外链)。

跑法: python3 eval3/inject_src_verdict.py

注入两套索引:
  n    —— 号 → {数字原文: 桶}          （精确匹配用）
  core —— 号 → {数字主体: [桶,...]}    （卡里的正则只吃一个单位字,"205 亿美元"会被抽成"205亿" ⇒ 必须再按主体兜一层）

★ 只收 status=='ok' 的条目 —— 没抓到正文的绝不能进表,否则卡就会说出处里没有。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = '/workspace/output'
CARD = os.path.join(OUT, '核验卡-朋友圈版-原型.html')
DATA = os.path.join(HERE, 'digao_data.json')
RULESET = 'guard-2026.11.02'


def fnv(s):
    h = 2166136261
    for b in s.encode('utf-8'):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF   # ★ FNV-1a 32 的素数是 16777619（抄错成 16776719 会让所有查表静默失灵）
    return h


def no_for(c, q):
    return '%08x' % fnv(c + '\x00' + q + '\x00' + RULESET)


def core(s):
    m = re.search(r'-?[0-9]+(?:\.[0-9]+)?', str(s).replace(',', '').replace('％', '%'))
    return m.group(0) if m else None


def main():
    d = json.load(open(DATA, encoding='utf-8'))
    # ★ 自检:算出来的号必须落在底稿自己的号集合里。
    #   哈希常数抄错一位不会报错,只会让所有查表静默失灵 —— 所以必须在这里喊出来。
    own = {e['no'] for e in d['entries']}
    bad = []
    for e in d['entries']:
        fp = no_for(e['claim'], e.get('quote') or '')
        if fp != e['no']:
            bad.append('%s: 算得 %s / 自带 %s' % (e['id'], fp, e['no']))
    if bad:
        print('✗ 号算不出来 —— 哈希口径对不上（%d 条）。第一条：%s' % (len(bad), bad[0]))
        print('  典型原因：FNV-1a 的素数写成 16776719（应为 16777619），或结论/原文取了不同的行。')
        sys.exit(1)
    print('✓ 号口径自检通过（%d 条）' % len(own))
    ver = {}
    for e in d['entries']:
        sc = e.get('src_check') or {}
        if sc.get('status') != 'ok' or not e.get('nums'):
            continue
        fp = no_for(e['claim'], e.get('quote') or '')
        nmap = {x['n']: x['b'] for x in sc.get('nums', [])}
        cmap = {}
        for name, b in nmap.items():
            c = core(name)
            if c:
                cmap.setdefault(c, [])
                if b not in cmap[c]:
                    cmap[c].append(b)
        ver[fp] = {'st': 'ok', 'n': nmap, 'core': cmap}
    js = ('/* ★ 出处全文核验结果（只收抓到正文的条目；没抓到的一律不进这张表 —— '
          '不能拿"没抓到"说"没有"） */\nconst SRC_VERDICT='
          + json.dumps(ver, ensure_ascii=False, separators=(',', ':')) + '\n')

    s = open(CARD, encoding='utf-8').read()
    # 替换掉旧的那一块（如果有）
    s2 = re.sub(r'/\* ★ 出处全文核验结果.*?\nconst SRC_VERDICT=.*?\n', '', s, flags=re.S)
    anchor = "P82.forEach(function(x){ const l=x.t.split('\\n'); P82_INDEX[noFor(l[0].trim(),x.o)]=x.i; });"
    assert anchor in s2, '找不到 P82_INDEX 锚点'
    s2 = s2.replace(anchor, anchor + '\n' + js, 1)
    open(CARD, 'w', encoding='utf-8').write(s2)
    print('✓ 注入 %d 个号的出处全文核验结果（核心索引 %d 项）'
          % (len(ver), sum(len(v['core']) for v in ver.values())))


if __name__ == '__main__':
    main()
