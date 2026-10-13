#!/usr/bin/env bash
# HCM 一键启动。默认后台；--fg 前台（Ctrl+C 停）。
# 用法: bash start.sh [--fg]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${PROFILE}/scripts/prepend-conda-python.sh"
# shellcheck disable=SC1091
source "${PROFILE}/scripts/prepend-node22.sh"

API_HOST="${HCM_HOST:-0.0.0.0}"
API_PORT="${HCM_PORT:-8000}"
UI_PORT="${HCM_UI_PORT:-5174}"
LOG_DIR="${PROFILE}/logs"
LOG_FILE="${LOG_DIR}/hcm.log"
API_PID_FILE="${LOG_DIR}/hcm-backend.pid"
UI_PID_FILE="${LOG_DIR}/hcm-frontend.pid"
FG=false
if [ "${1:-}" = "--fg" ]; then
  FG=true
fi

mkdir -p "${LOG_DIR}"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "[fail] 未找到 uvicorn。需要 conda 环境 openclaw-hr。" >&2
  echo "  已试: \$HOME/miniconda3 、 /home/hr/miniconda3 、 /usr/local/miniconda3" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[fail] 未找到 npm / Node 22。已试 ~/.local/node/node-22 、 /home/hr/.local/node/node-22 、 /opt/node/node-22" >&2
  exit 1
fi

api_ok() {
  curl -sS --noproxy '*' --max-time 2 "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null | grep -q '"ok"'
}

ui_ok() {
  code="$(curl -sS --noproxy '*' --max-time 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${UI_PORT}/" 2>/dev/null || true)"
  [ "${code}" = "200" ] || [ "${code}" = "304" ]
}

start_api() {
  if api_ok; then
    echo "[skip] HCM API 已在跑 · :${API_PORT}"
    return 0
  fi
  echo "[run] HCM API · uvicorn · ${API_HOST}:${API_PORT}"
  (
    cd "${SCRIPT_DIR}/backend"
    if [ "${FG}" = "true" ]; then
      uvicorn main:app --host "${API_HOST}" --port "${API_PORT}" &
      echo $! >"${API_PID_FILE}"
    else
      nohup uvicorn main:app --host "${API_HOST}" --port "${API_PORT}" >>"${LOG_FILE}" 2>&1 &
      echo $! >"${API_PID_FILE}"
    fi
  )
}

start_ui() {
  if ui_ok; then
    echo "[skip] HCM UI 已在跑 · :${UI_PORT}"
    return 0
  fi
  echo "[run] HCM UI · vite · :${UI_PORT}"
  (
    cd "${SCRIPT_DIR}/frontend"
    if [ "${FG}" = "true" ]; then
      npm run dev &
      echo $! >"${UI_PID_FILE}"
    else
      nohup npm run dev >>"${LOG_FILE}" 2>&1 &
      echo $! >"${UI_PID_FILE}"
    fi
  )
}

echo "[run] 启动 HCM 人力资源管理系统"
start_api
start_ui

ok_api=false
ok_ui=false
for _ in $(seq 1 40); do
  if api_ok; then ok_api=true; fi
  if ui_ok; then ok_ui=true; fi
  if [ "${ok_api}" = "true" ] && [ "${ok_ui}" = "true" ]; then
    break
  fi
  sleep 1
done

if [ "${ok_api}" != "true" ]; then
  echo "[fail] HCM API 未在 40s 内就绪 · ${LOG_FILE}" >&2
  tail -n 40 "${LOG_FILE}" >&2 || true
  exit 1
fi
if [ "${ok_ui}" != "true" ]; then
  echo "[fail] HCM UI 未在 40s 内就绪 · ${LOG_FILE}" >&2
  tail -n 40 "${LOG_FILE}" >&2 || true
  exit 1
fi

echo "[ok] HCM API http://127.0.0.1:${API_PORT}/docs"
echo "[ok] HCM UI  http://127.0.0.1:${UI_PORT}"

if [ "${FG}" = "true" ]; then
  echo "按 Ctrl+C 停止所有服务"
  trap 'kill "$(cat "${API_PID_FILE}" 2>/dev/null)" "$(cat "${UI_PID_FILE}" 2>/dev/null)" 2>/dev/null; exit 0' INT TERM
  wait
fi
