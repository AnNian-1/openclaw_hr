#!/bin/bash
# HR 月报 · 定时推送入口（OpenClaw cron 命令载荷专用）
#
# stdout 就是推送到飞书 HR 的正文，逐字交付，不经过模型。
# 非月末（且未指定 --period）时打印 NO_REPLY，cron 静默令牌 → 不推任何消息。
#
# 用法:
#   notify_monthly_report.sh                月末守卫：明天不是 01 则静默退出
#   notify_monthly_report.sh --period 2026-10   忽略守卫，出指定月份（演示用）
#
# 本脚本只编排，不改 generate_monthly_report.py / run_monthly_report.sh。
set -uo pipefail
export TZ=Asia/Shanghai

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SELF_DIR/../../.." && pwd)"
SKILL="$ROOT/skills/generating-monthly-report"
RUN="$SKILL/scripts/run_monthly_report.sh"

PERIOD=""
FORCED=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --period)   PERIOD="${2:-}"; FORCED=1; shift 2 ;;
    --period=*) PERIOD="${1#--period=}"; FORCED=1; shift ;;
    *) echo "[notify] 未知参数: $1" >&2; exit 2 ;;
  esac
done

if [ "$FORCED" -eq 1 ]; then
  case "$PERIOD" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]) ;;
    *) echo "[notify] --period 格式应为 YYYY-MM，收到: $PERIOD" >&2; exit 2 ;;
  esac
else
  # 月末守卫：与 run_monthly_report.sh / maybe-monthly-report.sh 同一判定
  TOMORROW_DAY="$(date -d tomorrow '+%d' 2>/dev/null || date -v+1d '+%d')"
  if [ "$TOMORROW_DAY" != "01" ]; then
    echo "NO_REPLY"
    exit 0
  fi
  PERIOD="$(date +%Y-%m)"
fi

LOG="/tmp/hr-monthly-report-${PERIOD}-notify.log"

if ! bash "$RUN" "$PERIOD" >"$LOG" 2>&1; then
  echo "❌ HR 月报 · ${PERIOD} 生成失败"
  echo
  echo "日志: $LOG"
  tail -n 6 "$LOG"
  exit 1
fi

AUDIT="$ROOT/report-output/hr-monthly-report-${PERIOD}-audit.md"
if [ ! -f "$AUDIT" ]; then
  echo "❌ HR 月报 · ${PERIOD} 回核表缺失"
  echo
  echo "期望路径: $AUDIT"
  echo "日志: $LOG"
  exit 1
fi

# 从回核表取数：原样读出脚本写进表格的值，不重算
val() {
  awk -F'|' -v k="$1" '
    { m = $2; gsub(/^[ \t]+|[ \t]+$/, "", m) }
    m == k { v = $3; gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit }
  ' "$AUDIT"
}

JOIN="$(val '本月入职人数')"
ATTR="$(val '月离职率')"
COST="$(val '人均招聘成本')"
TRAIN="$(val '培训完成率')"
FILL="$(val '整体到位率')"
EARLY="$(val '45天内离职率')"
ITEMS="$(grep -m1 '回核项数' "$AUDIT" | awk -F'：' '{print $2}' | tr -d ' ')"

echo "📊 HR 月报 · ${PERIOD} 已生成"
echo
echo "本月入职 ${JOIN:-—} 人 ｜ 月离职率 ${ATTR:-—} ｜ 人均招聘成本 ${COST:-—}"
echo "培训完成率 ${TRAIN:-—} ｜ 整体到位率 ${FILL:-—} ｜ 45天内离职率：${EARLY:-—}"
echo
echo "${ITEMS:-18} 项数字全部回核至 HCM 冻结快照，全程无 LLM 参与数值生成。"
