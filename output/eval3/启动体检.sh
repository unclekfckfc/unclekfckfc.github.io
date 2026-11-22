#!/usr/bin/env bash
# ★ 发布前体检 · 一键启动（Linux / macOS）
cd "$(dirname "$0")" || exit 1
echo
echo "  =========================================="
echo "    发布前体检 · 本地服务"
echo "  =========================================="
echo
echo "  浏览器会自动打开 http://127.0.0.1:8765/体检"
echo "  ★ 停服务：在这个终端按 Ctrl-C"
echo
python3 serve.py --lan &
SVC_PID=$!
sleep 3
if command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:8765/体检" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then open "http://127.0.0.1:8765/体检" >/dev/null 2>&1 &
fi
wait $SVC_PID
