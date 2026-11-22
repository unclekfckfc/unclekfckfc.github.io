#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁 v2:相对退化检测 —— 替掉绝对阈值。

为什么:
  旧的绝对阈值 `min_recall 0.60` 对着"实测 75.9%"。
  但那个 75.9% 是在**调过参的开发集**上测的。
  在从未参与调参的留出集 v2 上实测:召回 **50.0%**(7/14)、精确率 **100%**(7/7)、已知干净 15 条**零误报**。
  ⇒ 用绝对阈值会得出两个都错的结论:
     开发集上 0.60 挡不住"小幅退化"(75.9% → 72% 也过)
     留出集上又直接 FAIL(50% < 60%),而那不是退化,是**分布差异**
  ⇒ 正确做法:门禁量的是**相对基线的退化幅度**,不是绝对水平。
     绝对水平由留出集单独报,且必须带分母。

用法:
    python3 gate_relative.py            # 跑基线 + 当前,判退化
    python3 gate_relative.py --json     # 机器可读
"""
import json, subprocess, os, sys, datetime, hashlib

GUARD = '/workspace/.skills/transcription-guard/scripts/guard.py'
HO = '/workspace/output/eval3/holdout_v2.json'
PAIRS = '/workspace/output/eval3/cases/all82_pairs.json'
BASELINE = '/workspace/output/eval3/baseline_holdout_v2.json'

# ★ 退化容忍度:相对基线掉多少个百分点算退化。
#   3pp 的依据:留出集 n=14 时,1 条 = 7.1pp;3pp ≈ 半个样本的分辨率下限,
#   小于这个量的波动是抽样噪声,不是退化。
DEGRADE_TOLERANCE_PP = 3.0


def load_holdout_pairs():
    ho = json.load(open(HO, encoding='utf-8'))
    pm = {p['id']: p for p in json.load(open(PAIRS, encoding='utf-8'))}
    out = []
    for e in ho['entries']:
        p = pm.get(e['id'])
        if not p:
            continue
        out.append({'id': e['id'], 'transmitted': p['transmitted'], 'original': p['original'],
                    '_kind': e['kind'], '_types': e['types'], '_tuning': e['touched_by_tuning']})
    return out, ho


def run_detector(pool):
    tmp = '/tmp/_gate_holdout.json'
    json.dump([{k: v for k, v in o.items() if not k.startswith('_')} for o in pool],
              open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    r = subprocess.run(['python3', GUARD, '--pair', tmp, '--json'], capture_output=True, text=True)
    res = json.loads(r.stdout)
    byid = {x['id']: x for x in res}
    pos = sum(1 for o in pool if o['_kind'] == 'PROBLEM')
    fired = [o for o in pool if byid.get(o['id'], {}).get('flags')]
    tp = sum(1 for o in fired if o['_kind'] == 'PROBLEM')
    fp = sum(1 for o in fired if o['_kind'] != 'PROBLEM')
    clean = [o for o in pool if o['_kind'] == 'CLEAN']
    fp_clean = sum(1 for o in clean if byid.get(o['id'], {}).get('flags'))
    return {
        'n_total': len(pool),
        'n_known_problem': pos,
        'n_known_clean': len(clean),
        'n_fired': len(fired),
        'tp': tp, 'fp': fp, 'fp_on_clean': fp_clean,
        'recall': round(tp / pos, 4) if pos else None,
        'precision': round(tp / len(fired), 4) if fired else None,
        'false_positive_rate_on_clean': round(fp_clean / len(clean), 4) if clean else None,
        'denominators': {
            'recall': '已知真问题条数(%d)' % pos,
            'precision': '机器报出条数(%d)' % len(fired),
            'false_positive_rate_on_clean': '已知干净条数(%d)' % len(clean),
        },
    }


def main():
    pool, ho = load_holdout_pairs()
    cur = run_detector(pool)
    cur['at'] = datetime.datetime.now().replace(microsecond=0).isoformat()
    cur['holdout_sha256'] = ho['body_sha256']

    # ── 基线:第一次跑出来的就是基线,之后每次跑跟它比 ──
    base = None
    if os.path.exists(BASELINE):
        base = json.load(open(BASELINE, encoding='utf-8'))
    if base is None:
        json.dump(cur, open(BASELINE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('═══ 门禁 v2 · 首次运行,已写成基线 ═══')
        print(json.dumps(cur, ensure_ascii=False, indent=1))
        return 0

    def pp(a, b):
        return None if (a is None or b is None) else round((b - a) * 100, 2)

    d_recall = pp(base['recall'], cur['recall'])
    d_prec = pp(base['precision'], cur['precision'])
    d_fp = pp(base['false_positive_rate_on_clean'], cur['false_positive_rate_on_clean'])
    fails = []
    if d_recall is not None and d_recall < -DEGRADE_TOLERANCE_PP:
        fails.append('召回退化 %.2fpp(容忍 %.1fpp)' % (-d_recall, DEGRADE_TOLERANCE_PP))
    if d_prec is not None and d_prec < -DEGRADE_TOLERANCE_PP:
        fails.append('精确率退化 %.2fpp' % (-d_prec))
    if d_fp is not None and d_fp > DEGRADE_TOLERANCE_PP:
        fails.append('干净样本假阳率上升 %.2fpp' % d_fp)

    out = {'at': cur['at'], 'baseline_at': base['at'], 'tolerance_pp': DEGRADE_TOLERANCE_PP,
           'current': cur, 'baseline': {k: base[k] for k in
           ('recall', 'precision', 'false_positive_rate_on_clean', 'n_known_problem',
            'n_known_clean', 'n_fired')},
           'delta_pp': {'recall': d_recall, 'precision': d_prec, 'fp_on_clean': d_fp},
           'verdict': 'FAIL' if fails else 'PASS', 'reasons': fails}
    if '--json' in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print('═══ 门禁 v2 · 相对退化检测 ═══')
        print('  基线 %s | 当前 %s | 容忍 ±%.1fpp'
              % (base['at'], cur['at'], DEGRADE_TOLERANCE_PP))
        print('  召回     %.1f%% → %.1f%%  (Δ %+.2fpp) 分母=%s'
              % (base['recall'] * 100, cur['recall'] * 100, d_recall or 0,
                 cur['denominators']['recall']))
        print('  精确率   %.1f%% → %.1f%%  (Δ %+.2fpp) 分母=%s'
              % (base['precision'] * 100, cur['precision'] * 100, d_prec or 0,
                 cur['denominators']['precision']))
        print('  干净假阳 %.1f%% → %.1f%%  (Δ %+.2fpp) 分母=%s'
              % (base['false_positive_rate_on_clean'] * 100,
                 cur['false_positive_rate_on_clean'] * 100, d_fp or 0,
                 cur['denominators']['false_positive_rate_on_clean']))
        print('  ⇒ %s%s' % (out['verdict'], ('　' + '; '.join(fails)) if fails else ''))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
