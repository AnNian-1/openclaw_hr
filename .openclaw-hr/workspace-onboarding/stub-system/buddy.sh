#!/bin/bash
# Buddy 匹配 stub —— 模拟为新员工匹配带教导师
NAME="${1:-员工}"
ROLE="${2:-岗位}"
STATE_DIR="$(cd "$(dirname "$0")/.."; pwd)/stub-state"
mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/buddy.json" <<EOF
{"system":"Buddy匹配","candidate":"${NAME}","role":"${ROLE}","buddy":"王工 后端组 司龄3年","mentor":"李经理 后端组负责人","status":"已匹配"}
EOF
echo "[Buddy 系统 stub] ${NAME} 已匹配 Buddy 王工 后端组，带教导师 李经理"
