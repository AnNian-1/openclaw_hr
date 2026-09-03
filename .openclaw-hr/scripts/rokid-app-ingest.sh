#!/usr/bin/env bash
# 乐奇眼镜上传服务（:18791）。与 Gateway 分进程。不要用本脚本去起 Gateway。
set -euo pipefail
PROFILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER="$PROFILE/rokid-app-ingest/server.py"
PIDFILE="${ROKID_APP_INGEST_PIDFILE:-$PROFILE/logs/rokid-app-ingest.pid}"
LOGFILE="${ROKID_APP_INGEST_LOG:-$PROFILE/logs/rokid-app-ingest.log}"
HOST="${ROKID_APP_INGEST_HOST:-0.0.0.0}"
PORT="${ROKID_APP_INGEST_PORT:-18791}"

if [[ -f "$PROFILE/env.sh" ]]; then
  set +u
  # shellcheck disable=SC1091
  source "$PROFILE/env.sh"
  set -u
fi
# shellcheck disable=SC1091
source "$PROFILE/scripts/prepend-conda-python.sh"
# shellcheck disable=SC1091
source "$PROFILE/scripts/prepend-node22.sh"

if [[ -x "$PROFILE/install/node_modules/.bin/openclaw" ]]; then
  export PATH="$PROFILE/install/node_modules/.bin:$PATH"
fi

usage() {
  echo "usage: $0 {run|start|stop|status}" >&2
  exit 2
}

need_secret() {
  if [[ -z "${ROKID_APP_INGEST_SECRET:-}" ]]; then
    echo "rokid-app-ingest: ROKID_APP_INGEST_SECRET 未设置（写在 env.sh）" >&2
    exit 1
  fi
}

is_running() {
  [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

cmd="${1:-run}"
case "$cmd" in
  run)
    need_secret
    export ROKID_APP_INGEST_HOST="$HOST"
    export ROKID_APP_INGEST_PORT="$PORT"
    exec python3 "$SERVER"
    ;;
  start)
    need_secret
    mkdir -p "$(dirname "$PIDFILE")" "$(dirname "$LOGFILE")"
    if is_running; then
      echo "rokid-app-ingest already running pid=$(cat "$PIDFILE")"
      exit 0
    fi
    export ROKID_APP_INGEST_HOST="$HOST"
    export ROKID_APP_INGEST_PORT="$PORT"
    nohup python3 "$SERVER" >>"$LOGFILE" 2>&1 &
    echo $! >"$PIDFILE"
    sleep 0.3
    if ! is_running; then
      echo "rokid-app-ingest failed to start; see $LOGFILE" >&2
      exit 1
    fi
    echo "rokid-app-ingest started pid=$(cat "$PIDFILE") http://${HOST}:${PORT}"
    ;;
  stop)
    if ! is_running; then
      echo "rokid-app-ingest not running"
      rm -f "$PIDFILE"
      exit 0
    fi
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo "rokid-app-ingest stopped"
    ;;
  status)
    if is_running; then
      echo "rokid-app-ingest running pid=$(cat "$PIDFILE")"
    else
      echo "rokid-app-ingest not running"
      exit 1
    fi
    ;;
  *)
    usage
    ;;
esac
