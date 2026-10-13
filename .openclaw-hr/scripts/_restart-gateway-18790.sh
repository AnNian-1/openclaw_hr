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
for p in $(ss -lptn 2>/dev/null | awk '/:18790/{print}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u); do
  kill "$p" 2>/dev/null || true
done
sleep 1
exec bash "$PROFILE/scripts/start-gateway-18790.sh"
