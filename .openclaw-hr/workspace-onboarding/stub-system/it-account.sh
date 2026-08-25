#!/bin/bash
# IT 账号配置 stub —— 模拟 IT 系统把新员工账号资料配好、待安全审批放行
# 本集不接真实 IT 系统，把"账号已配置、待审批"状态产出为本地 JSON 文件
# 真实环境这里会换成调用企业微信/AD/IT 工单系统的 API
NAME="${1:-员工}"
PINYIN="${2:-employee}"   # 邮箱前缀用拼音，避免中文进 tr 被破坏
STATE_DIR="$(cd "$(dirname "$0")/.."; pwd)/stub-state"
mkdir -p "$STATE_DIR"
WORKNO="XQ$(date +%s | tail -c 5)"
EMAIL="${PINYIN}@xingqiao-tech.com"
cat > "$STATE_DIR/account.json" <<EOF
{"system":"IT账号","candidate":"${NAME}","workno":"${WORKNO}","email":"${EMAIL}","wecom":"已创建","status":"待审批"}
EOF
echo "[IT 系统 stub] ${NAME} 账号资料已配置（工号 ${WORKNO} 邮箱 ${EMAIL} 企业微信），待 IT 安全审批"
