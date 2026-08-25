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
#   run-onboarding.sh start  <name> <pinyin> <role> <salary>   # 启动工作流（到第一个审批门 halt）
#   run-onboarding.sh resume <token> yes|no                    # 批准/拒绝一个审批门
#   run-onboarding.sh dry    <name> <pinyin> <role> <salary>   # dry-run，只打印执行计划
#
# 退出码：0 = lobster 正常返回（含 needs_approval / ok / cancelled，都属正常）；
#         非 0 = 启动器自身的前置检查失败（文件缺失等）或 lobster 进程异常。
set -euo pipefail

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

# lobster CLI 入口：用 `command -v lobster` 走 PATH 找
# env.sh 已 export PATH 包含 $HOME/.openclaw-hr/node_modules/.bin；
# 不写死具体路径——npm install 装 lobster 可能换其它 scope 名，避免环境漂移。
LOBSTER="$(command -v lobster 2>/dev/null || true)"
LOBSTER_FALLBACK="$HOME/.openclaw-hr/node_modules/.bin/lobster"
[ -z "$LOBSTER" ] && [ -x "$LOBSTER_FALLBACK" ] && LOBSTER="$LOBSTER_FALLBACK"

# ── 前置检查：solve-don't-punt，文件缺失立即明确报错 ──────────────
fail() { echo "[run-onboarding] 错误：$1" >&2; exit 3; }
[ -f "$WORKFLOW" ] || fail "工作流文件不存在：$WORKFLOW"
[ -x "$LOBSTER" ]  || fail "lobster CLI 不在 PATH 里、且 $LOBSTER_FALLBACK 不存在。
请先安装 lobster：npm install @clawdbot/lobster --prefix \$HOME/.openclaw-hr
然后 source ~/.openclaw-hr/env.sh 让 lobster 二进制入 PATH。"
for s in contract.sh it-account.sh device.sh buddy.sh training.sh \
         build-approval-prompt.py record-pending-approval.py update-workflow.py \
         emit-approval-verbatim.py; do
  [ -f "$SCRIPT_DIR/$s" ] || fail "依赖脚本缺失：$SCRIPT_DIR/$s"
done
mkdir -p "$STATE"

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
    NAME="${2:-新员工}"; PINYIN="${3:-employee}"; ROLE="${4:-工程师}"; SALARY="${5:-面议}"
    # stub 目录改为按候选人隔离：STUB_STATE_DIR = $STATE/<pinyin>/
    # 5 个 stub 脚本不改，只读取 $STUB_STATE_DIR 环境变量，自然落到候选人子目录下。
    # 此处 export 后 lobster 会透传给每个 run 子 shell（含 4 路并行的 stub 子 shell）。
    export STUB_STATE_DIR="$STATE/$PINYIN"
    mkdir -p "$STUB_STATE_DIR"
    ARGS_JSON=$(NAME="$NAME" PINYIN="$PINYIN" ROLE="$ROLE" SALARY="$SALARY" python3 -c \
      'import json,os; print(json.dumps({"name":os.environ["NAME"],"pinyin":os.environ["PINYIN"],"role":os.environ["ROLE"],"salary":os.environ["SALARY"]},ensure_ascii=False))')
    # start 真跑前清掉该候选人旧 stub + workflow.json，确保本次扭转记录从 init 开始
    if [ "$ACTION" = "start" ]; then
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
