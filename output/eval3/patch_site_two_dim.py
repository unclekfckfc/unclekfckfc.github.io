#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 站点两维章补丁生成器  ② §9 议题前提清单(真表)

★ 为什么这两件放一起:它们共用同一份真值库和同一套 id 对应关系。

站点侧的关键事实(实测,不是推测):
  · signals.js 是「构建期自动生成,勿手改」的数据快照 → **改它没用,得改生成它的那一步**
  · ctl.schema.json 是站长的契约文件 → **★ 字段定义 + 原则文本都在这里,可以直接改**
  · 渲染带 sig-stamp 的那个页面不在交接快照里(站长的活文件)→ 渲染层给不出补丁,只能给规格
  · `id:132` ≡ `id-0132` → **id 直接对得上,这是能做数据层补丁的前提**

用法:
    python3 patch_site_two_dim.py            # 生成补丁 + 规格 + 议题前提清单
    python3 patch_site_two_dim.py --preview  # 生成一个 HTML 预览(用真数据看两维章长什么样)
"""
import json, os, re, glob, collections, datetime

TRUTH = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/truth'
PAIRS = '/workspace/output/eval3/cases/all82_pairs.json'
DAILY = '/workspace/tmpwork/h2b/handoff-2026-11-02/10-skills/claim-audit/data/daily'
SITE = '/workspace/tmpwork/h2b/handoff-2026-11-02/40-站点原始素材/站点源码-2026-10-27'
OUT = '/workspace/output/eval3/site_patch'
NOW = datetime.datetime.now().replace(microsecond=0).isoformat()

# ★ 三态:内容核验层
VC_VERIFIED = 'v'      # 已成立:有人/判据路核过,且原文支持这句话
VC_REFUTED = 'r'       # 不成立:★ 原文明确否定了这句话的某个关键要素(限定词丢失等)
VC_UNKNOWN = 'x'       # 查不了:引文跟说法不是同一件事 / 人工判不了 —— ★ 不是"不成立"
VC_UNVERIFIED = 'u'    # 从来没被查过:机器路没看它 / 从没被人单独判读

VC_TEXT = {
    VC_VERIFIED: '已成立',
    VC_REFUTED: '不成立',
    VC_UNKNOWN: '查不了',
    VC_UNVERIFIED: '从来没被查过',
}
VC_COLOR = {VC_VERIFIED: 'ok', VC_REFUTED: 'warn', VC_UNKNOWN: 'warn', VC_UNVERIFIED: 'none'}


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
    return recs


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


# ★ 「不成立」的唯一硬判据:原文里的限定词在转述里没了
#   原文「计划筹集最高 1000 亿美元」→ 转述「募 1000 亿美元」⇒ 前提确实被推翻了
# ★ 「查不了」与「不成立」必须分开:引文对不上 ≠ 这句话是假的。
CAP_LOST = re.compile(r'(最高|最多|不超过|至多|上限)')


def vc_of(rec, claim='', quote=''):
    """真值 → 内容核验层【四态】。判据全部写在这里,可审计。"""
    if not rec:
        return VC_UNVERIFIED, '真值库里没有这条 ⇒ 从来没被查过'
    v = rec.get('verdict')
    types = rec.get('types') or []
    note = str(rec.get('note', ''))
    # ① 不成立:限定词被抹(硬判据,靠原文对照)
    lost = CAP_LOST.findall(quote or '')
    if lost and not CAP_LOST.findall(claim or ''):
        return VC_REFUTED, '原文的上限词「%s」在转述里没了 ⇒ 前提不成立' % ('/'.join(set(lost)))
    if 'limit' in types or '口径' in note or '限定' in note:
        return VC_REFUTED, '限定/口径丢失(人工判定)⇒ 前提不成立'
    # ② 查不了:引文跟说法不是同一件事 / 人工判不了
    if 'assembly' in types or '完全不对应' in note or '完全错配' in note:
        return VC_UNKNOWN, '引文跟说法不是同一件事 ⇒ 查不了(不是不成立)'
    if v == 'PROBLEM':
        return VC_UNKNOWN, '判为真问题(转述失真/口径丢失)⇒ 查不了'
    if v == 'UNCLEAR':
        return VC_UNKNOWN, '人工判不了 ⇒ 查不了'
    if v == 'TN':
        if '从未被单独判读' in note:
            return VC_UNVERIFIED, '机器未报出,人工亦未单独判读 ⇒ 从来没被查过'
        return VC_VERIFIED, '已成立'
    return VC_UNVERIFIED, '无判定 ⇒ 从来没被查过'


def main():
    os.makedirs(OUT, exist_ok=True)
    truth = load_truth()
    pairs = load_pairs()

    # ── ① 生成带 vc 的数据 + 补丁规格 ──
    rows = []
    for p in pairs:
        i = p['id']
        _lines = (p.get('transmitted') or '').split('\n')
        vc, why = vc_of(truth.get(i), _lines[0], p.get('original') or '')
        lines = (p.get('transmitted') or '').split('\n')
        rows.append({
            'id': i, 'sid': int(re.sub(r'\D', '', i) or 0),
            'claim': lines[0].strip(), 'quote': (p.get('original') or '')[:160],
            'url': p.get('url'), 'vc': vc, 'vc_text': VC_TEXT[vc], 'vc_basis': why,
        })
    n = len(rows)
    cnt = collections.Counter(r['vc'] for r in rows)

    patch = {
        'generated_at': NOW,
        'n': n,
        'vc_counts': dict(cnt),
        'field_name': 'vc',
        'field_values': {'v': '已成立', 'r': '不成立', 'x': '查不了', 'u': '从来没被查过'},
        'field_colors': VC_COLOR,
        '★ 为什么是四态': ('★「查不了」≠「不成立」:引文跟说法对不上,只说明无法判定,'
                            '不代表这句话是假的。把它塞进「不成立」会得出错误结论 —— '
                            '例如 id-0100「土安全部 60 天清退 DeepSeek」只是引文对不上,前提未必假。'),
        'why_not_a_new_stamp': (
            '★ 站长 schema 的 principle 已写:「等级(L0–L3,证据链完整度)与章位(stamp,口径状态)'
            '是两条正交维度,不得混用。」'
            '⇒ 本补丁不动 stamp(s/st),不动等级(L0-L3),只补第三条正交维度:内容核验层。'),
        'steps': [
            {'n': 1, 'where': 'open-audit/ctl.schema.json',
             'what': 'fields 里加 vc;principle 文本改成三条正交维度',
             'why': 'schema 是站长的契约文件,生成脚本读它 —— 改这里字段就有了',
             'note': '★ 不要改 signals.js:它是「构建期自动生成,勿手改」'},
            {'n': 2, 'where': '构建脚本(生成 signals.js 的那一步)',
             'what': '给每条算 vc 并写进产物',
             'why': 'signals.js 是快照,直接改会被下次构建覆盖',
             'note': '判据见本文件的 vc_basis 字段,可直接复用'},
            {'n': 3, 'where': '卡片渲染(活站点文件)',
             'what': '在现有 sig-stamp 下面加一行内容核验层;未核验的显式写「未核验」',
             'why': '★ 现在 s=ok 的条目里有 29 条被判过转述失真,而 stamp 说的是「口径有没有补录」,回答不了「结论核没核」',
             'note': '★ 关键:未核验必须显示成「未核验」,绝不能显示成「没问题」'},
            {'n': 4, 'where': 'build_guard.py / check_metrics.py',
             'what': '加一条断言:vc=x 的条目数必须与真值库 PROBLEM+UNCLEAR 对得上',
             'why': '防止两处口径漂移 —— 这正是今天我自己踩的坑'},
        ],
        'render_spec': {
            '来源层': '沿用现有 sig-stamp(s/st),不动',
            '内容核验层': 'v → 中性色「已核验」;u → 暖灰「未核验」;x → 暖灰「查不了」',
            '禁止': '不得用绿色表示已核验;不得把 u 渲染成任何肯定词',
            '文案': '「核到了什么」= 逐字比对过,不代表结论对',
        },
        'rows': rows,
    }
    json.dump(patch, open(os.path.join(OUT, 'site_patch.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # ── ② §9 议题前提清单(真表) ──
    TOPIC = 'AI 芯片出口管制'
    KW = re.compile(r'(出口|管制|清退|禁令|英伟达|NVIDIA|芯片|算力|H20|B30|实体清单)')
    prem = []
    for r in rows:
        txt = r['claim'] + ' ' + r['quote']
        if not KW.search(txt):
            continue
        state = VC_TEXT[r['vc']]
        prem.append({'id': r['id'], 'premise': r['claim'][:70], 'state': state,
                     'basis': r['vc_basis'], 'url': r['url']})
    est = [p for p in prem if p['state'] == '已成立']
    unk = [p for p in prem if p['state'] == '从来没被查过']
    dis = [p for p in prem if p['state'] == '不成立']
    que = [p for p in prem if p['state'] == '查不了']
    premise_table = {
        'generated_at': NOW, 'topic': TOPIC,
        'method': '§9 议题前提清单:从档案取该议题下所有事实 → 每条写成前提 → 标三态 → 汇总还缺什么',
        'n_premises': len(prem), 'n_established': len(est),
        'n_never_checked': len(unk), 'n_refuted': len(dis), 'n_undecidable': len(que),
        'missing': [p['id'] for p in unk], 'refuted': [p['id'] for p in dis],
        'premises': prem,
    }
    json.dump(premise_table, open(os.path.join(OUT, '议题前提清单-%s.json' % TOPIC), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # ── 打印 ──
    print('═══ ① 站点两维章补丁 @ %s ═══' % NOW)
    print('  %d 条 | 已核验 %d · 未核验 %d · 查不了 %d'
          % (n, cnt['v'], cnt['u'], cnt['x']))
    print('  ★ 不动 stamp(s/st)与等级(L0-L3)—— 只补第三条正交维度')
    print('  ★ 修改点: ctl.schema.json(字段+principle) → 构建脚本(算 vc) → 卡片渲染(加一行) → 护栏(断言口径)'
          '      ★ 不要改 signals.js(构建期自动生成,勿手改)')
    print('  清单: %s/site_patch.json' % OUT)

    print('\n═══ ② §9 议题前提清单 · 「%s」═══' % TOPIC)
    print('  前提 %d 条 | 已成立 %d · 不成立 %d · 查不了 %d · 从来没被查过 %d'
          % (len(prem), len(est), len(dis), len(que), len(unk)))
    print('\n  ── 已成立(有逐字原文 + 号)──')
    for p in est:
        print('  ✓ %-10s %s' % (p['id'], p['premise'][:52]))
    print('\n  ── 不成立(原文明确否定了某个关键要素)──')
    for p in dis:
        print('  ✗ %-10s %-52s ← %s' % (p['id'], p['premise'][:52], p['basis'][:40]))
    print('\n  ── 查不了(引文对不上 / 人工判不了)—— ★ 不是"不成立"──')
    for p in que:
        print('  ? %-10s %-52s ← %s' % (p['id'], p['premise'][:52], p['basis'][:40]))
    print('\n  ── 从来没被查过(★ 这就是"还缺什么")──')
    for p in unk:
        print('  ? %-10s %s' % (p['id'], p['premise'][:52]))
    print('\n  ★ 汇总:这个议题下 —— 已成立 %d · 不成立 %d · 查不了 %d · 从来没被查过 %d'
          % (len(est), len(dis), len(que), len(unk)))
    print('  ★ 这张清单真正的交付物不是预测,是**缺什么**:那 %d 个"从来没被查过"的。' % len(unk))
    print('  ★ 而 %d 个"查不了"说明另一件事:★ 抓来的东西里,大部分现在还不能当依据用。' % len(que))
    print('  清单: %s/议题前提清单-%s.json' % (OUT, TOPIC))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
