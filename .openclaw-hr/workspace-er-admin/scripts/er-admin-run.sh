#!/usr/bin/env bash
# er-admin 唯一允许的 exec 入口：政策检索 / 花名册薪资 / 月报。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCESS="$ROOT/scripts/hr-data-access.sh"

extract_sender() {
  SENDER=""
  FORWARD=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --sender)
        SENDER="${2:-}"
        shift 2
        ;;
      --sender=*)
        SENDER="${1#--sender=}"
        shift
        ;;
      *)
        FORWARD+=("$1")
        shift
        ;;
    esac
  done
}

require_hr_data() {
  local out
  if ! out="$(bash "$ACCESS" check "$SENDER")"; then
    printf '%s\n' "$out"
    echo "拒绝：当前身份不能查他人工资或出月报。飞书仅 HR 可以；WebChat / CLI 不传 --sender。" >&2
    exit 3
  fi
}

cmd="${1:-}"
shift || true
case "$cmd" in
  ima-search)
    exec node "$ROOT/skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs" "$@"
    ;;
  payroll-query)
    extract_sender "$@"
    require_hr_data
    exec python3 "$ROOT/skills/querying-employee-payroll/scripts/query_payroll.py" "${FORWARD[@]+"${FORWARD[@]}"}"
    ;;
  monthly-report)
    extract_sender "$@"
    require_hr_data
    exec bash "$ROOT/skills/generating-monthly-report/scripts/run_monthly_report.sh" "${FORWARD[@]+"${FORWARD[@]}"}"
    ;;
  *)
    echo "usage: scripts/er-admin-run.sh ima-search <问题> | payroll-query [--sender ou_…] --name|--all | monthly-report [--sender ou_…] [args]" >&2
    echo "禁止用 exec 把政策写入 md /tmp 或其它路径。政策只检索、口头发。" >&2
    exit 2
    ;;
esac
