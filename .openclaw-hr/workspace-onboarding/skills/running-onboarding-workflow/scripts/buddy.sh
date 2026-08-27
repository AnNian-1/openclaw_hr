#!/bin/bash
# Buddy 匹配 —— 从 HCM 系统读取数据，更新 Buddy 节点状态
# 数据来源：HCM 系统 API（各部门通过前端填写的数据）
NAME="${1:-员工}"
ROLE="${2:-岗位}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="${STUB_STATE_DIR:-$(cd "$SCRIPT_DIR/.."; pwd)/stub-state}"
mkdir -p "$STATE_DIR"

NOW="$(TZ=Asia/Shanghai date +%Y-%m-%dT%H:%M:%S%:z)"
PREPARED_AT="$NOW"

# 保留首次落盘时间
if [ -f "$STATE_DIR/buddy.json" ]; then
  EXISTING_PREPARED="$(python3 -c "import json,sys; d=json.load(open('$STATE_DIR/buddy.json')); print(d.get('prepared_at',''))" 2>/dev/null)"
  [ -n "$EXISTING_PREPARED" ] && PREPARED_AT="$EXISTING_PREPARED"
fi

# 从 HCM API 读取已有数据
HCM_DATA="$(python3 - "$SCRIPT_DIR" "$NAME" "$ROLE" "$PREPARED_AT" "$NOW" <<'PY'
import sys, os, json
sys.path.insert(0, sys.argv[1])
import hcm_api

name, role, prepared_at, now = sys.argv[2:6]

stub_dir = os.environ.get("STUB_STATE_DIR", "")
pinyin = os.path.basename(stub_dir.rstrip("/")) if stub_dir else ""

candidate_info = hcm_api.get_candidate_info(pinyin) if pinyin else None
api_data = hcm_api.get_prep_node_data(pinyin, "buddy") if pinyin else {}

result = {
    "system": "Buddy匹配",
    "candidate": (candidate_info or {}).get("name", name),
    "role": (candidate_info or {}).get("role", role),
    "buddy": api_data.get("buddy", "王工 后端组 司龄3年"),
    "mentor": api_data.get("mentor", "李经理 后端组负责人"),
    "status": "已匹配",
    "prepared_at": api_data.get("prepared_at", prepared_at),
    "updated_at": now,
}

# 不向 HCM 写入——部门节点由各部门在 HCM 维护
print(json.dumps(result, ensure_ascii=False))
PY
)"

if [ -n "$HCM_DATA" ]; then
  echo "$HCM_DATA" > "$STATE_DIR/buddy.json"
  echo "[Buddy] ${NAME} 已匹配 (HCM API + 本地已更新)"
else
  cat > "$STATE_DIR/buddy.json" <<EOF
{"system":"Buddy匹配","candidate":"${NAME}","role":"${ROLE}","buddy":"王工 后端组 司龄3年","mentor":"李经理 后端组负责人","status":"已匹配","prepared_at":"${PREPARED_AT}","updated_at":"${NOW}"}
EOF
  echo "[Buddy] ${NAME} 已匹配 (本地 fallback)"
fi
