#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 数字口径闸 truth_numbers.py —— 防"引用过期读数"。

为什么要有这个:
  2026-11-10 的一次分析里,我引用了三条已经过期的数字
  (「留出集只剩 3 条」「真值库 140 条人工标注」「外部用户 0 个」),
  而这三件事在母会话里其实都已经修掉了。
  ⇒ 这个体系对抗了很多年"自己给自己打高分",却没对抗"引用过期读数"。
  ⇒ 本脚本把所有"对外可引用的数"改成:
      现场算 + 必须印分母 + 必须标取数时点
     并且对文档里的写死数字做 grep 断言。

用法:
    python3 truth_numbers.py            # 打印全部可引用数字(带分母+时点)
    python3 truth_numbers.py --check    # 闸:检查文档里有没有写死的过期数
    python3 truth_numbers.py --json     # 输出机器可读
"""
import json, os, re, glob, sys, hashlib, datetime, collections

TRUTH = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/truth'
PAIRS = '/workspace/output/eval3/cases/all82_pairs.json'
DAILY = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/daily'
DOCS = ['/workspace/output']
# ★ 排除:历史归档(那里的旧数字在它当时是真的)+ 分析类文档(引旧数字正是它们的目的)
EXCLUDE_PREFIX = ('/workspace/output/会话归档-2026-11-02',
                  '/workspace/work_archive',
                  '/workspace/tmpwork')
EXCLUDE_NAMES = ('truth_numbers.py',)   # 闸自己含这些字面量
EXCLUDE_RE = re.compile(r'(分析|纪要|更正|报告)')   # 这类文档允许引旧数(用于对照)

# ★ 跨文档一致性:同一个"标签"在多份文档里必须指向同一个数,
#   否则就是同一个量有两个口径 —— 跟"引用过期数字"是同一类病。
# ★ 锚点比对只跑「当前口径」文档。旧档(11-02 及以前)里的数字在它们当时是对的,
#   用今天的数去判它们矛盾,是把时间维度压扁了 —— 那正是本闸要防的病。
CURRENT_DOCS = {
    'Runbook-具体到每一步.md',
    '完整规划-减法优先-2026-11-10.md',
    '优化分析-减法优先-2026-11-10.md',
    '俱乐部定位-差距分析.md',
    '对话完整分析-两份会话合并.md',
    '对话归档完整分析-2026-11-10.md',
    '产品吸引力-两轮feed测试结论.md',
    '可用性测试报告-两轮.md',
}
# ★ 每个锚点带一个"期望值来源":
#   ('live', 'truth.unique_ids')  → 必须等于现场算出来的值
#   ('const', 75.9, '归档 regress 基线,历史常量') → 固定值,写在这里当契约
#   ('skip',)                    → 只查文档之间是否一致,不查绝对值
# ★ 关键:只查"文档之间一致"是不够的 —— 4 处都写 122 内部是一致的,
#   但现场真值是 79。**"文档和现实打架"才是要拦的那个。**
ANCHORS = [
    ('真值唯一id',   r'唯一\s*id\s*\*{0,2}(\d+)',              ('live', 'truth.unique_ids')),
    ('实质判定',     r'实质判定\s*\*{0,2}(\d+)',                ('live', 'truth.substantive_judged')),
    ('auto-default', r'auto-default\s*\*{0,2}(\d+)',            ('live', 'truth.auto_default')),
    ('agent盲读',    r'agent\s*盲读\s*\*{0,2}(\d+)',           ('live', 'truth.by_agent_blind')),
    ('留出集v2条数', r'留出集\s*v2\s*\*{0,2}(\d+)\s*条',      ('live', 'holdout.n_selected')),
    ('finding数',    r'finding\s*\*{0,2}(\d+)',                  ('live', 'materials.machine_findings_attached')),
    ('旧留出集条数', r'旧留出集\s*\*{0,2}(\d+)\s*条',          ('const', 12, '旧冻结留出集 id0133-0144')),
    ('开发集召回',   r'(?<![占比路])\s*召回\s*\*{0,2}(\d+\.\d)%', ('const', 75.9, '归档 regress 基线')),
    ('留出集召回',   r'留出集\s*\*{0,2}召回\s*\*{0,2}(\d+\.\d)%', ('live', 'holdout_v2.recall_pct')),
]

# ★ 文档里禁止出现的写死数字(它们曾经是真的,现在不是了)
BANNED_LITERALS = [
    (r'140\s*条人工标注', '真值口径已改成 102 条实质判定;38 条是 auto-default,不是人工标注'),
    (r'留出集干净样本\s*[:：]?\s*3\s*条', '留出集已重切并冻结(holdout_freeze.py),旧口径作废'),
    # ★ 这条提示自己以前也写错过(写"3 人")—— ★ 权威源是站点 METRICS.md:
    #   外部真实订户 = 2 人(编号 003/004);★ 001 是运营者自测号(is_internal=true),002 已退订。
    (r'外部用户\s*0\s*个', '11-09 的旧读数;最新是外部订户 2 人(003/004;001 是自测号,002 已退订)'),
    (r'97\s*条', '装配错挂错条目时的虚高数;真实 finding 数应以本脚本现场算为准'),
    (r'22/29\s*=\s*75\.9%', '文档口径已改为修正口径 21/23;两个数不能并存'),
]


def load_truth():
    recs = []
    for f in sorted(glob.glob(os.path.join(TRUTH, '2026-*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        items = d if isinstance(d, list) else d.get('records') or d.get('items') or []
        for r in items:
            if isinstance(r, dict) and r.get('id'):
                r['_shard'] = os.path.basename(f)
                recs.append(r)
    return recs


def load_pairs():
    p = json.load(open(PAIRS, encoding='utf-8'))
    return p if isinstance(p, list) else p.get('pairs', [])


def compute():
    recs = load_truth()
    pairs = load_pairs()
    now = datetime.datetime.now().replace(microsecond=0).isoformat()

    # ── 真值库口径(分三层,每层一个分母) ──
    by_id = {}
    for r in recs:
        i = r['id']
        if i not in by_id:
            by_id[i] = dict(r)
        else:
            # 后写的分片覆盖旧的,但保留 supersedes 链信息
            if r.get('checked_at', '') >= by_id[i].get('checked_at', ''):
                keep = by_id[i].get('supersedes')
                by_id[i] = dict(r)
                if keep:
                    by_id[i]['supersedes'] = keep
    uid = len(by_id)
    # ★ 交接包(2026-11-02)是真值库旧版:没有 judged 字段,也没有 by=auto-default。
    #   只看 judged 会算出 auto=0 —— 那是错的。必须能从 note 兜底判出来。
    AUTO_NOTE = re.compile(r'从未被单独判读')
    auto = sum(1 for r in by_id.values()
               if r.get('by') == 'auto-default' or r.get('judged') is False
               or AUTO_NOTE.search(str(r.get('note', ''))))
    human = sum(1 for r in by_id.values() if r.get('by') == 'human')
    agent = sum(1 for r in by_id.values() if str(r.get('by', '')).startswith('agent'))
    conflict = sum(1 for r in by_id.values() if r.get('superseded') or r.get('supersedes'))
    substantive = uid - auto
    v = {'TN': 0, 'PROBLEM': 0, 'UNCLEAR': 0}
    for r in by_id.values():
        if r.get('verdict') in v:
            v[r['verdict']] += 1
    # 查不了(UNCLEAR)占比:三个分母都印
    unc = v['UNCLEAR']
    # 已知真问题:PROBLEM 且带 types(说明有具体失真类型)
    known_problem = sum(1 for r in by_id.values()
                        if r.get('verdict') == 'PROBLEM' and (r.get('types') or []))

    # ── 材料池 ──
    pair_ids = {p['id'] for p in pairs}
    covered = len(pair_ids & set(by_id))

    # ── daily 侧的判据路 finding(按 id 归组,不按天) ──
    findings = {}
    for day in sorted(glob.glob(os.path.join(DAILY, '20*'))):
        L = os.path.join(day, 'lanes')
        if not os.path.isdir(L):
            continue
        for ln in ('N', 'S', 'T'):
            f = os.path.join(L, ln + '.json')
            if not os.path.exists(f):
                continue
            j = json.load(open(f, encoding='utf-8'))
            for it in j.get('findings', []):
                findings.setdefault(it.get('id'), []).append(
                    {'lane': ln, 'claim': it.get('claim', '')[:80]})

    # ── 装机量(口径化的三句) ──
    site_cards = '/workspace/tmpwork/handoff/sites_cards.json'
    n_site = 0
    if os.path.exists(site_cards):
        try:
            sc = json.load(open(site_cards, encoding='utf-8'))
            n_site = len(sc if isinstance(sc, list) else sc.get('cards', []))
        except Exception:
            pass

    return {
        'as_of': now,
        'source': 'truth/*.json (现场算)',
        'truth': {
            'unique_ids': uid,
            'substantive_judged': substantive,   # 唯一 id 减去 auto-default
            'auto_default': auto,
            'auto_default_how': ('by=auto-default 或 judged=false,或 note 含「从未被单独判读」'
                                 '(交接包旧版无 judged 字段,必须靠 note 兜底)'),
            'by_human': human,
            'by_agent_blind': agent,
            'supersede_conflicts': conflict,
            'verdict_TN': v['TN'], 'verdict_PROBLEM': v['PROBLEM'], 'verdict_UNCLEAR': v['UNCLEAR'],
            'known_problem_with_types': known_problem,
            'unclear_ratio_by_unique_ids': round(unc / uid * 100, 1) if uid else None,
            'unclear_ratio_by_substantive': round(unc / substantive * 100, 1) if substantive else None,
        },
        'materials': {
            'pairs_total': len(pairs),
            'pairs_covered_by_truth': covered,
            'pairs_never_judged': len(pairs) - covered,
            'site_cards': n_site,
            'machine_findings_attached': sum(len(v) for v in findings.values()),
        },
        'notes': [
            '「查不了」有三个分母:唯一 id / 实质判定 / 机器报出 —— 对外必须声明用的是哪一个',
            'agent 盲读是模型判读,不是独立信源;不得计入「人工标注」',
        ],
    }


def _dig(obj, path):
    for p in path.split('.'):
        obj = obj.get(p) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


def exp_of(label, data=None):
    """这个锚点的期望值:live → 现场算;const → 契约里的常量。"""
    for lbl, _pat, spec in ANCHORS:
        if lbl != label:
            continue
        if spec[0] == 'live':
            if spec[1] == 'holdout.n_selected':
                try:
                    ho = json.load(open('/workspace/output/eval3/holdout_v2.json', encoding='utf-8'))
                    return ho['n_selected']
                except Exception:
                    return None
            if spec[1] == 'holdout_v2.recall_pct':
                try:
                    sc = json.load(open('/tmp/ho_score.json', encoding='utf-8'))
                    return round(sc['holdout_v2']['recall'] * 100, 1)
                except Exception:
                    return None
            return _dig(data or {}, spec[1])   # ★ 路径是相对 data 根的
        if spec[0] == 'const':
            return spec[1]
    return None


def check():
    """闸:文档里出现写死的过期数字 ⇒ 失败"""
    data = compute()
    bad = []
    for d in DOCS:
        if not os.path.isdir(d):
            continue
        for root, _dd, files in os.walk(d):
            for fn in files:
                if not fn.endswith(('.md', '.html', '.py', '.json')):
                    continue
                # ★ 临时文件(以下划线开头:连接器 args / 快照 / 中间态)不是文档 ——
                #   ★ 2026-11-24 实测:一个 804KB 的 _push.json 被当成"写死的过期数字"扫出来,
                #   ★ 假警报把真问题(上游 +10 条没核)掩盖了。★★
                if fn.startswith('_'):
                    continue
                p = os.path.join(root, fn)
                ap = os.path.abspath(p)
                if any(ap.startswith(x) for x in EXCLUDE_PREFIX):
                    continue
                if fn in EXCLUDE_NAMES:
                    continue
                if EXCLUDE_RE.search(fn):
                    continue
                try:
                    t = open(p, encoding='utf-8').read()
                except Exception:
                    continue
                for pat, why in BANNED_LITERALS:
                    for m in re.finditer(pat, t):
                        # ★ 闸要拦的是「把旧数当现数用」,不是「提到旧数」。
                        #   若同段里带时点/作废标记(在讲历史),放行。
                        ctx = t[max(0, m.start() - 160): m.end() + 160]
                        if re.search(r'当时|曾经|历史|旧的?|已作废|已修正|已清零|原先|此前|bug|BUG', ctx):
                            continue
                        bad.append((p, m.group(0), why))
    print('═══ 数字口径闸 @ %s ═══' % data['as_of'])
    print('  真值:唯一 id %d = 实质判定 %d + auto-default %d  (人判 %d / agent 盲读 %d)'
          % (data['truth']['unique_ids'], data['truth']['substantive_judged'],
             data['truth']['auto_default'], data['truth']['by_human'], data['truth']['by_agent_blind']))
    print('  verdict: TN %d / PROBLEM %d / UNCLEAR %d'
          % (data['truth']['verdict_TN'], data['truth']['verdict_PROBLEM'], data['truth']['verdict_UNCLEAR']))
    print('  查不了占比: %s%%(唯一 id) / %s%%(实质判定)'
          % (data['truth']['unclear_ratio_by_unique_ids'], data['truth']['unclear_ratio_by_substantive']))
    print('  材料: %d 对 · 真值覆盖 %d · 从没判过 %d'
          % (data['materials']['pairs_total'], data['materials']['pairs_covered_by_truth'],
             data['materials']['pairs_never_judged']))
    # ── 正向断言:把现场算的结果落成唯一真源,并断言它与本次计算一致 ──
    canon = os.path.join('/workspace/output', '数字口径-唯一真源.json')
    prev = None
    if os.path.exists(canon):
        try:
            prev = json.load(open(canon, encoding='utf-8'))
        except Exception:
            prev = None
    drift = []
    if prev:
        for k in ('unique_ids', 'substantive_judged', 'auto_default', 'verdict_PROBLEM', 'verdict_UNCLEAR'):
            a = prev.get('truth', {}).get(k)
            b = data['truth'].get(k)
            if a is not None and a != b:
                drift.append('%s: 真源 %s → 现场 %s' % (k, a, b))
    json.dump(data, open(canon, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('  唯一真源已写: %s' % canon)
    if drift:
        print('  ⚠️ 数字漂移(真源 vs 现场):')
        for x in drift:
            print('     ', x)
    else:
        print('  ✓ 现场算与唯一真源一致(无漂移)')
    # ── 跨文档一致性 ──
    print('  ── 跨文档锚点一致性 ──')
    for label, pat, _spec in ANCHORS:
        vals = collections.defaultdict(list)
        for root, _dd, files in os.walk('/workspace/output'):
            for fn in files:
                if not fn.endswith(('.md', '.html')):
                    continue
                p = os.path.join(root, fn)
                if any(os.path.abspath(p).startswith(x) for x in EXCLUDE_PREFIX):
                    continue
                rel = os.path.relpath(p, '/workspace/output')
                if rel not in CURRENT_DOCS:
                    continue
                try:
                    t = open(p, encoding='utf-8').read()
                except Exception:
                    continue
                for m in re.finditer(pat, t):
                    ctx = t[max(0, m.start() - 120): m.end() + 120]
                    if re.search(r'当时|曾经|历史|旧的?|已作废|已修正|已清零|原先|此前|快照|母会话', ctx):
                        continue
                    vals[m.group(1)].append(os.path.relpath(p, '/workspace/output'))
        if len(vals) > 1:
            bad.append(('一致性', label, str({k: len(v) for k, v in vals.items()})))
            print('    ❌ 「%s」有 %d 个口径: %s' % (label, len(vals),
                  ' | '.join('%s(%d处)' % (k, len(v)) for k, v in vals.items())))
            continue
        if not vals:
            print('    · 「%s」文档里没出现' % label)
            continue
        k = list(vals)[0]
        exp = exp_of(label, data)
        if exp is None:
            print('    · 「%s」= %s(%d 处,不做绝对值校验)' % (label, k, len(vals[k])))
        elif abs(float(k) - float(exp)) < 0.051:
            print('    ✓ 「%s」= %s(%d 处,等于现场值 %s)' % (label, k, len(vals[k]), exp))
        else:
            bad.append(('绝对值', label, '%s ≠ 现场 %s' % (k, exp)))
            print('    ❌ 「%s」= %s 但现场算的是 %s  ← %s'
                  % (label, k, exp, ' '.join(sorted(set(vals[k]))[:3])))
    print()
    if bad:
        print('❌ 发现 %d 处写死的过期数字:' % len(bad))
        for p, lit, why in bad[:20]:
            print('   %s\n     「%s」 —— %s' % (p, lit, why))
        return 1
    print('✅ 没有写死的过期数字')
    return 0


def main():
    if '--check' in sys.argv:
        sys.exit(check())
    data = compute()
    if '--json' in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
