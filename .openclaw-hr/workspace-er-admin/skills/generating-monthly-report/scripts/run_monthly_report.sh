#!/bin/bash
# HR 月报入口（宿主机日检 / 运维 CLI）
# 不经 Gateway、不经 OpenClaw Cron。行政飞书会话禁止跑本脚本。
#
# 用法:
#   run_monthly_report.sh                  仅月末当天生成并发布(其余日期空跑退出)
#   run_monthly_report.sh --force          忽略月末守卫, 立即生成并发布(调试用)
#   run_monthly_report.sh 2026-05          指定月份, 同时忽略月末守卫并发布
#   run_monthly_report.sh --no-publish ... 只生成到 report-output/, 不发 Canvas
#   未指定月份时用 Asia/Shanghai 当前 YYYY-MM；先 POST HCM freeze，再把该月传给生成器。
#
# 月末守卫说明:
#   宿主机 crontab 每天 23:59 调 /opt/hr-ops/maybe-monthly-report.sh，
#   明天不是 01 则根本不进本脚本。本守卫仍保留，便于 CLI 无 --force 时防误跑。
#   （旧方案 OpenClaw cron "59 23 28-31 * *" 已废弃：空跑仍会写 isolated 会话。）
#
# Canvas:
#   默认 --publish --force，落盘 id=hr-monthly-report（覆盖上一期）。
#   约束见 references/canvas-publishing.md。
#
# Python:
#   OpenClaw exec 的 PATH 常解析到 /usr/bin/python3（无 pandas）。
#   本脚本优先使用 conda openclaw-hr；可用 MONTHLY_REPORT_PYTHON 覆盖。
#   禁止对系统 python 执行 pip install。
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_python() {
  if [ -n "${MONTHLY_REPORT_PYTHON:-}" ]; then
    if [ ! -x "$MONTHLY_REPORT_PYTHON" ]; then
      echo "[monthly-report] ERROR: MONTHLY_REPORT_PYTHON 不可执行: $MONTHLY_REPORT_PYTHON" >&2
      exit 127
    fi
    echo "$MONTHLY_REPORT_PYTHON"
    return
  fi
  local candidates=(
    "${HOME}/miniconda3/envs/openclaw-hr/bin/python3"
    /usr/local/miniconda3/envs/openclaw-hr/bin/python3
    "${HOME}/miniconda3/envs/py312/bin/python3"
    /usr/local/miniconda3/envs/py312/bin/python3
    "${HOME}/anaconda3/envs/py312/bin/python3"
  )
  local c
  for c in "${candidates[@]}"; do
    if [ -x "$c" ] && "$c" -c 'import pandas, matplotlib' >/dev/null 2>&1; then
      echo "$c"
      return
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import pandas, matplotlib' >/dev/null 2>&1; then
      command -v python3
      return
    fi
  fi
  echo "[monthly-report] ERROR: 未找到带 pandas/matplotlib 的 Python。" >&2
  echo "  请用: ~/miniconda3/envs/openclaw-hr/bin/python3" >&2
  echo "  或: export MONTHLY_REPORT_PYTHON=/path/to/python3" >&2
  echo "  禁止对 /usr/bin/python3 执行 pip install。" >&2
  exit 127
}

FORCE=0
PUBLISH=1
TARGET=""
HCM_URL="${HCM_API_BASE:-http://127.0.0.1:8000}"
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --publish) PUBLISH=1 ;;
    --no-publish) PUBLISH=0 ;;
    [0-9]*-[0-9]*) TARGET="$arg"; FORCE=1 ;;
    -h|--help)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "[monthly-report] 未知参数: $arg" >&2
      exit 1
      ;;
  esac
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] HR 月报 Cron 任务启动"

# ---- 月末守卫 ----
if [ "$FORCE" -eq 0 ]; then
  TOMORROW_DAY=$(date -v+1d '+%d' 2>/dev/null || date -d tomorrow '+%d')
  if [ "$TOMORROW_DAY" != "01" ]; then
    echo "今天不是本月最后一天(明天是 ${TOMORROW_DAY} 号), 月末守卫拦截, 空跑退出。"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] HR 月报 Cron 任务结束(未生成)"
    exit 0
  fi
  echo "确认为本月最后一天, 开始生成本月月报。"
fi

PYTHON_BIN="$(resolve_python)"
echo "[monthly-report] Python: $PYTHON_BIN"

if [ -z "$TARGET" ]; then
  TARGET="$(TZ=Asia/Shanghai date +%Y-%m)"
  echo "[monthly-report] 未指定月份，使用 Asia/Shanghai 当前月 $TARGET"
fi
echo "[monthly-report] 目标月份: $TARGET"

if ! curl -sf --max-time 5 "${HCM_URL}/api/health" >/dev/null; then
  echo "[monthly-report] ERROR: HCM 不可达 (${HCM_URL}/api/health)。请先启动 HCM。禁止回退 CSV。" >&2
  exit 1
fi
echo "[monthly-report] HCM health ok: ${HCM_URL}"
FREEZE_URL="${HCM_URL}/api/reports/monthly/${TARGET}/freeze"
echo "[monthly-report] POST freeze $TARGET"
HTTP_CODE="$(curl -sS -o /tmp/hcm-monthly-freeze.json -w '%{http_code}' --max-time 30 -X POST "$FREEZE_URL" || true)"
if [ "$HTTP_CODE" != "200" ]; then
  echo "[monthly-report] ERROR: 冻结失败 HTTP ${HTTP_CODE}" >&2
  cat /tmp/hcm-monthly-freeze.json >&2 || true
  echo >&2
  exit 1
fi
echo "[monthly-report] freeze ok"

GEN_ARGS=("$TARGET")
GEN_ARGS+=(--hcm-url "$HCM_URL")
if [ "$PUBLISH" -eq 1 ]; then
  # 固定 canvas-id 重出必须覆盖
  GEN_ARGS+=(--publish --force)
  echo "[monthly-report] 生成后将发布到 Canvas: hr-monthly-report"
else
  echo "[monthly-report] --no-publish: 仅写 report-output/"
fi

"$PYTHON_BIN" "$SCRIPT_DIR/generate_monthly_report.py" "${GEN_ARGS[@]}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] HR 月报 Cron 任务结束"
