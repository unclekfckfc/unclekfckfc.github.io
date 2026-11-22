#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《底稿》—— 结论可查的地方。

单文件、零外链、离线可用。
数据全部来自真实流水线产物,不在这里重算判定:
  · daily/2026-*/pairs.json      结论 + 逐字原文 + 链接 + 编号口径
  · daily/2026-*/lanes/{N,S,T}.json   三条判据路的真实 finding
  · daily/2026-*/lanes/flags.json      线索
  · daily/2026-*/lanes/uncovered.json  落在未覆盖区的
  · eval3/cases/all82_pairs.json       82 条真实材料全集
  · eval3/cases/dual_label_82.json     双人工标注
  · eval3/cases/ground_truth.json      人工真值

编号规则:内容寻址。no = FNV-1a32(结论 + 原文 + 规则版本)
  ⇒ 同一份内容永远是同一个号;内容一改,号就变
  ⇒ 「这个数后来被改过没有」不需要额外的版本表,查号就知道
"""
import json, glob, os, hashlib, html as H

BASE = '/workspace/tmpwork/h2b/handoff-2026-11-02'
DAILY = os.path.join(BASE, '10-skills', 'claim-audit', 'data', 'daily')
CASES = '/workspace/output/eval3/cases'
OUT = '/workspace/output/底稿-结论可查的地方.html'

RULESET_VERSION = 'guard-2026.11.02'
RULESET_SHA = None   # 下面算


def fnv1a32(s: str) -> int:
    h = 2166136261
    for b in s.encode('utf-8'):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def no_for(claim: str, quote: str) -> str:
    return '%08x' % fnv1a32(claim + '\x00' + quote + '\x00' + RULESET_VERSION)


def load(p, default=None):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


# ── 1. 82 条全集 ──
PAIRS = load(os.path.join(CASES, 'all82_pairs.json'), [])
_D = load(os.path.join(CASES, 'dual_label_82.json'), {}) or {}
DUAL_A = _D.get('annotator1', {}) or {}
DUAL_B = _D.get('annotator2', {}) or {}
DUAL_DISAGREE = set(_D.get('disagree', []) or [])
DUAL_BOTH_DIRTY = set(_D.get('both_dirty', []) or [])
DUAL_BOTH_CLEAN = set(_D.get('both_clean', []) or [])
_G = load(os.path.join(CASES, 'ground_truth.json'), {}) or {}
GT_BY = {}
for g in (_G.get('findings', []) or []):
    GT_BY.setdefault(g['id'], []).append(g)
GT_UNCLEAR = {}
for g in (_G.get('unclear', []) or []):
    GT_UNCLEAR[g['id']] = g.get('desc', '')

# ── 2. daily 流水线的真实产物 ──
daily = {}          # id -> {n,s,t,flags,uncovered,day}
for d in sorted(os.path.basename(x) for x in glob.glob(os.path.join(DAILY, '20*'))):
    L = os.path.join(DAILY, d, 'lanes')
    if not os.path.isdir(L):
        continue
    P = load(os.path.join(DAILY, d, 'pairs.json'), [])
    P = P.get('pairs', P) if isinstance(P, dict) else P
    fl = load(os.path.join(L, 'flags.json'), [])
    fl = fl if isinstance(fl, list) else [fl]
    un = load(os.path.join(L, 'uncovered.json'), {})
    # ★ 按 id 分组：finding 自带 id，按天整批挂会把别的条目的判定扣到这条头上
    lanes = {}
    for ln in ('N', 'S', 'T'):
        j = load(os.path.join(L, ln + '.json'), {})
        by = {}
        for f in j.get('findings', []):
            by.setdefault(f.get('id'), []).append(f)
        lanes[ln] = by
    flags_by = {}
    for f in fl:
        for it in f.get('items', []):
            flags_by.setdefault(it.get('id'), []).append(it)
    for p in P:
        i = p['id']
        daily[i] = {
            'day': d,
            'file': p.get('file'),
            'url': p.get('url'),
            'nums': p.get('nums', []),
            'n': lanes['N'].get(i, []),
            's': lanes['S'].get(i, []),
            't': lanes['T'].get(i, []),
            'flags': flags_by.get(i, []),
            'uncovered': i in set(un.get('uncovered', [])),
            'flag_labels': [f.get('flag', '') for f in fl],
        }

# ── 3. 组装条目 ──
entries = []
for p in PAIRS:
    i = p['id']
    lines = (p.get('transmitted') or '').split('\n')
    claim = lines[0].strip()
    note = '\n'.join(lines[1:]).strip()
    quote = p.get('original') or ''
    d = daily.get(i)
    findings = []
    if d:
        for ln, name in (('n', '数字无出处'), ('s', '限定与口径'), ('t', '主体与术语')):
            for f in d[ln]:
                findings.append({
                    'lane': name,
                    'claim': f.get('claim', ''),
                    'reason': f.get('reason', ''),
                    'quote': f.get('quote', ''),
                })
    flags = []
    for f in (d['flags'] if d else []):
        flags.append({'claim': f.get('claim', ''), 'id': f.get('id', '')})
    gt = GT_BY.get(i, [])
    entries.append({
        'id': i,
        'no': no_for(claim, quote),
        'claim': claim,
        'note': note,
        'quote': quote,
        'url': (d or {}).get('url'),
        'nums': (d or {}).get('nums', []),
        'day': (d or {}).get('day'),
        'lane_run': bool(d),                       # 有没有跑过判据路
        'findings': findings,
        'flags': flags,
        'uncovered': bool(d and d['uncovered']),   # 落在未覆盖区
        'dual_a': DUAL_A.get(i),                  # 标注员 1
        'dual_b': DUAL_B.get(i),                  # 标注员 2
        'dual_disagree': i in DUAL_DISAGREE,
        'gt': gt,
        'gt_unclear': GT_UNCLEAR.get(i, ''),
    })

# daily 里那 30 条有的不在 82 条里（id-0133 等）—— 补进来
for i, d in daily.items():
    if any(e['id'] == i for e in entries):
        continue
    P = load(os.path.join(DAILY, d['day'], 'pairs.json'), [])
    P = P.get('pairs', P) if isinstance(P, dict) else P
    p = next((x for x in P if x['id'] == i), None)
    if not p:
        continue
    lines = (p.get('transmitted') or '').split('\n')
    claim = lines[0].strip(); note = '\n'.join(lines[1:]).strip()
    quote = p.get('original') or ''
    fs = []
    for ln, name in (('n', '数字无出处'), ('s', '限定与口径'), ('t', '主体与术语')):
        for f in d[ln]:
            fs.append({'lane': name, 'claim': f.get('claim', ''), 'reason': f.get('reason', ''), 'quote': f.get('quote', '')})
    entries.append({
        'id': i, 'no': no_for(claim, quote), 'claim': claim, 'note': note, 'quote': quote,
        'url': p.get('url'), 'nums': p.get('nums', []), 'day': d['day'], 'lane_run': True,
        'findings': fs, 'flags': [{'claim': f.get('claim', ''), 'id': f.get('id', '')} for f in d['flags']],
        'uncovered': d['uncovered'], 'dual_a': DUAL_A.get(i), 'dual_b': DUAL_B.get(i),
        'dual_disagree': i in DUAL_DISAGREE, 'gt': GT_BY.get(i, []), 'gt_unclear': GT_UNCLEAR.get(i, ''),
    })

# 档案按时间倒序（新的在前）；没入 daily 的按 id 排在后面
entries.sort(key=lambda e: (e['day'] or '0000-00-00', e['id']), reverse=True)

# ── 4. 规则集：真版本号 + 真校验和 + 可下载 ──
rs = json.dumps({
    'version': RULESET_VERSION,
    'lanes': ['N 数字无出处', 'S 限定与口径', 'T 主体与术语'],
    'todos': ['结论比证据强多少 —— 要人判',
              '适用范围有没有被放大（地域/人群/榜单/时间窗）',
              '有没有把两件并列的事说成因果'],
    'note': '判定口径见下方「怎么重跑」',
}, ensure_ascii=False, sort_keys=True, indent=1)
RULESET_SHA = hashlib.sha256(rs.encode('utf-8')).hexdigest()

# ── 5. 统计（全部可从上面推出来） ──
stat = {
    'n_total': len(entries),
    'n_lane_run': sum(1 for e in entries if e['lane_run']),
    'n_uncovered': sum(1 for e in entries if e['uncovered']),
    'n_findings': sum(len(e['findings']) for e in entries),
    'n_with_url': sum(1 for e in entries if e['url']),
    'n_with_nums': sum(1 for e in entries if e['nums']),
    'n_dual_dirty': sum(1 for e in entries if e['dual_a'] == 'DIRTY' and e['dual_b'] == 'DIRTY'),
    'n_dual_unclear': sum(1 for e in entries if e['dual_a'] == 'UNCLEAR' and e['dual_b'] == 'UNCLEAR'),
    'n_dual_clean': sum(1 for e in entries if e['dual_a'] == 'CLEAN' and e['dual_b'] == 'CLEAN'),
    'n_dual_disagree': sum(1 for e in entries if e['dual_disagree']),
    'n_gt': sum(1 for e in entries if e['gt'] or e['gt_unclear']),
    'n_no_url': sum(1 for e in entries if not e['url']),
}

DATA = {
    'entries': entries,
    'stat': stat,
    'ruleset': {'version': RULESET_VERSION, 'sha256': RULESET_SHA, 'body': rs},
    'generated_at': '2026-11-03',
    'source': '「核材料」daily 流水线产物 + 82 条真实材料全集',
}

print('条目 %d 条 | 跑过判据路 %d | 落在未覆盖区 %d | 判据 finding %d 条 | 有链接 %d | 有口径说明 %d'
      % (stat['n_total'], stat['n_lane_run'], stat['n_uncovered'], stat['n_findings'],
         stat['n_with_url'], stat['n_with_nums']))
print('双标注 DIRTY %d / UNCLEAR %d / CLEAN %d | 有真值 %d'
      % (stat['n_dual_dirty'], stat['n_dual_unclear'], stat['n_dual_clean'], stat['n_gt']))
print('规则集 %s  sha256 %s' % (RULESET_VERSION, RULESET_SHA[:16]))
# ★ 合并出处全文核验结果 —— 存在独立文件里,按 no 索引
#   （直接写进 digao_data.json 会被这次重建冲掉 —— 我踩过）
try:
    V = load('/workspace/output/eval3/source_verdicts.json', {}) or {}
except Exception:
    V = {}
for e in entries:
    e['src_check'] = V.get(e['no'], {'status': 'none', 'len': 0, 'via': '', 'nums': []})
n_vc = sum(1 for e in entries if e['src_check'].get('status') != 'none')
print('出处全文核验:合并 %d 条（有链接的）' % n_vc)

json.dump(DATA, open('/workspace/output/eval3/digao_data.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('数据已就绪 → eval3/digao_data.json')
