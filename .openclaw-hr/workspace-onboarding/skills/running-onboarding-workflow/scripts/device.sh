#!/bin/bash
# 设备申请 —— 从 HCM 系统读取数据，更新行政设备节点状态
# 数据来源：HCM 系统 API（各部门通过前端填写的数据）
NAME="${1:-员工}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="${STUB_STATE_DIR:-$(cd "$SCRIPT_DIR/.."; pwd)/stub-state}"
mkdir -p "$STATE_DIR"

ASSET="MBP$(date +%s | tail -c 4)"
LAPTOP="MacBook Pro 14 资产号 ${ASSET}"

NOW="$(TZ=Asia/Shanghai date +%Y-%m-%dT%H:%M:%S%:z)"
PREPARED_AT="$NOW"

# 保留首次落盘时间和已有资产号
if [ -f "$STATE_DIR/device.json" ]; then
  EXISTING="$(python3 -c "
import json
d=json.load(open('$STATE_DIR/device.json'))
print(d.get('prepared_at',''))
print(d.get('laptop',''))
" 2>/dev/null)"
  EXISTING_PREPARED="$(printf '%s\n' "$EXISTING" | sed -n '1p')"
  EXISTING_LAPTOP="$(printf '%s\n' "$EXISTING" | sed -n '2p')"
  [ -n "$EXISTING_PREPARED" ] && PREPARED_AT="$EXISTING_PREPARED"
  [ -n "$EXISTING_LAPTOP" ] && LAPTOP="$EXISTING_LAPTOP"
fi

# 从 HCM API 读取已有数据
HCM_DATA="$(python3 - "$SCRIPT_DIR" "$NAME" "$LAPTOP" "$PREPARED_AT" "$NOW" <<'PY'
import sys, os, json
sys.path.insert(0, sys.argv[1])
import hcm_api

name, laptop_default, prepared_at, now = sys.argv[2:6]

stub_dir = os.environ.get("STUB_STATE_DIR", "")
pinyin = os.path.basename(stub_dir.rstrip("/")) if stub_dir else ""

candidate_info = hcm_api.get_candidate_info(pinyin) if pinyin else None
api_data = hcm_api.get_prep_node_data(pinyin, "device") if pinyin else {}

result = {
    "system": "行政设备",
    "candidate": (candidate_info or {}).get("name", name),
    "laptop": api_data.get("laptop", laptop_default),
    "badge": api_data.get("badge", "门禁卡已制"),
    "desk": api_data.get("desk", "3F-A12 工位已分配"),
    "status": "已配齐",
    "prepared_at": api_data.get("prepared_at", prepared_at),
    "updated_at": now,
}

if pinyin:
    hcm_api.update_prep_node(pinyin, "device", status="completed", data=result)

print(json.dumps(result, ensure_ascii=False))
PY
)"

if [ -n "$HCM_DATA" ]; then
  echo "$HCM_DATA" > "$STATE_DIR/device.json"
  echo "[行政] ${NAME} 设备已配齐 (HCM API + 本地已更新)"
else
  cat > "$STATE_DIR/device.json" <<EOF
{"system":"行政设备","candidate":"${NAME}","laptop":"${LAPTOP}","badge":"门禁卡已制","desk":"3F-A12 工位已分配","status":"已配齐","prepared_at":"${PREPARED_AT}","updated_at":"${NOW}"}
EOF
  echo "[行政] ${NAME} 设备已配齐 (本地 fallback)"
fi
