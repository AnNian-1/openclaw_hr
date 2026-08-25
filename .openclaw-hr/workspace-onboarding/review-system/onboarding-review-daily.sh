#!/usr/bin/env bash
# Onboarding Review Daily Scheduler - Zhang San
# Triggered by launchd daily at 9:00 AM
# Start date: 2026-05-25
set -euo pipefail

NAME="${1:-zhangsan}"
TODAY="${TODAY_OVERRIDE:-$(date +%Y-%m-%d)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REVIEW_SH="${SCRIPT_DIR}/onboarding-review.sh"

case "$TODAY" in
  2026-06-01) DAY=7  ;;
  2026-06-24) DAY=30 ;;
  2026-07-24) DAY=60 ;;
  2026-08-23) DAY=90 ;;
  *)
    echo "[$(date)] Not a review day (today=$TODAY), skipping"
    exit 0
    ;;
esac

echo "[$(date)] === Triggering Day $DAY Review: $NAME ==="
bash "$REVIEW_SH" "$NAME" "$DAY"
echo "[$(date)] === Day $DAY Review complete ==="
