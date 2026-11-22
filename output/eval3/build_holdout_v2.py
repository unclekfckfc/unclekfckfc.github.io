#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""留出集 v2 —— 按 experimental-design 的结构切分,而不是随手抽。

它解决三个结构缺陷:
  ① 伪重复:单位必须是"一条材料",且 n 按**已知真问题条数**算,不是材料条数
  ② 没块化:按 (verdict × 信源语种 × 判定分片) 分层,层内随机抽,避免批次混淆
  ③ 冻结只防写不防看:冻结清单 + 独立复算脚本双验 + 列出"可能已被调参污染、待人工确认"的 id

★ 诚实前提(不要跳过):
  现有真值池 **已知真问题只有 32 条**(122 唯一 id 里)。
  ⇒ 即便全放进留出集,n=32 也只能支撑"小幅退化"的检测,撑不起"准"的证明。
  ⇒ 脚本会现场算这个账,并给出"要达到 n=15 已知真问题,还差多少新材料"。

用法:
    python3 build_holdout_v2.py            # 切分 + 打印设计账
    python3 build_holdout_v2.py --verify   # 独立复算(不看切分结果,重数一遍)
"""
import json, os, re, glob, random, hashlib, collections, datetime, sys

TRUTH = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/truth'
PAIRS = '/workspace/output/eval3/cases/all82_pairs.json'
DAILY = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/daily'
OUT = '/workspace/output/eval3/holdout_v2.json'
SEED = 20261110

# 旧留出集(已冻结并被守卫保护)—— 必须排除
OLD_HOLDOUT = {'id-0133', 'id-0134', 'id-0135', 'id-0136', 'id-0137', 'id-0138',
                'id-0139', 'id-0140', 'id-0141', 'id-0142', 'id-0143', 'id-0144'}
# 设计目标
TARGET_PROBLEM = 15      # 已知真问题
TARGET_CLEAN = 15        # 已知干净(TN)
SEED_NOTE = 'Seed checklist: 分离 development 信号与 final scoring 信号'


def load_truth():
    recs = {}
    for f in sorted(glob.glob(os.path.join(TRUTH, '2026-*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        items = d if isinstance(d, list) else (d.get('records') or d.get('items') or [])
        for r in items:
            if isinstance(r, dict) and r.get('id'):
                i = r['id']
                if i not in recs or (r.get('checked_at', '') >= recs[i].get('checked_at', '')):
                    recs[i] = dict(r)
                    recs[i]['_shard'] = os.path.basename(f)
    return recs


def canonical_body(entries):
    """★ build 与 verify 必须用同一个序列化,否则 sha 永远对不上
       —— 这正是独立复算的价值:重跑 build 是发现不了的。"""
    return json.dumps(sorted(entries, key=lambda x: (x['kind'], x['stratum'], x['id'])),
                      ensure_ascii=False, sort_keys=True)


def lang_of(quote):
    q = quote or ''
    cjk = len(re.findall(r'[一-鿿]', q))
    return 'zh' if cjk >= max(6, len(q) * 0.12) else 'en'


def build():
    truth = load_truth()
    pairs = {p['id']: p for p in json.load(open(PAIRS, encoding='utf-8'))}
    # daily 的 30 条(有 url 和口径)
    for day in sorted(glob.glob(os.path.join(DAILY, '20*'))):
        f = os.path.join(day, 'pairs.json')
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding='utf-8'))
        for p in (d.get('pairs', d) if isinstance(d, dict) else d):
            pairs.setdefault(p['id'], p)

    pool = []
    for i, r in truth.items():
        p = pairs.get(i)
        if not p:
            continue
        v = r.get('verdict')
        types = r.get('types') or []
        if v == 'PROBLEM' and types:
            kind = 'PROBLEM'          # 已知真问题(有具体失真类型)
        elif v == 'TN':
            kind = 'CLEAN'            # 已知干净
        elif v == 'UNCLEAR':
            kind = 'UNCLEAR'          # 查不了(判不了,不能当分母)
        else:
            continue
        # 分层:verdict × 语种 × 判定分片(批次)
        strat = '%s|%s|%s' % (kind, lang_of(p.get('original', '')), r['_shard'].replace('.json', ''))
        pool.append({
            'id': i, 'kind': kind, 'stratum': strat,
            'types': types,
            'by': r.get('by'),
            'checked_at': r.get('checked_at'),
            'ruleset': r.get('ruleset'),
            'machine_flagged': bool((r.get('machine') or {}).get('flagged')),
            'in_old_holdout': i in OLD_HOLDOUT,
            'touched_by_tuning': bool(types) and r.get('by') in ('human', 'agent-blind'),
        })

    # ── 排除:旧留出集(已被冻结守卫保护,重复用就污染了) ──
    usable = [x for x in pool if not x['in_old_holdout']]
    # ── 分层抽样:层内随机,按目标比例分配 ──
    by_stratum = collections.defaultdict(list)
    for x in usable:
        by_stratum[x['stratum']].append(x)
    rng = random.Random(SEED)
    for k in by_stratum:
        rng.shuffle(by_stratum[k])

    def take(kind, target):
        """在 kind 的各层里,按层内可用比例分层抽,直到凑够 target"""
        strata = {k: v for k, v in by_stratum.items() if v and v[0]['kind'] == kind}
        total = sum(len(v) for v in strata.values())
        if total == 0:
            return []
        want = min(target, total)
        picked, quota = [], {k: want * len(v) / total for k, v in strata.items()}
        # 第一轮:按配额向下取整
        left = want
        for k, v in strata.items():
            q = min(len(v), int(quota[k]))
            picked += v[:q]
            left -= q
        # 第二轮:把剩下的按余数从大到小补
        remain = sorted(strata.keys(),
                        key=lambda k: -(quota[k] - int(quota[k])))
        while left > 0:
            progressed = False
            for k in remain:
                used = sum(1 for p in picked if p['stratum'] == k)
                if used < len(strata[k]) and left > 0:
                    picked.append(strata[k][used]); left -= 1; progressed = True
            if not progressed:
                break
        return picked

    sel = take('PROBLEM', TARGET_PROBLEM) + take('CLEAN', TARGET_CLEAN)
    sel.sort(key=lambda x: (x['kind'], x['stratum'], x['id']))

    body = canonical_body(sel)
    manifest = {
        'version': 'holdout-v2',
        'seed': SEED,
        'seed_note': SEED_NOTE,
        'built_at': datetime.datetime.now().replace(microsecond=0).isoformat(),
        'ruleset': sorted({x['ruleset'] for x in sel if x['ruleset']}),
        'target_problem': TARGET_PROBLEM,
        'target_clean': TARGET_CLEAN,
        'excluded_old_holdout': sorted(OLD_HOLDOUT),
        'n_selected': len(sel),
        'n_problem': sum(1 for x in sel if x['kind'] == 'PROBLEM'),
        'n_clean': sum(1 for x in sel if x['kind'] == 'CLEAN'),
        'n_strata': len({x['stratum'] for x in sel}),
        'n_touched_by_tuning': sum(1 for x in sel if x['touched_by_tuning']),
        'ids': [x['id'] for x in sel],
        'entries': sel,
        'body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
    }
    json.dump(manifest, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return manifest, pool


def design_accounting(manifest, pool):
    """★ 这个函数就是"不要造假"的保险:现场算清楚池子有多大、还差多少新材料。"""
    pool_problem = [x for x in pool if x['kind'] == 'PROBLEM']
    pool_clean = [x for x in pool if x['kind'] == 'CLEAN']
    pool_unc = [x for x in pool if x['kind'] == 'UNCLEAR']
    need_p = max(0, TARGET_PROBLEM - len(pool_problem))
    need_c = max(0, TARGET_CLEAN - len(pool_clean))
    return {
        'pool_total': len(pool),
        'pool_problem': len(pool_problem),
        'pool_clean': len(pool_clean),
        'pool_unclear': len(pool_unc),
        'excluded_old_holdout': len(OLD_HOLDOUT),
        'need_new_material_for_problem': need_p,
        'need_new_material_for_clean': need_c,
        'can_detect': '退化(小幅)',
        'cannot_detect': '准(召回/精确率的绝对水平)',
    }


def verify():
    """独立复算:不看切分逻辑,直接从真值分片重数一遍。"""
    truth = load_truth()
    m = json.load(open(OUT, encoding='utf-8'))
    ids = m['ids']
    bad = []
    for i in ids:
        r = truth.get(i)
        if not r:
            bad.append('%s 不在真值库里' % i); continue
        e = [x for x in m['entries'] if x['id'] == i][0]
        if e['kind'] != ('PROBLEM' if (r.get('verdict') == 'PROBLEM' and (r.get('types') or []))
                         else 'CLEAN' if r.get('verdict') == 'TN' else 'UNCLEAR'):
            bad.append('%s 的档位对不上' % i)
        if i in OLD_HOLDOUT:
            bad.append('%s 在旧留出集里,不应出现' % i)
    body = canonical_body(m['entries'])
    sha = hashlib.sha256(body.encode('utf-8')).hexdigest()
    print('═══ 留出集 v2 独立复算 ═══')
    print('  声明 %d 条 | 真值库里查得到 %d 条 | 档位对得上 %d 条'
          % (m['n_selected'], len(ids) - len([b for b in bad if '不在真值库' in b]),
             len(ids) - len([b for b in bad if '档位' in b])))
    print('  旧留出集混入: %d 条' % len([b for b in bad if '旧留出集' in b]))
    print('  条目正文 sha256: %s' % sha)
    print('  清单里记的 sha256: %s' % m['body_sha256'])
    print('  ⇒ %s' % ('✅ 一致' if not bad and sha == m['body_sha256'] else '❌ 不一致'))
    for b in bad[:8]:
        print('     ', b)
    return 0 if (not bad and sha == m['body_sha256']) else 1


def main():
    if '--verify' in sys.argv:
        return verify()
    m, pool = build()
    acc = design_accounting(m, pool)
    print('═══ 留出集 v2 设计账 ═══')
    print('  种子 %d | %s' % (SEED, SEED_NOTE))
    print('  池: %d 条(已知真问题 %d / 已知干净 %d / 查不了 %d) · 已排除旧留出集 %d 条'
          % (acc['pool_total'], acc['pool_problem'], acc['pool_clean'],
             acc['pool_unclear'], acc['excluded_old_holdout']))
    print('  切出: %d 条(已知真问题 %d / 已知干净 %d) · 分层 %d 层'
          % (m['n_selected'], m['n_problem'], m['n_clean'], m['n_strata']))
    print('  其中可能已被调参污染(带 types 且人/agent 判过): %d 条 ⇒ 待人工确认'
          % m['n_touched_by_tuning'])
    print()
    print('═══ ★ 这套切分能证明什么 / 不能证明什么 ═══')
    print('  能:改一条规则后,召回/精确率有没有<b>小幅退化</b>(退化检测)')
    print('  不能:证明"准" —— 绝对水平需要独立的新材料')
    print()
    if acc['need_new_material_for_problem'] or acc['need_new_material_for_clean']:
        print('  ⇒ 要拿到 n≥%d 已知真问题,还需要新采 **%d 条已知真问题**'
              % (TARGET_PROBLEM, acc['need_new_material_for_problem']))
        print('     (或:接受 n=%d 的留出集,并在报告里明写它只能测退化)'
              % acc['pool_problem'])
    print()
    print('  清单: %s  sha256 %s' % (OUT, m['body_sha256'][:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
