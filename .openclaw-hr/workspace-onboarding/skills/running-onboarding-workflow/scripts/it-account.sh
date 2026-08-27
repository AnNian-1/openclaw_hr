#!/bin/bash
# IT 账号配置 —— 从 HCM 系统读取数据，更新 IT 账号节点状态
# 参数：name pinyin [status]
#   status 默认「待审批」；进 account_gate 前传「已审批」刷新落盘
#
# 数据来源：HCM 系统 API（各部门通过前端填写的数据）
NAME="${1:-员工}"
PINYIN="${2:-employee}"
STATUS="${3:-待审批}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="${STUB_STATE_DIR:-$(cd "$SCRIPT_DIR/.."; pwd)/stub-state}"
mkdir -p "$STATE_DIR"

WORKNO="XQ$(date +%s | tail -c 5)"
EMAIL="${PINYIN}@xingqiao-tech.com"

NOW="$(TZ=Asia/Shanghai date +%Y-%m-%dT%H:%M:%S%:z)"
PREPARED_AT="$NOW"

# 保留首次落盘时间和已有工号/邮箱
if [ -f "$STATE_DIR/account.json" ]; then
  EXISTING="$(python3 -c "
import json
d=json.load(open('$STATE_DIR/account.json'))
print(d.get('prepared_at',''))
print(d.get('workno',''))
print(d.get('email',''))
" 2>/dev/null)"
  EXISTING_PREPARED="$(printf '%s\n' "$EXISTING" | sed -n '1p')"
  EXISTING_WORKNO="$(printf '%s\n' "$EXISTING" | sed -n '2p')"
  EXISTING_EMAIL="$(printf '%s\n' "$EXISTING" | sed -n '3p')"
  [ -n "$EXISTING_PREPARED" ] && PREPARED_AT="$EXISTING_PREPARED"
  [ -n "$EXISTING_WORKNO" ] && WORKNO="$EXISTING_WORKNO"
  [ -n "$EXISTING_EMAIL" ] && EMAIL="$EXISTING_EMAIL"
fi

# 从 HCM API 读取已有数据
HCM_DATA="$(python3 - "$SCRIPT_DIR" "$NAME" "$PINYIN" "$STATUS" "$WORKNO" "$EMAIL" "$PREPARED_AT" "$NOW" <<'PY'
import sys, os, json
sys.path.insert(0, sys.argv[1])
import hcm_api

name, pinyin, status, workno, email, prepared_at, now = sys.argv[2:9]

candidate_info = hcm_api.get_candidate_info(pinyin)
api_data = hcm_api.get_prep_node_data(pinyin, "account")

result = {
    "system": "IT账号",
    "candidate": (candidate_info or {}).get("name", name),
    "workno": api_data.get("workno", workno),
    "email": api_data.get("email", email),
    "wecom": api_data.get("wecom", "已创建"),
    "status": status,
    "prepared_at": api_data.get("prepared_at", prepared_at),
    "updated_at": now,
}

# 不向 HCM 写入——部门节点由各部门在 HCM 维护
print(json.dumps(result, ensure_ascii=False))
PY
)"

if [ -n "$HCM_DATA" ]; then
  echo "$HCM_DATA" > "$STATE_DIR/account.json"
  echo "[IT] ${NAME} 账号已配置 status=${STATUS} (HCM API + 本地已更新)"
else
  cat > "$STATE_DIR/account.json" <<EOF
{"system":"IT账号","candidate":"${NAME}","workno":"${WORKNO}","email":"${EMAIL}","wecom":"已创建","status":"${STATUS}","prepared_at":"${PREPARED_AT}","updated_at":"${NOW}"}
EOF
  echo "[IT] ${NAME} 账号已配置 status=${STATUS} (本地 fallback)"
fi
