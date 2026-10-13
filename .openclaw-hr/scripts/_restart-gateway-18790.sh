#!/usr/bin/env bash
set -euo pipefail
PROFILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROFILE/gateway.pid"
if [ -f "$PID_FILE" ]; then
  OLD="$(cat "$PID_FILE" || true)"
  if [ -n "$OLD" ] && ps -p "$OLD" >/dev/null 2>&1; then
    kill "$OLD" || true
    sleep 1
    ps -p "$OLD" >/dev/null 2>&1 && kill -9 "$OLD" || true
  fi
  rm -f "$PID_FILE"
fi
# leftover listeners on 18790
if command -v ss >/dev/null 2>&1; then
  LEFTOVER="$(ss -lptn 2>/dev/null | awk '/:18790/{print}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
else
  # 云机无 ss：按进程名兜底。本段只用于清理 18790 残留监听；注意它会连带命中调用方的 openclaw CLI。
  LEFTOVER="$(pgrep -x openclaw 2>/dev/null | sort -u || true)"
fi
# shellcheck disable=SC2086
for p in ${LEFTOVER}; do
  kill "$p" 2>/dev/null || true
done
sleep 1
exec bash "$PROFILE/scripts/start-gateway-18790.sh"
