#!/bin/bash
# 合同准备 —— 从 HCM 系统读取候选人数据，更新合同节点状态
# 参数：name role salary [status]
#   status 默认「待审批」；合同门通过后由 lobster 以「已通过」再调一次，刷新 updated_at
#
# 数据来源：HCM 系统 API（各部门通过前端填写的数据）
# 写入方式：PUT /api/candidates/{id}/prep/contract（合并更新）
# 兼容：同时写本地 JSON（供 build-approval-prompt.py 读取）
NAME="${1:-员工}"
ROLE="${2:-岗位}"
SALARY="${3:-面议}"
STATUS="${4:-待审批}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# stub 状态产出目录（兼容旧流程）
STATE_DIR="${STUB_STATE_DIR:-$(cd "$SCRIPT_DIR/.."; pwd)/stub-state}"
mkdir -p "$STATE_DIR"

NOW="$(TZ=Asia/Shanghai date +%Y-%m-%dT%H:%M:%S%:z)"
PREPARED_AT="$NOW"

# 保留首次落盘时间
if [ -f "$STATE_DIR/contract.json" ]; then
  EXISTING_PREPARED="$(python3 -c "import json,sys; d=json.load(open('$STATE_DIR/contract.json')); print(d.get('prepared_at',''))" 2>/dev/null)"
  [ -n "$EXISTING_PREPARED" ] && PREPARED_AT="$EXISTING_PREPARED"
fi

# 从 HCM API 读取已有数据（部门通过前端填写的）
# 若 API 有数据，优先使用；否则用参数传入的值
HCM_DATA="$(python3 - "$SCRIPT_DIR" "$NAME" "$ROLE" "$SALARY" "$STATUS" "$PREPARED_AT" "$NOW" <<'PY'
import sys, os
sys.path.insert(0, sys.argv[1])
import hcm_api

name, role, salary, status, prepared_at, now = sys.argv[2:8]

# 从 workflow.json 读 pinyin（STUB_STATE_DIR 环境变量指向候选人目录）
stub_dir = os.environ.get("STUB_STATE_DIR", "")
pinyin = os.path.basename(stub_dir.rstrip("/")) if stub_dir else ""

candidate_info = None
api_data = {}
if pinyin:
    candidate_info = hcm_api.get_candidate_info(pinyin)
    api_data = hcm_api.get_prep_node_data(pinyin, "contract")

# 合并：API 数据 > 参数传入值
import json
result = {
    "system": "合同文件",
    "candidate": (candidate_info or {}).get("name", name),
    "role": api_data.get("role") or (candidate_info or {}).get("role", role),
    "salary": api_data.get("salary") or (candidate_info or {}).get("salary", salary),
    "contract": api_data.get("contract", "劳动合同已起草"),
    "files": api_data.get("files", "岗位说明书/保密协议/员工手册确认书 已备齐"),
    "probation": api_data.get("probation", "6个月"),
    "status": status,
    "prepared_at": api_data.get("prepared_at", prepared_at),
    "updated_at": now,
}

# 不向 HCM 写入——部门节点由各部门在 HCM 维护
print(json.dumps(result, ensure_ascii=False))
PY
)"

# 写本地 JSON（兼容 build-approval-prompt.py）
if [ -n "$HCM_DATA" ]; then
  echo "$HCM_DATA" > "$STATE_DIR/contract.json"
  echo "[合同] ${NAME} ${ROLE} ${SALARY} status=${STATUS} (HCM API + 本地已更新)"
else
  # API 不可用时回退到纯本地模式
  cat > "$STATE_DIR/contract.json" <<EOF
{"system":"合同文件","candidate":"${NAME}","role":"${ROLE}","salary":"${SALARY}","contract":"劳动合同已起草","files":"岗位说明书/保密协议/员工手册确认书 已备齐","probation":"6个月","status":"${STATUS}","prepared_at":"${PREPARED_AT}","updated_at":"${NOW}"}
EOF
  echo "[合同] ${NAME} ${ROLE} ${SALARY} status=${STATUS} (本地 fallback)"
fi
