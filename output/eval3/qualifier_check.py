#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""限定词体检器 —— 投资叙事里最致命的一档失真:把上限说成定值。

★ 起源:真值库 id-0053 的 note
  「原文『计划筹集最高 1000 亿美元资金』的上限口径『最高』被抹,
    转述写成『拟向海湾金主募 1000 亿美元』,把上限说成定值。」

★ 为什么这比数字对不对更致命:
  数字对不对 ⇒ 精确率/召回率能测
  限定词在不在 ⇒ **规则层根本不看**,而它恰恰是投资叙事里最常见的失真
  ⇒ 任何"投资观点可核验"的产品,**第一件该做的事就是查限定词还在不在**

检测口径(严格版,宁可漏不可错):
  原文里出现了限定词 → 转述里该限定词**必须**还在(或落在允许的等价替换表里)
  消失 ⇒ 报一条「限定词丢失」

用法:
    python3 qualifier_check.py                 # 全语料跑 + 打印
    python3 qualifier_check.py --pair file.json
    python3 qualifier_check.py --json
"""
import json, os, re, sys, glob, collections, datetime

TRUTH = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/truth'
PAIRS = '/workspace/output/eval3/cases/all82_pairs.json'
DAILY = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/daily'

# ── 限定词分类 ──
# ★ 每个词标了 severity:限定词丢失的严重程度
#   cap   = 上限类(最高/最多/不超过) —— 丢它 = 把上限说成定值,最致命
#   approx= 约数类(约/超过)          —— 丢它 = 把估计说成事实
#   plan  = 计划类(计划/拟/预计)      —— 丢它 = 把"打算做"说成"做了"
CAP = ['最高', '最多', '不超过', '至多', '上限', '不超过', '最多可达', '最高可达', '不超过约', '不超过']
APPROX = ['约', '大约', '左右', '接近', '将近', '逾', '超过', '逾', '超出', '近']
PLAN = ['计划', '拟', '预计', '有望', '目标', '拟于', '预计将', '有望达到', '力争', '计划于']
# 允许的等价替换(丢了一个但意思没丢,不算失真)
ALIAS = {
    '最高': ['最多', '上限', '至多'], '最多': ['最高', '上限', '至多'],
    '不超过': ['至多', '最多', '最高'], '至多': ['不超过', '最多'],
    '上限': ['最高', '最多', '至多'], '最高可达': ['最多可达', '最高'],
    '约': ['大约', '左右', '将近', '接近'], '大约': ['约', '左右'],
    '左右': ['约', '大约'], '将近': ['约', '接近'], '接近': ['约', '将近'],
    '逾': ['超过', '超出'], '超过': ['逾', '超出'], '超出': ['超过', '逾'],
    '近': ['约', '接近'],
    '计划': ['拟', '预计', '力争', '目标'], '拟': ['计划', '预计'],
    '预计': ['有望', '计划', '拟'], '有望': ['预计'], '目标': ['计划', '力争'],
}
ALL = CAP + APPROX + PLAN
RE_CAP = re.compile('|'.join(sorted(set(CAP), key=len, reverse=True)))
RE_APPROX = re.compile('|'.join(sorted(set(APPROX), key=len, reverse=True)))
RE_PLAN = re.compile('|'.join(sorted(set(PLAN), key=len, reverse=True)))


def kind_of(w):
    if w in CAP:
        return 'cap'
    if w in APPROX:
        return 'approx'
    return 'plan'


def check(quote, claim):
    """原文有限定词 → 转述必须还有(或等价替换)。返回丢失列表。"""
    out = []
    for w in set(RE_CAP.findall(quote)) | set(RE_APPROX.findall(quote)) | set(RE_PLAN.findall(quote)):
        if w in claim:
            continue
        # 等价替换:转述里有它的同义组 ⇒ 意思没丢
        if any(a in claim for a in ALIAS.get(w, [])):
            continue
        out.append((w, kind_of(w)))
    return sorted(out, key=lambda x: {'cap': 0, 'approx': 1, 'plan': 2}[x[1]])


def load_pairs():
    out = list(json.load(open(PAIRS, encoding='utf-8')))
    for day in sorted(glob.glob(os.path.join(DAILY, '20*'))):
        f = os.path.join(day, 'pairs.json')
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding='utf-8'))
        for p in (d.get('pairs', d) if isinstance(d, dict) else d):
            if not any(x['id'] == p['id'] for x in out):
                out.append(dict(p))
    return out


def main():
    pairs = load_pairs()
    now = datetime.datetime.now().replace(microsecond=0).isoformat()
    rows = []
    for p in pairs:
        quote = p.get('original') or ''
        claim = (p.get('transmitted') or '').split('\n')[0]
        lost = check(quote, claim)
        if lost:
            rows.append({'id': p['id'], 'claim': claim[:90], 'quote': quote[:110],
                         'lost': [{'word': w, 'kind': k} for w, k in lost]})
    n = len(pairs)
    kinds = collections.Counter(k for r in rows for k in [x['kind'] for x in r['lost']])
    cap_n = sum(1 for r in rows if any(x['kind'] == 'cap' for x in r['lost']))
    out = {
        'as_of': now, 'n_materials': n,
        'n_with_lost_qualifier': len(rows),
        'rate': round(len(rows) / n, 4) if n else None,
        'denominator': n,
        'by_kind': dict(kinds),
        'n_with_cap_lost': cap_n,
        'cap_rate': round(cap_n / n, 4) if n else None,
        'rows': rows,
    }
    json.dump(out, open('/workspace/output/eval3/qualifier_check.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    if '--json' in sys.argv:
        print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
        return 0

    print('═══ 限定词体检 @ %s ═══' % now)
    print('  语料 %d 条真实材料\n' % n)
    print('  限定词丢失          %d 条  (%.1f%%)  分母 = %d'
          % (len(rows), 100 * len(rows) / n, n))
    print('  ├ 上限类(cap)丢失   %d 条  (%.1f%%)  ← 最致命:把上限说成定值'
          % (cap_n, 100 * cap_n / n))
    print('  ├ 约数类(approx)丢失 %d 条' % kinds.get('approx', 0))
    print('  └ 计划类(plan)丢失  %d 条  ← 把"打算做"说成"做了"' % kinds.get('plan', 0))
    print('\n  ★ 逐条:')
    for r in sorted(rows, key=lambda x: [k for k in ('cap', 'approx', 'plan') if any(y['kind'] == k for y in x['lost'])][0]):
        words = '/'.join('%s(%s)' % (x['word'], x['kind']) for x in r['lost'])
        print('  %-10s 丢 %-28s %s' % (r['id'], words, r['claim'][:52]))
    print('\n  清单: /workspace/output/eval3/qualifier_check.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
