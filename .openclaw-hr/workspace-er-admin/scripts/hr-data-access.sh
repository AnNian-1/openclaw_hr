#!/usr/bin/env bash
# 行政敏感数据闸门：花名册薪资查询、对话出月报。
# 允许：飞书 HR、无 sender（WebChat / CLI / 演示 *）。
# 拒绝：已登记的飞书主管 / 员工 / owner。未知 ou_ 也拒绝。
#
# 用法:
#   hr-data-access.sh check [sender]
#   hr-data-access.sh role [sender]
# 退出: 0 允许 · 3 拒绝 · 2 用法错
set -euo pipefail

HR_ID="ou_2f67ed66e57e214e72c318a57c60d1c4"
# 主管 / 员工 / owner（与 openclaw.yaml toolsBySender 同一批 ou_）
DENY_IDS=$'ou_85759e2571f33307b6fc7b265060d5c1\nou_66cfc2fa5b3142c6b232fc9114fc7b94\nou_a8cf75f38e774b2c1a5c79117004d965'

normalize_sender() {
  local raw="${1:-}"
  raw="${raw#"${raw%%[![:space:]]*}"}"
  raw="${raw%"${raw##*[![:space:]]}"}"
  raw="${raw#id:}"
  raw="${raw#user:}"
  raw="${raw#channel:feishu:}"
  raw="${raw#feishu:}"
  printf '%s' "$raw"
}

classify() {
  local s
  s="$(normalize_sender "${1:-}")"
  if [ -z "$s" ] || [ "$s" = "*" ] || [ "$s" = "webchat" ] || [ "$s" = "cli" ] || [ "$s" = "demo" ]; then
    echo "demo"
    return
  fi
  if [ "$s" = "$HR_ID" ]; then
    echo "hr"
    return
  fi
  if printf '%s\n' "$DENY_IDS" | grep -qxF "$s"; then
    echo "denied"
    return
  fi
  echo "unknown"
}

cmd="${1:-}"
sender="${2:-}"
case "$cmd" in
  role)
    classify "$sender"
    ;;
  check)
    role="$(classify "$sender")"
    case "$role" in
      hr|demo)
        echo "{\"allowed\":true,\"role\":\"$role\"}"
        exit 0
        ;;
      *)
        echo "{\"allowed\":false,\"role\":\"$role\",\"reason\":\"飞书非 HR 不能查他人工资或出月报\"}"
        exit 3
        ;;
    esac
    ;;
  *)
    echo "usage: hr-data-access.sh check|role [sender]" >&2
    exit 2
    ;;
esac
