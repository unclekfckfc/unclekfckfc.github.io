#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 平台假设补丁器(幂等)  ② 全 skill 自检总检矩阵

★ 为什么要有这个:这套体系跑在 Windows 上(D:\\.minimax\\skills\\),
  但审阅/交接/CI 环境是 Linux。实测:
    · eval-rig/scripts/gates.py 用 'py -3 "<tool>"' 调子进程 —— Linux 上没有 py ⇒ 9 项自检全挂
    · audit-router/scripts/acceptance.py 硬编码 C:\\Users\\Kc\\... ⇒ 直接 FileNotFoundError
    · 我自己的 check_prototypes.py 读 /tmp 的中间文件 ⇒ 隔天 /tmp 被清就崩在断言之前
  ⇒ 三处都是"护栏自己的可用性没人测"。

用法:
    python3 fix_platform_assumptions.py --target <skills目录> [--dry]
    python3 run_all_selftests.py
"""
import os, re, sys, json, glob, subprocess, datetime, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# ── ① 补丁定义 ──
PATCHES = json.load(open(os.path.join(HERE, 'platform_patches.json'), encoding='utf-8'))['patches']

def apply_patches(target, dry=False):
    """幂等:已打过就跳过。定位靠"行内唯一子串",不做正则。"""
    done, skipped = [], []
    for p in PATCHES:
        f = os.path.join(target, p['file'])
        if not os.path.exists(f):
            skipped.append((p['file'], '文件不存在')); continue
        lines = open(f, encoding='utf-8').read().split('\n')
        hit = [i for i, l in enumerate(lines) if p['match'] in l]
        if not hit:
            skipped.append((p['file'], '锚点没匹配上')); continue
        if p['replace'][0].strip()[:30] in lines[hit[0]]:
            skipped.append((p['file'], '已打过')); continue
        lines[hit[0]:hit[0] + 1] = p['replace']
        if not dry:
            open(f, 'w', encoding='utf-8').write('\n'.join(lines))
        done.append((p['file'], p['why']))
    return done, skipped


# ── ② 全 skill 自检总检 ──
SELFTESTS = [
    ('claim-audit',      'scripts/pipeline.py',      ['--selftest']),
    ('content-evolver',  'scripts/selftest.py',      []),
    ('transcription-guard', 'scripts/selftest.py',  []),
    ('deep-chat-audit',  'scripts/selftest.js',      []),
    ('eval-rig',         'scripts/gates.py',        ['--selftest']),
    ('audit-router',     'scripts/acceptance.py',   []),
    ('cross-audit',      'scripts/merge_findings.py', []),   # 无 --selftest
    ('skill-bench',      'scripts/skill_bench.py',  []),      # 无 --selftest
]


def find_skills_roots():
    roots = []
    for base in ('/workspace/.skills',
                 '/workspace/output/会话归档-2026-11-02/06-原始素材/handoff-2026-11-02-解包/10-skills'):
        if os.path.isdir(base):
            roots.append(base)
    return roots


def run_one(root, name, script, args):
    p = os.path.join(root, name, script)
    if not os.path.exists(p):
        return ('NO-ENTRY', '没有自检入口')
    cmd = ([sys.executable, p] if script.endswith('.py') else ['node', p]) + args
    env = dict(os.environ)
    # skill-bench 要找到 claim-audit 的 scripts 才跑得起来
    env.setdefault('CLAIM_AUDIT_SCRIPTS', os.path.join(root, 'claim-audit', 'scripts'))
    env.setdefault('SKILLS_DIR', root)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=os.path.dirname(p), env=env)
    except subprocess.TimeoutExpired:
        return ('TIMEOUT', '120s 没跑完')
    out = (r.stdout or '') + (r.stderr or '')
    tail = [l for l in out.strip().splitlines() if l.strip()][-1:] or ['']
    if r.returncode == 0:
        return ('PASS', tail[0][:70])
    return ('FAIL', 'exit=%d %s' % (r.returncode, tail[0][:70]))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'fix':
        target = sys.argv[sys.argv.index('--target') + 1] if '--target' in sys.argv else '.'
        dry = '--dry' in sys.argv
        done, skipped = apply_patches(target, dry)
        print('═══ 平台假设补丁 @ %s ═══' % target)
        for f, why in done:
            print('  ✓ %-42s %s' % (f, why))
        for f, why in skipped:
            print('  · %-42s %s' % (f, why))
        return 0

    print('═══ 全 skill 自检总检 @ %s ═══' % datetime.datetime.now().replace(microsecond=0).isoformat())
    roots = find_skills_roots()
    rows = []
    for name, script, args in SELFTESTS:
        row = {'skill': name, 'entry': script, 'status': 'MISSING', 'detail': ''}
        for root in roots:
            if os.path.isdir(os.path.join(root, name)):
                st, det = run_one(root, name, script, args)
                row['status'] = st
                row['detail'] = det
                row['root'] = root
                break
        rows.append(row)
    print('%-24s %-28s %-10s %s' % ('skill', '入口', '结果', '说明'))
    for r in rows:
        print('%-24s %-28s %-10s %s' % (r['skill'], r['entry'], r['status'], r['detail']))
    n_pass = sum(1 for r in rows if r['status'] == 'PASS')
    n_fail = sum(1 for r in rows if r['status'] == 'FAIL')
    n_no = sum(1 for r in rows if r['status'] in ('NO-ENTRY', 'MISSING'))
    print('\n  通过 %d · 挂 %d · 没入口 %d   ← 这就是"护栏覆盖面"的真数' % (n_pass, n_fail, n_no))
    out = os.path.join(HERE, 'selftest_matrix.json')
    json.dump({'at': datetime.datetime.now().replace(microsecond=0).isoformat(),
               'rows': rows, 'n_pass': n_pass, 'n_fail': n_fail, 'n_no_entry': n_no},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('  矩阵已写: %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
