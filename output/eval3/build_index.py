#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《总索引》—— 扫文件系统生成,所以它不会过期。

用法: python3 build_index.py
"""
import os, json, re, hashlib, datetime

OUT = '/workspace/output'
SKILLS = '/workspace/.skills'      # ★ skill 目录也要进索引
BUILT = '2026-11-11'

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            h.update(b)
    return h.hexdigest()[:12]

def size(p):
    n = os.path.getsize(p)
    return '%.1f KB' % (n / 1024) if n < 1024 * 1024 else '%.1f MB' % (n / 1048576)

# ── 分类规则(有序,先匹配先生效) ──
RULES = [
    ('产品原型',      r'^(底稿-结论可查的地方|核验卡-朋友圈版-原型|今日核验)\.html$'),
    ('门禁与脚本',    r'^eval3/'),
    ('规划与操作',    r'^(Runbook|B1-回访包|完整规划|优化分析|俱乐部定位|对话完整分析|对话归档完整分析|产品吸引力|可用性测试报告|数字口径-唯一真源)'),
    ('可上传包',      r'\.(zip)$'),
    ('11-02 归档',    r'^会话归档-'),
    ('分析与研究',    r'\.md$'),
]
def cat(rel):
    for name, pat in RULES:
        if re.search(pat, rel):
            return name
    return '其他'

# ── 每道闸覆盖谁 ──
GATES = [
    ('eval3/check_prototypes.py', '两个核验卡原型', ['核验卡-朋友圈版-原型.html']),
    ('eval3/check_digao.py',      '《底稿》站',       ['底稿-结论可查的地方.html']),
    ('eval3/truth_numbers.py',    '全部文档的数字口径', []),
    ('eval3/gate_relative.py',    '留出集 v2 退化检测', []),
    ('eval3/build_holdout_v2.py', '留出集 v2 切分/复算', []),
    ('eval3/zip_guard.py',        '交付 zip 的路径',   []),
    ('.skills/premise-ledger/scripts/selftest.py', 'premise-ledger skill 自检', []),
]

items = []
for BASE, tag in ((OUT, ''), (SKILLS, 'skill/')):
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if not d.startswith('_ux') and d != '__pycache__']
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, BASE)
            if rel.startswith('_ux') or rel.endswith('.pyc'):
                continue
            if tag == 'skill/' and not rel.startswith('premise-ledger/'):
                continue          # ★ 只索引本次新建的 skill
            items.append((cat(rel), tag + rel, p))

by = {}
for c, rel, p in items:
    by.setdefault(c, []).append((rel, p))

L = []
L.append('# 总索引 · 「阶 · 能力复利台」/ 核材料体系\n')
L.append('> 生成于 **%s** · 扫描 `/workspace/output` + `/workspace/.skills/premise-ledger` 自动生成 · **%d 个文件**\n' % (BUILT, len(items)))
L.append('> **★ 这个索引会过期,所以它是脚本生成的。** 重新跑 `python3 eval3/build_index.py` 即可刷新。\n')
L.append('---\n')

# ── 门禁表 ──
L.append('## 一、门禁(每次改完必跑)\n')
L.append('| 脚本 | 管什么 | 退出码 |\n|---|---|---|')
for rel, what, _ in GATES:
    L.append('| `%s` | %s | 0 = 通过 |' % (rel, what))
L.append('\n**★ 一条命令跑全部:`bash eval3/daily.sh`**\n')
L.append('---\n')

# ── 各类文件 ──
L.append('## 二、产出物\n')
for c in ['产品原型', '规划与操作', '门禁与脚本', '分析与研究', '11-02 归档', '其他']:
    if c not in by:
        continue
    L.append('### %s(%d)\n' % (c, len(by[c])))
    L.append('| 文件 | 大小 | sha256(前12) |\n|---|---|---|')
    for rel, p in sorted(by[c]):
        L.append('| `%s` | %s | `%s` |' % (rel, size(p), sha(p)))
    L.append('')

# ── 这轮真正做出来的结论(短,不重复正文) ──
L.append('---\n')
L.append('## 三、当前口径(现场算,带时点)\n')
canon = json.load(open(os.path.join(OUT, '数字口径-唯一真源.json'), encoding='utf-8'))
t, m = canon['truth'], canon['materials']
L.append('> 取数时点 **%s** · 唯一真源 `数字口径-唯一真源.json`\n' % canon['as_of'])
L.append('| 量 | 值 | 分母 |\n|---|---|---|')
L.append('| 真值唯一 id | **%d** | — |' % t['unique_ids'])
L.append('| 实质判定 | **%d** | 唯一 id %d |' % (t['substantive_judged'], t['unique_ids']))
L.append('| 人判 / agent 盲读 | **%d / %d** | 实质判定 %d |' % (t['by_human'], t['by_agent_blind'], t['substantive_judged']))
L.append('| verdict TN / PROBLEM / UNCLEAR | **%d / %d / %d** | 唯一 id %d |'
         % (t['verdict_TN'], t['verdict_PROBLEM'], t['verdict_UNCLEAR'], t['unique_ids']))
L.append('| 查不了占比 | **%s%%** | 唯一 id %d |' % (t['unclear_ratio_by_unique_ids'], t['unique_ids']))
L.append('| 材料对 / 覆盖 / 从没判过 | **%d / %d / %d** | — |'
         % (m['pairs_total'], m['pairs_covered_by_truth'], m['pairs_never_judged']))
L.append('| 机器 finding | **%d** | 30 条跑过判据路 |' % m['machine_findings_attached'])
L.append('')
L.append('> **★ agent 盲读是模型判读,不是独立信源 —— 不得计入「人工标注」。**\n')

L.append('---\n')
L.append('## 四、这一轮的三件事(其余都是过程)\n')
L.append('1. **B1 回访那 12 个人** —— 12 通电话,不需要任何授权,产出是「卡在第几步」的分布\n')
L.append('2. **把「数字过期」变成机器能查的** —— `truth_numbers.py` 现场算 + 印分母 + 标时点 + 跨文档锚点一致性\n')
L.append('3. **把门禁从绝对阈值改成相对退化检测** —— `gate_relative.py`;同时量出「开发集 75.9% vs 留出集 50.0%」这 26pp\n')

open(os.path.join(OUT, '总索引.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('已生成 总索引.md · %d 个文件' % len(items))
for c in ['产品原型', '规划与操作', '门禁与脚本', '分析与研究', '11-02 归档', '其他']:
    if c in by:
        print('  %-10s %d' % (c, len(by[c])))
