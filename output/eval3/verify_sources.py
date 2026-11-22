#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出处全文核验 —— 把「查不了」和「不成立」分开,并把结论写回底稿数据。

跑法: python3 verify_sources.py           # 有缓存就用缓存,没缓存才联网抓
      python3 verify_sources.py --refresh # 强制重新抓

产出:
  eval3/source_cache.json   抓取缓存(url → {status, text, http, len, fetched_at})
  digao_data.json 每条多一个 src_check:
      {'status':'ok|stub|blocked|timeout|none',
       'via':'curl|playwright', 'len':N,
       'nums':[{'n':'205 亿美元','b':'hit|unit_mismatch|miss|not_a_number','ev':'...'}]}

★ 纪律:status != 'ok' 的条目,它的数一律记成 'unknown',不许说成 'miss'。
  「出处全文里没有」这句话,只有在确认抓到了正文时才敢说。
"""
import json, os, re, sys, time, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_source import fetch, judge_number

DATA = os.path.join(HERE, 'digao_data.json')
CACHE = os.path.join(HERE, 'source_cache.json')


def load_cache():
    try:
        return json.load(open(CACHE, encoding='utf-8'))
    except Exception:
        return {}


_CLAIM_RE = re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(%|％|倍|万|亿)?')


def claim_nums(claim):
    """从结论文本里提数 —— 口径跟卡里的正则一致（卡只吃一个单位字）"""
    out = []
    for m in _CLAIM_RE.finditer(claim or ''):
        raw, unit = m.group(1), (m.group(2) or '')
        if len(raw) < 2 and not unit:
            continue
        if raw in ('10', '100', '2024', '2025', '2026', '2027'):
            continue
        name = raw + unit
        if name not in out:
            out.append(name)
    return out


def main():
    refresh = '--refresh' in sys.argv
    d = json.load(open(DATA, encoding='utf-8'))
    cache = load_cache()
    todo = [e for e in d['entries'] if e.get('url')]
    print('═══ 出处全文核验（%d 条有链接）═══' % len(todo))

    need = []
    for e in todo:
        u = e['url']
        if refresh or u not in cache or cache[u].get('status') not in ('ok', 'stub', 'blocked', 'timeout'):
            need.append(e)
    print('缓存命中 %d 条,需抓取 %d 条' % (len(todo) - len(need), len(need)))

    if need:
        def get(e):
            return e['url'], fetch(e['url'], use_browser=True)

        with cf.ThreadPoolExecutor(5) as ex:
            for u, r in ex.map(get, need):
                r.pop('final_url', None)
                r['fetched_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                cache[u] = r
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        print('缓存已写 %s（%d 条）' % (CACHE, len(cache)))

    # ── 判定并写回 ──
    from collections import Counter
    cnt = Counter()
    n_changed = 0
    for e in d['entries']:
        u = e.get('url')
        if not u:
            e['src_check'] = {'status': 'none', 'len': 0, 'via': '', 'nums': []}
            continue
        r = cache.get(u, {'status': 'timeout', 'len': 0, 'via': ''})
        st = r.get('status', 'timeout')
        txt = r.get('text', '') if st == 'ok' else ''      # ★ 只有 ok 才给文本
        quote = e.get('quote') or ''
        rows = []
        seen = set()
        for n in (e.get('nums') or []):
            name = n['n']
            if name in seen:
                continue
            seen.add(name)
            bq, _ = judge_number(name, quote)
            if st != 'ok':
                b, ev = 'unknown', '没抓到正文，不能说没有'
            else:
                b, ev = judge_number(name, txt)
                if bq == 'hit' and b != 'hit':
                    b, ev = 'quoted', '引文已盖住'
            rows.append({'n': name, 'b': b, 'ev': ev})
            cnt[b] += 1
        # ★ 结论文本里还有 nums 字段没登记的数（卡是从结论文本里提数的）
        #   —— 不补这一段，卡上标的某些数在表里查不到，就会又退回"你贴的这句里没有"
        for name in claim_nums(e.get('claim') or ''):
            if name in seen:
                continue
            seen.add(name)
            bq, _ = judge_number(name, quote)
            if st != 'ok':
                b, ev = 'unknown', '没抓到正文，不能说没有'
            else:
                b, ev = judge_number(name, txt)
                if bq == 'hit' and b != 'hit':
                    b, ev = 'quoted', '引文已盖住'
            rows.append({'n': name, 'b': b, 'ev': ev})
            cnt[b] += 1
        e['src_check'] = {'status': st, 'len': r.get('len', 0), 'via': r.get('via', ''),
                          'fetched_at': r.get('fetched_at', ''), 'nums': rows}
        n_changed += 1

    # ★ 单独存一份,按 no 索引 —— build_digao.py 重建 digao_data.json 时会冲掉直接写在里面的字段,
    #   所以判定结果必须存在独立文件里,再由 build 合并回去。
    verdicts = {e['no']: e['src_check'] for e in d['entries'] if e.get('src_check')}
    vpath = os.path.join(HERE, 'source_verdicts.json')
    json.dump(verdicts, open(vpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False)
    print('\n【数字判定分布】')
    for k, v in cnt.most_common():
        print('  %-14s %d' % (k, v))
    stc = Counter(e['src_check']['status'] for e in d['entries'] if e.get('url'))
    print('\n【抓取状态（条目级）】')
    for k, v in stc.most_common():
        print('  %-10s %d 条' % (k, v))
    print('\n已写 %s（%d 条）与 %s' % (vpath, len(verdicts), DATA))


if __name__ == '__main__':
    main()
