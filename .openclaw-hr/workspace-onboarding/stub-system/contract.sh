#!/bin/bash
# 合同准备 stub —— 模拟生成劳动合同与入职文件
NAME="${1:-员工}"
ROLE="${2:-岗位}"
SALARY="${3:-面议}"
STATE_DIR="$(cd "$(dirname "$0")/.."; pwd)/stub-state"
mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/contract.json" <<EOF
{"system":"合同文件","candidate":"${NAME}","role":"${ROLE}","salary":"${SALARY}","contract":"劳动合同已起草","files":"岗位说明书/保密协议/员工手册确认书 已备齐","probation":"6个月","status":"待审批"}
EOF
echo "[合同系统 stub] ${NAME} ${ROLE} ${SALARY} 劳动合同与入职文件已起草，待 HR 主管审批"
