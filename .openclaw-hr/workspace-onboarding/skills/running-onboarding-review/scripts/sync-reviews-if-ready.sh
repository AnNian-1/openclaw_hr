#!/usr/bin/env bash
# sync-reviews-if-ready.sh — 仅当 HCM 五节点均为 completed 时 ensure + 挂 Cron
# 用法: sync-reviews-if-ready.sh <姓名> <pinyin>
# 退出: 0 已挂或已跳过（未全绿 / 已挂过）；5 HCM 不可用；4 花名册无此人；1 挂 Cron 失败
set -euo pipefail

NAME="${1:?usage: sync-reviews-if-ready.sh <姓名> <pinyin>}"
PINYIN="${2:?usage: sync-reviews-if-ready.sh <姓名> <pinyin>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ONBOARDING_WORKSPACE:-${WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}}"
WF_SCRIPTS="$WORKSPACE/skills/running-onboarding-workflow/scripts"
export ONBOARDING_WORKSPACE="$WORKSPACE"
export WORKSPACE

_PREPEND_NODE="$(cd "$SCRIPT_DIR/../../../.." && pwd)/scripts/prepend-node22.sh"
# shellcheck disable=SC1090
[ -f "$_PREPEND_NODE" ] && . "$_PREPEND_NODE"

SUMMARY="$(python3 - "$WF_SCRIPTS" "$PINYIN" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import hcm_api
print(json.dumps(hcm_api.summarize_prep(sys.argv[2]), ensure_ascii=False))
PY
)"

set +e
python3 - "$SUMMARY" <<'PY'
import json, sys
s = json.loads(sys.argv[1])
if not s.get("hcm_up"):
    sys.exit(5)
if not s.get("found"):
    sys.exit(4)
if not s.get("all_completed"):
    pending = ",".join(s.get("pending") or [])
    print(f"[sync-reviews] 五节点未全绿，不挂跟进（pending={pending}）", file=sys.stderr)
    sys.exit(3)
sys.exit(0)
PY
rc=$?
set -e
if [ "$rc" = "5" ]; then
  echo "[sync-reviews] HCM 不可用" >&2
  exit 5
fi
if [ "$rc" = "4" ]; then
  echo "[sync-reviews] 花名册无 ${PINYIN}" >&2
  exit 4
fi
if [ "$rc" = "3" ]; then
  exit 0
fi

ARMED="$(python3 "$SCRIPT_DIR/review_store.py" --workspace "$WORKSPACE" is-armed "$PINYIN")"
if echo "$ARMED" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('armed') else 1)"; then
  echo "[sync-reviews] ${PINYIN} 跟进 Cron 已挂过，跳过" >&2
  exit 0
fi

bash "$SCRIPT_DIR/review-store.sh" ensure "$NAME" "$PINYIN" >/dev/null
if bash "$SCRIPT_DIR/schedule-onboarding-reviews.sh" "$NAME" "$PINYIN"; then
  python3 "$SCRIPT_DIR/review_store.py" --workspace "$WORKSPACE" mark-armed "$PINYIN" >/dev/null
  echo "[sync-reviews] 五节点已完成，已 ensure 并注册 7/30/60/90 Cron" >&2
  exit 0
fi
echo "[sync-reviews] 注册 Cron 失败" >&2
exit 1
