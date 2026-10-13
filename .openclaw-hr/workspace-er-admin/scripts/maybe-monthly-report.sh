#!/bin/bash
# 宿主机日检：明天是否为 1 号（Asia/Shanghai）。是则出上一个月的月报。
set -e
export TZ=Asia/Shanghai
TOMORROW_DAY=$(date -d tomorrow '+%d' 2>/dev/null || date -v+1d '+%d')
if [ "$TOMORROW_DAY" != "01" ]; then
  exit 0
fi
PERIOD="$(date +%Y-%m)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/skills/generating-monthly-report/scripts/run_monthly_report.sh" "$PERIOD"
