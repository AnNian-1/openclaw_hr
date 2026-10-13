#!/usr/bin/env bash
# 本机 WSL：在 18790 启动小慧 Gateway（OpenClaw 2026.5.12）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/prepend-node22.sh"
export PATH="${PROFILE}/install/node_modules/.bin:${PATH}"
export npm_config_fund=false

mkdir -p "${PROFILE}/logs" "${PROFILE}/memory" "${PROFILE}/sessions" "${PROFILE}/agents" "${PROFILE}/npm"

if [ ! -f "${PROFILE}/env.sh" ]; then
  echo "[fail] 缺少 ${PROFILE}/env.sh" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${PROFILE}/env.sh"
set +a

export OPENCLAW_STATE_DIR="${PROFILE}"
export OPENCLAW_CONFIG_PATH="${PROFILE}/config/openclaw.yaml"
export OPENCLAW_HR_BIN="${PROFILE}/install/node_modules/.bin/openclaw"

if [ ! -x "${OPENCLAW_HR_BIN}" ]; then
  echo "[fail] 未找到 OpenClaw 2026.5.12：${OPENCLAW_HR_BIN}" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[fail] 未找到 node（需要 ≥ 22.16）。已试 ~/.local/node/node-22 、 /opt/openclaw-hr/.local/node/node-22 、 /opt/node/node-22" >&2
  exit 1
fi

PORT="${HR_PORT:-18790}"
PID_FILE="${PROFILE}/gateway.pid"
LOG_FILE="${PROFILE}/logs/gateway.log"

listener_pid() {
  ss -lptn "sport = :${PORT}" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2
}

health_ok() {
  curl -sS --noproxy '*' --max-time 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null | grep -q '"ok":true'
}

if health_ok; then
  PID="$(listener_pid)"
  if [ -n "${PID}" ]; then
    echo "${PID}" >"${PID_FILE}"
  fi
  echo "[skip] gateway 已在跑 · pid=${PID:-?} · port=${PORT}"
  exit 0
fi

if [ -f "${PID_FILE}" ]; then
  OLD_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${OLD_PID}" ] && ps -p "${OLD_PID}" >/dev/null 2>&1; then
    kill "${OLD_PID}" 2>/dev/null || true
    sleep 1
  fi
  rm -f "${PID_FILE}"
fi

echo "[run] $( "${OPENCLAW_HR_BIN}" --version ) · node=$(node -v) · port=${PORT} · log=${LOG_FILE}"
setsid -f "${OPENCLAW_HR_BIN}" gateway run >>"${LOG_FILE}" 2>&1

ok=false
for _ in $(seq 1 40); do
  if health_ok; then
    ok=true
    break
  fi
  sleep 1
done

PID="$(listener_pid)"
if [ -n "${PID}" ]; then
  echo "${PID}" >"${PID_FILE}"
fi

if [ "${ok}" = "true" ]; then
  echo "[ok] gateway ready · pid=${PID:-?} · http://127.0.0.1:${PORT}/health"
  exit 0
fi

echo "[fail] gateway 未在 40s 内就绪 · 最近日志:" >&2
tail -n 80 "${LOG_FILE}" >&2 || true
exit 1
