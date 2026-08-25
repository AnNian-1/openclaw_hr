#!/bin/bash
# 入职培训安排 —— 从 HCM 系统读取数据，更新培训节点状态
# 数据来源：HCM 系统 API（各部门通过前端填写的数据）
NAME="${1:-员工}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="${STUB_STATE_DIR:-$(cd "$SCRIPT_DIR/.."; pwd)/stub-state}"
mkdir -p "$STATE_DIR"

TRAINDATE="$(date -v+1d +%Y-%m-%d 2>/dev/null || date -d '+1 day' +%Y-%m-%d)"
TRAIN_SLOT="${TRAINDATE} 09:30"

NOW="$(TZ=Asia/Shanghai date +%Y-%m-%dT%H:%M:%S%:z)"
PREPARED_AT="$NOW"

# 保留首次落盘时间和已有培训日期
if [ -f "$STATE_DIR/training.json" ]; then
  EXISTING="$(python3 -c "
import json
d=json.load(open('$STATE_DIR/training.json'))
print(d.get('prepared_at',''))
print(d.get('date',''))
" 2>/dev/null)"
  EXISTING_PREPARED="$(printf '%s\n' "$EXISTING" | sed -n '1p')"
  EXISTING_DATE="$(printf '%s\n' "$EXISTING" | sed -n '2p')"
  [ -n "$EXISTING_PREPARED" ] && PREPARED_AT="$EXISTING_PREPARED"
  [ -n "$EXISTING_DATE" ] && TRAIN_SLOT="$EXISTING_DATE"
fi

# 从 HCM API 读取已有数据
HCM_DATA="$(python3 - "$SCRIPT_DIR" "$NAME" "$TRAIN_SLOT" "$PREPARED_AT" "$NOW" <<'PY'
import sys, os, json
sys.path.insert(0, sys.argv[1])
import hcm_api

name, train_default, prepared_at, now = sys.argv[2:6]

stub_dir = os.environ.get("STUB_STATE_DIR", "")
pinyin = os.path.basename(stub_dir.rstrip("/")) if stub_dir else ""

candidate_info = hcm_api.get_candidate_info(pinyin) if pinyin else None
api_data = hcm_api.get_prep_node_data(pinyin, "training") if pinyin else {}

result = {
    "system": "培训安排",
    "candidate": (candidate_info or {}).get("name", name),
    "course": api_data.get("course", "公司级 Onboarding 第一课"),
    "date": api_data.get("date", train_default),
    "content": api_data.get("content", "公司介绍/文化/核心制度/安全合规/IT与HR系统使用"),
    "status": "已排期",
    "prepared_at": api_data.get("prepared_at", prepared_at),
    "updated_at": now,
}

if pinyin:
    hcm_api.update_prep_node(pinyin, "training", status="completed", data=result)

print(json.dumps(result, ensure_ascii=False))
PY
)"

if [ -n "$HCM_DATA" ]; then
  echo "$HCM_DATA" > "$STATE_DIR/training.json"
  echo "[培训] ${NAME} 培训已排期 (HCM API + 本地已更新)"
else
  cat > "$STATE_DIR/training.json" <<EOF
{"system":"培训安排","candidate":"${NAME}","course":"公司级 Onboarding 第一课","date":"${TRAIN_SLOT}","content":"公司介绍/文化/核心制度/安全合规/IT与HR系统使用","status":"已排期","prepared_at":"${PREPARED_AT}","updated_at":"${NOW}"}
EOF
  echo "[培训] ${NAME} 培训已排期 (本地 fallback)"
fi
