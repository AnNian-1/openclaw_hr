#!/usr/bin/env bash
# D-011：recruitment-run 闸，不经 Gateway。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/scripts/recruitment-run.sh"
ONB="$ROOT/../workspace-onboarding/stub-state/lixin/workflow.json"
fail=0
cd "$ROOT"

expect_deny() {
  local name="$1"
  shift
  if "$RUN" "$@" >/tmp/rr-out.txt 2>/tmp/rr-err.txt; then
    echo "FAIL $name: 应当拒绝却退出 0"
    fail=1
  else
    echo "ok   deny $name"
  fi
}

expect_allow() {
  local name="$1"
  shift
  if "$RUN" "$@" >/tmp/rr-out.txt 2>/tmp/rr-err.txt; then
    echo "ok   allow $name"
  else
    echo "FAIL $name: 应当放行"
    cat /tmp/rr-err.txt
    fail=1
  fi
}

expect_deny "python -c" python3 -c 'print(1)'
expect_deny "绝对路径 onboarding" cat "$ONB"
expect_deny "相对路径 onboarding" cat "../workspace-onboarding/stub-state/lixin/workflow.json"
expect_allow "echo" echo ok
expect_allow "true" true

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "test-recruitment-run: all passed"
