#!/usr/bin/env bash
# run-onboarding.sh —— running-onboarding-workflow Skill 的入职审批工作流启动器
#
# 用途：把"用 lobster 跑 hr-onboarding.lobster 入职审批工作流"这件确定性的事
#       固化进一个脚本——Agent 只需照一条命令调用，不必猜 lobster 的 action /
#       pipeline 路径 / cwd 该怎么传（基线测试里 Agent 正是连错两次才蒙对）。
#
# 它解决五件封装期的真实问题：
#   1. lobster CLI 入口定位——固定指向 @clawdbot/lobster 的 bin。
#   2. 路径推导——$STUB 指向本 Skill 的 scripts/（工作流文件 + 5 个 stub 都在这），
#      $STATE 指向 workspace 根的 stub-state/（review / 看板两个下游 Skill 要读它）。
#      路径由本脚本所在位置反推，不依赖调用方在哪个目录。
#   3. 环境变量注入——lobster 默认透传外部 env 到每个 run 子 shell，前提是这些
#      env 在调 lobster 前 export；本脚本 export $STUB / $STATE / $STUB_STATE_DIR / $WORKSPACE。
#   4. 多候选人隔离——每个候选人独立子目录 stub-state/<pinyin>/，
#      并发入职互不冲突（5 文件平铺会撞路径，子目录天然避免）。
#      注意：$STUB_STATE_DIR 必须在 case start 分支拿到 $PINYIN 后才能拼，
#      不能在文件顶部 export（那时 $PINYIN 还没解析）。
#   5. lobster 返回后回写 approval_id / resume_token 到 workflow.json——
#      这两个值在 run 块内拿不到（lobster 在 approval: true 之后才生成），
#      所以本脚本捕获 lobster stdout，再调 update-workflow.py attach。
#
# 用法：
#   run-onboarding.sh start [--force] <name> <pinyin> <role> <salary>
#   run-onboarding.sh resume <token> yes|no
#   run-onboarding.sh dry    <name> <pinyin> <role> <salary>
#
# 退出码：0 = lobster 正常返回（含 needs_approval / ok / cancelled，都属正常）；
#         非 0 = 启动器自身的前置检查失败（文件缺失等）或 lobster 进程异常。
set -euo pipefail

# lobster 子进程会继承本 PATH。openclaw 的 shebang 是 env node：
# 只保证「找得到 openclaw」不够，PATH 里若先是 Node 20，cron add 会直接失败。
_PREPEND_NODE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/scripts/prepend-node22.sh"
# shellcheck disable=SC1090
[ -f "$_PREPEND_NODE" ] && . "$_PREPEND_NODE"
export OPENCLAW_HR_BIN="${OPENCLAW_HR_BIN:-$(command -v openclaw || true)}"

# HCM_API_URL 与 HCM_API_BASE 等价，统一导出给 python 子进程
if [ -n "${HCM_API_BASE:-}" ] && [ -z "${HCM_API_URL:-}" ]; then
  export HCM_API_URL="$HCM_API_BASE"
fi
if [ -n "${HCM_API_URL:-}" ] && [ -z "${HCM_API_BASE:-}" ]; then
  export HCM_API_BASE="$HCM_API_URL"
fi
export HCM_API_URL="${HCM_API_URL:-http://127.0.0.1:8000}"
export HCM_API_BASE="${HCM_API_BASE:-$HCM_API_URL}"

# ── 路径推导：由本脚本位置反推，不依赖调用方 cwd ────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # …/skills/running-onboarding-workflow/scripts
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"                    # …/skills/running-onboarding-workflow
WORKSPACE="$(cd "$SKILL_DIR/../.." && pwd)"                  # …/workspace-onboarding

WORKFLOW="$SCRIPT_DIR/hr-onboarding.lobster"   # 工作流文件，和本脚本同在 scripts/
# stub 脚本目录 = 本脚本所在目录（5 个 stub 与本脚本同在 scripts/）
export STUB="$SCRIPT_DIR"
# stub 状态产出目录 = workspace 根的 stub-state/（review、看板下游 Skill 读这里）
export STATE="$WORKSPACE/stub-state"
# 注意：STUB_STATE_DIR 不在此 export——它需要 $PINYIN 才能拼成 $STATE/<pinyin>/，
# 而 $PINYIN 在 case start 分支才解析。见下方 start|dry 分支。
# workspace 根，记录 pending 审批快照到 <WORKSPACE>/pending-approvals/
export WORKSPACE
# lobster args.pinyin 通过 ${pinyin} template 替换传给 record-pending-approval.py；
# 不走 $PINYIN 环境变量（lobster 不注入 args 到 env）。本脚本不需在此 export。

# lobster CLI：PATH 优先；fallback 为 profile 根 node_modules（本脚本在 workspace-onboarding 下）
PROFILE_DIR="$(cd "$WORKSPACE/.." && pwd)"
LOBSTER="$(command -v lobster 2>/dev/null || true)"
LOBSTER_FALLBACK="$PROFILE_DIR/node_modules/.bin/lobster"
[ -z "$LOBSTER" ] && [ -x "$LOBSTER_FALLBACK" ] && LOBSTER="$LOBSTER_FALLBACK"

# ── 前置检查：solve-don't-punt，文件缺失立即明确报错 ──────────────
fail() { echo "[run-onboarding] 错误：$1" >&2; exit 3; }
[ -f "$WORKFLOW" ] || fail "工作流文件不存在：$WORKFLOW"
[ -x "$LOBSTER" ]  || fail "lobster CLI 不在 PATH 里、且 $LOBSTER_FALLBACK 不存在。
请先安装 lobster：npm install @clawdbot/lobster --prefix $PROFILE_DIR
然后 source $PROFILE_DIR/env.sh 让 lobster 二进制入 PATH。"
for s in contract.sh it-account.sh device.sh buddy.sh training.sh \
         build-approval-prompt.py record-pending-approval.py update-workflow.py \
         emit-approval-verbatim.py snapshot_hcm_prep.py; do
  [ -f "$SCRIPT_DIR/$s" ] || fail "依赖脚本缺失：$SCRIPT_DIR/$s"
done
mkdir -p "$STATE"

# HCM 花名册先行：小慧只读、不写 HCM。start/dry 前必须能在 HCM 查到该拼音。
# 覆盖：HCM_API_URL 或 HCM_API_BASE（默认 http://127.0.0.1:8000）
require_hcm_candidate() {
  local pinyin="$1"
  local base="${HCM_API_URL:-${HCM_API_BASE:-http://127.0.0.1:8000}}"
  local url="${base%/}/api/candidates"
  local body
  if ! body="$(curl -sS -m 5 "$url" 2>/dev/null)"; then
    fail "无法连接 HCM（$url）。请先启动 HCM，再在花名册新建拼音「${pinyin}」的候选人后重试。"
  fi
  if ! PINYIN="$pinyin" BODY="$body" python3 -c '
import json, os, sys
pinyin = os.environ["PINYIN"]
try:
    data = json.loads(os.environ["BODY"])
except json.JSONDecodeError:
    sys.exit(2)
if not isinstance(data, list):
    data = data.get("candidates") or data.get("items") or []
ok = any(isinstance(c, dict) and c.get("pinyin") == pinyin for c in data)
sys.exit(0 if ok else 1)
'; then
    local rc=$?
    if [ "$rc" = "2" ]; then
      fail "HCM 返回无法解析（$url）。请确认服务正常。"
    fi
    fail "HCM 花名册中没有拼音「${pinyin}」的候选人。请先在 HCM（看板或 POST /api/candidates）建档，再启动入职流程。小慧不会向 HCM 写入。"
  fi
  echo "[run-onboarding] HCM 已有候选人拼音=${pinyin}，继续" >&2
}

# 进审批门前：合同节点须在 HCM 为 in_progress/completed。未齐则只记 waiting，不跑 lobster。
require_contract_gate_ready() {
  local name="$1"
  local pinyin="$2"
  set +e
  python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$pinyin" --name "$name" \
    --nodes contract,account,device,training,buddy \
    --require-gate contract
  local rc=$?
  set -e
  if [ "$rc" = "6" ]; then
    python3 "$SCRIPT_DIR/update-workflow.py" init "$pinyin" "$name" "$ROLE" "$SALARY" >/dev/null || true
    python3 "$SCRIPT_DIR/update-workflow.py" event "$pinyin" prep waiting \
      "HCM 合同节点未齐，未启动审批。请催 HR 在 HCM 填写后再 start。" >/dev/null || true
    echo "[run-onboarding] 未进入审批：HCM 合同尚未开始/完成。入职小慧不代替部门填写。请催办后再次 start。" >&2
    return 6
  fi
  if [ "$rc" != "0" ]; then
    return "$rc"
  fi
  return 0
}

# 捕获 lobster 输出 → attach approval_id/resume_token → 原样把 lobster JSON 打到 stdout
# 注意：不用 exec，否则无法做回写。
run_lobster_and_attach() {
  local pinyin="$1"
  shift
  local out
  out="$(mktemp -t lobster-out.XXXXXX)"
  # lobster 退出码非 0 也要把输出交还给调用方；attach 失败不阻断主输出
  set +e
  "$LOBSTER" "$@" >"$out" 2>/tmp/lobster-stderr.$$
  local rc=$?
  set -e
  if [ -s /tmp/lobster-stderr.$$ ]; then
    cat /tmp/lobster-stderr.$$ >&2
  fi
  rm -f /tmp/lobster-stderr.$$
  # 回写 workflow.json（失败只打警告，不改 lobster 退出码）
  if [ -n "$pinyin" ]; then
    export STUB_STATE_DIR="$STATE/$pinyin"
    python3 "$SCRIPT_DIR/update-workflow.py" attach "$pinyin" "$out" >/dev/null || \
      echo "[run-onboarding] 警告：attach approval_id/resume_token 失败" >&2
    # 强制原样交回块 → 脚本自身写 stderr（勿再 >&2 套一层，避免重复）
    python3 "$SCRIPT_DIR/emit-approval-verbatim.py" "$pinyin" || true
  fi
  cat "$out"
  rm -f "$out"
  return "$rc"
}

ACTION="${1:-}"
case "$ACTION" in
  start|dry)
    rest=("${@:2}")
    FORCE=0
    if [ "${rest[0]:-}" = "--force" ]; then
      FORCE=1
      rest=("${rest[@]:1}")
    fi
    NAME="${rest[0]:-新员工}"; PINYIN="${rest[1]:-employee}"; ROLE="${rest[2]:-工程师}"; SALARY="${rest[3]:-面议}"
    # 先查 HCM 花名册（只读），没有该拼音则拒绝，不建 stub、不调 lobster
    require_hcm_candidate "$PINYIN"
    # stub 目录改为按候选人隔离：STUB_STATE_DIR = $STATE/<pinyin>/
    # 5 个 stub 脚本不改，只读取 $STUB_STATE_DIR 环境变量，自然落到候选人子目录下。
    # 此处 export 后 lobster 会透传给每个 run 子 shell。
    export STUB_STATE_DIR="$STATE/$PINYIN"
    mkdir -p "$STUB_STATE_DIR"
    ARGS_JSON=$(NAME="$NAME" PINYIN="$PINYIN" ROLE="$ROLE" SALARY="$SALARY" python3 -c \
      'import json,os; print(json.dumps({"name":os.environ["NAME"],"pinyin":os.environ["PINYIN"],"role":os.environ["ROLE"],"salary":os.environ["SALARY"]},ensure_ascii=False))')
    # completed 后再 start 会抹掉扭转轨迹；须显式 --force
    # waiting_departments 允许再次 start（部门补齐后继续）
    if [ "$ACTION" = "start" ] && [ "$FORCE" != 1 ] && [ -f "$STUB_STATE_DIR/workflow.json" ]; then
      st="$(python3 - "$STUB_STATE_DIR/workflow.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("status") or "")
PY
)"
      if [ "$st" = "completed" ]; then
        fail "拼音 ${PINYIN} 已有 status=completed 的入职工作流，拒绝静默覆盖。确认重跑请：run-onboarding.sh start --force ${NAME} ${PINYIN} ${ROLE} ${SALARY}"
      fi
      if [ "$st" = "halted" ]; then
        fail "拼音 ${PINYIN} 审批正在 halt，请 resume，不要重新 start（除非 --force）。"
      fi
    fi
    if [ "$ACTION" = "start" ]; then
      set +e
      require_contract_gate_ready "$NAME" "$PINYIN"
      gate_rc=$?
      set -e
      if [ "$gate_rc" = "6" ]; then
        exit 6
      fi
      if [ "$gate_rc" != "0" ]; then
        exit "$gate_rc"
      fi
      rm -f "$STUB_STATE_DIR"/contract.json "$STUB_STATE_DIR"/account.json "$STUB_STATE_DIR"/device.json \
            "$STUB_STATE_DIR"/buddy.json "$STUB_STATE_DIR"/training.json \
            "$STUB_STATE_DIR"/workflow.json
      run_lobster_and_attach "$PINYIN" run --file "$WORKFLOW" --args-json "$ARGS_JSON"
    else
      exec "$LOBSTER" run --dry-run --file "$WORKFLOW" --args-json "$ARGS_JSON"
    fi
    ;;
  resume)
    TOKEN="${2:-}"; DECISION="${3:-}"
    [ -n "$TOKEN" ] || fail "resume 需要 resumeToken 作为第 2 个参数"
    case "$DECISION" in
      yes|no)
        # 从旧 token 反查 pinyin，才能定位 stub-state/<pinyin>/workflow.json
        PINYIN=$(python3 "$SCRIPT_DIR/update-workflow.py" pinyin-from-token "$TOKEN" 2>/dev/null || true)
        if [ -z "$PINYIN" ]; then
          echo "[run-onboarding] 警告：无法从 resumeToken 反查 pinyin，跳过 attach" >&2
        else
          export STUB_STATE_DIR="$STATE/$PINYIN"
        fi
        run_lobster_and_attach "$PINYIN" resume --token "$TOKEN" --approve "$DECISION"
        ;;
      *) fail "resume 的决定必须是 yes 或 no，收到：'$DECISION'" ;;
    esac
    ;;
  *)
    fail "未知操作 '$ACTION'。用法：run-onboarding.sh start|resume|dry ..."
    ;;
esac
