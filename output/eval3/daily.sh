#!/usr/bin/env bash
# ★ 每天开工跑这条 —— 五道闸的退出码全 0 才算今天没做错事
set -e
cd "$(dirname "$0")"
echo "═══ 每日七闸 ═══"
# ★ 先重建中间数据 —— 门禁不能依赖"上次跑过"的临时文件(隔天 /tmp 被清就会崩)
python3 build_digao.py >/dev/null
python3 build_digao_page.py >/dev/null
python3 truth_numbers.py --check
python3 gate_relative.py
python3 check_prototypes.py
python3 check_digao.py
python3 build_holdout_v2.py --verify
# ★ 第六道：二维码端到端（卡 → PNG → 扫码 → 站点）。缺依赖会大声报错,不静默跳过
python3 check_qr.py
python3 check_site.py
# ★ 第八步(非闸):重建「每日精选位」—— 自循环基建的入口页,固定地址、内容每天换
python3 build_today.py
echo
echo "✅ 七闸全过"
