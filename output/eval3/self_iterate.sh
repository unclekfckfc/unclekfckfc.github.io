#!/usr/bin/env bash
# ★ 自迭代:一条命令跑完「拉料 → 核 → 建站 → 精选 → 归档 → 自检」
# ★ 它是给任何外部定时器(GitHub Actions / livepage report_task / 本机 cron)调的入口。
# ★ 幂等:同一天重复跑,除非上游出新料,否则产物不变。
set -e
cd "$(dirname "$0")"

echo "═══ 自迭代 $(date '+%Y-%m-%d %H:%M:%S') ═══"

# ① 拉上游新料 + 核验(只抓没有缓存的,老的走缓存 —— 12 天跑下来的增量只花了几分钟)
python3 seed_cards.py

# ② 重建全部产物(免码站 272 页 + 270 张 og:image)
python3 build_site.py
python3 build_og.py

# ③ 每日精选位:固定地址 today.html,内容每天换(自循环基建的入口)
python3 build_today.py

# ④ 七道闸 —— 自检不过就不算今天没做错事
./daily.sh

# ④½ 公开面:只拷「今天那一张卡 + 精选页」—— 暴露面 = 1 条 + 1 个出处链接
python3 build_public.py

# ④¾ RSS:往期页 + feed.xml —— ★ 这是唯一一条【不需要读者能打开我的站】的分发腿
python3 build_feed.py

# ⑤ 分享图 —— ★ 【卡集变了才重画】:每天 103 张要 2 分钟,★ 而卡集只在新料来时才变。
#   指纹 = 全部 (卡 id, 核验号) 序列;★ 没变就跳过,★ 省下的时间给核验。
python3 - <<'PY'
import json, hashlib, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath('self_iterate.sh'))
cs = json.load(open('seed_cards.json', encoding='utf-8'))['cards']
fp = hashlib.sha256('|'.join('%s:%s' % (c['id'], c['no']) for c in cs).encode()).hexdigest()[:16]
old = ''
try:
    old = open('share_fingerprint.txt', encoding='utf-8').read().strip()
except Exception:
    pass
if fp != old:
    r = subprocess.run([sys.executable, 'make_seed_shares.py'], capture_output=True, text=True)
    sys.stdout.write(r.stdout[-400:]); sys.stderr.write(r.stderr[-400:])
    if r.returncode == 0:
        open('share_fingerprint.txt', 'w', encoding='utf-8').write(fp)
        print('  ✓ 卡集变了(%s → %s),分享图已重画' % (old or '无', fp))
    else:
        print('  ★ 分享图重画失败(不阻断)')
else:
    print('  · 卡集没变,分享图跳过')
PY

# ⑤ 发布:把今天那一条推到 livepage 的同一页(同一链接,内容每天换)+ 订阅码推送
# ★ 这一步需要 livepage 凭证,没有就跳过(本地产物仍然是完整的)
if [ -n "$LIVEPAGE_TOKEN" ]; then
  python3 publish_livepage.py || echo "  ★ livepage 发布跳过(不影响本体)"
else
  echo "  · 跳过 livepage 发布(没设 LIVEPAGE_TOKEN)"
fi

echo
echo "✅ 自迭代完成:$(python3 -c "
import json;d=json.load(open('seed_cards.json',encoding='utf-8'));print(len(d['cards']),'条')")"
