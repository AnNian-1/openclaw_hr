#!/usr/bin/env bash
# er-admin 唯一允许的 exec 入口：政策检索 / 月报脚本。禁止写任意 md。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cmd="${1:-}"
shift || true
case "$cmd" in
  ima-search)
    exec node "$ROOT/skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs" "$@"
    ;;
  monthly-report)
    exec bash "$ROOT/skills/generating-monthly-report/scripts/run_monthly_report.sh" "$@"
    ;;
  *)
    echo "usage: scripts/er-admin-run.sh ima-search <问题> | monthly-report [args]" >&2
    echo "禁止用 exec 把政策写入 md /tmp 或其它路径。政策只检索、口头发。" >&2
    exit 2
    ;;
esac
