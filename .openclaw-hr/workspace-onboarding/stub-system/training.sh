#!/bin/bash
# 入职培训安排 stub —— 模拟排定公司级 Onboarding 第一课
NAME="${1:-员工}"
STATE_DIR="$(cd "$(dirname "$0")/.."; pwd)/stub-state"
mkdir -p "$STATE_DIR"
TRAINDATE="$(date -v+1d +%Y-%m-%d 2>/dev/null || date -d '+1 day' +%Y-%m-%d)"
cat > "$STATE_DIR/training.json" <<EOF
{"system":"培训安排","candidate":"${NAME}","course":"公司级 Onboarding 第一课","date":"${TRAINDATE} 09:30","content":"公司介绍/文化/核心制度/安全合规/IT与HR系统使用","status":"已排期"}
EOF
echo "[培训系统 stub] ${NAME} 入职培训已排期 ${TRAINDATE} 09:30 公司级 Onboarding 第一课"
