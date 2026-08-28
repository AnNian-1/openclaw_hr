#!/usr/bin/env bash
# schedule-onboarding-reviews.sh —— 入职审批完成后，注册 7/30/60/90 天一次性 Cron
#
# 用法：
#   schedule-onboarding-reviews.sh <姓名> <pinyin> [入职日YYYY-MM-DD]
#
# 入职日缺省：读 stub-state/<pinyin>/workflow.json 的 started_at 日期；再不行用今天。
# 每个节点在「入职日 + N 天」的 09:00（Asia/Shanghai）触发一次 agentTurn，
# 让 onboarding Agent 执行 running-onboarding-review 脚本。
#
# 环境：
#   需 PATH 上有 openclaw（先 source 本机 profile 的 env.sh），或设 OPENCLAW_HR_BIN
#   SCHEDULE_DRY_RUN=1 只打印将注册的任务，不真正 cron add
#
# 由 hr-onboarding.lobster 的 complete 节点调用。
set -euo pipefail

NAME="${1:?usage: schedule-onboarding-reviews.sh <姓名> <pinyin> [入职日]}"
PINYIN="${2:?usage: schedule-onboarding-reviews.sh <姓名> <pinyin> [入职日]}"
HIRE_DATE="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 本脚本在 running-onboarding-review/scripts/；workspace 根向上三级
WORKSPACE="${ONBOARDING_WORKSPACE:-${WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}}"
STATE_DIR="${STUB_STATE_DIR:-$WORKSPACE/stub-state/$PINYIN}"
REVIEW_SH="$WORKSPACE/skills/running-onboarding-review/scripts/onboarding-review.sh"

if [ ! -x "$REVIEW_SH" ] && [ -f "$REVIEW_SH" ]; then
  chmod +x "$REVIEW_SH" || true
fi
if [ ! -f "$REVIEW_SH" ]; then
  echo "[schedule-reviews] 找不到 review 脚本：$REVIEW_SH" >&2
  exit 2
fi

# openclaw 用 env node；lobster 里常见 PATH 先命中 Node 20，必须把 22 放最前。
if [ -d "${HOME}/.local/node/node-22/bin" ]; then
  export PATH="${HOME}/.local/node/node-22/bin:${PATH}"
fi
# openclaw CLI：只信 OPENCLAW_HR_BIN 或 PATH，不 source 家目录 env.sh
OPENCLAW_BIN="${OPENCLAW_HR_BIN:-$(command -v openclaw || true)}"
if [ -z "$OPENCLAW_BIN" ] || [ ! -x "$OPENCLAW_BIN" ]; then
  echo "[schedule-reviews] 找不到 openclaw（请 source 本机 profile 的 env.sh，或设 OPENCLAW_HR_BIN）" >&2
  exit 2
fi

# 解析入职日
if [ -z "$HIRE_DATE" ] && [ -f "$STATE_DIR/workflow.json" ]; then
  HIRE_DATE="$(python3 - "$STATE_DIR/workflow.json" <<'PY'
import json, sys
from datetime import datetime
wf = json.load(open(sys.argv[1], encoding="utf-8"))
raw = wf.get("started_at") or wf.get("completed_at") or ""
if not raw:
    print("")
    raise SystemExit
# 支持 2026-07-17T22:20:51+08:00 / ...Z
s = raw.replace("Z", "+00:00")
try:
    dt = datetime.fromisoformat(s)
    print(dt.date().isoformat())
except ValueError:
    print(raw[:10] if len(raw) >= 10 else "")
PY
)"
fi
if [ -z "$HIRE_DATE" ]; then
  HIRE_DATE="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
fi

echo "[schedule-reviews] 候选人=${NAME}（${PINYIN}）入职日=${HIRE_DATE}"
echo "[schedule-reviews] review 脚本=${REVIEW_SH}"

schedule_one () {
  local day="$1"
  local at_iso
  at_iso="$(python3 - "$HIRE_DATE" "$day" <<'PY'
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
hire = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
day = int(sys.argv[2])
tz = ZoneInfo("Asia/Shanghai")
when = datetime(hire.year, hire.month, hire.day, 9, 0, 0, tzinfo=tz) + timedelta(days=day)
print(when.isoformat())
PY
)"
  local job_name="onboard-review-${PINYIN}-day${day}"
  local msg="请执行命令并把完整输出返回：bash ${REVIEW_SH} ${NAME} ${day} ${PINYIN}"

  echo "[schedule-reviews] day${day} → ${at_iso}  name=${job_name}"

  if [ "${SCHEDULE_DRY_RUN:-0}" = "1" ]; then
    echo "  DRY_RUN: $OPENCLAW_BIN cron add --name $job_name --at $at_iso ..."
    return 0
  fi

  # --no-deliver：HR profile 无聊天 channel，否则投递失败会把整次任务判失败
  # --delete-after-run：一次性 --at 跑完即删
  # --tools exec：允许 Agent 执行 bash
  if ! "$OPENCLAW_BIN" cron add \
      --name "$job_name" \
      --description "${NAME}入职第${day}天试用期跟进 review" \
      --agent onboarding \
      --at "$at_iso" \
      --tz Asia/Shanghai \
      --session isolated \
      --no-deliver \
      --delete-after-run \
      --timeout-seconds 120 \
      --tools exec \
      --message "$msg"
  then
    echo "[schedule-reviews] 警告：注册 day${day} 失败（可稍后手动 cron add）" >&2
    return 1
  fi
  return 0
}

fail=0
for d in 7 30 60 90; do
  schedule_one "$d" || fail=1
done

if [ "$fail" -ne 0 ]; then
  echo "[schedule-reviews] 部分任务注册失败，请检查 gateway / openclaw-hr cron list" >&2
  exit 1
fi
echo "[schedule-reviews] 已注册 7/30/60/90 四次一次性 Cron"
exit 0
