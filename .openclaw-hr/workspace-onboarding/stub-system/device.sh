#!/bin/bash
# 设备申请 stub —— 模拟向行政系统提交办公设备申请
# 本集不接真实行政系统，把"已申请/已配齐"状态产出为本地 JSON 文件
NAME="${1:-员工}"
STATE_DIR="$(cd "$(dirname "$0")/.."; pwd)/stub-state"
mkdir -p "$STATE_DIR"
ASSET="MBP$(date +%s | tail -c 4)"
cat > "$STATE_DIR/device.json" <<EOF
{"system":"行政设备","candidate":"${NAME}","laptop":"MacBook Pro 14 资产号 ${ASSET}","badge":"门禁卡已制","desk":"3F-A12 工位已分配","status":"已配齐"}
EOF
echo "[行政系统 stub] ${NAME} 设备已配齐，MacBook Pro 14 资产号 ${ASSET} 门禁卡 工位 3F-A12"
