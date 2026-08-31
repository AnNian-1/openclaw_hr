#!/usr/bin/env bash
# 启动 Canvas 反代 18999 → Gateway 18790（浏览器免 Bearer）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="$(cd "$ROOT/.." && pwd)"
CONF="$ROOT/conf/nginx.conf"
PIDFILE="$ROOT/nginx.pid"

if [[ -f "$PROFILE/env.sh" ]]; then
  set +u
  # shellcheck disable=SC1091
  source "$PROFILE/env.sh"
  set -u
fi

export OPENCLAW_GATEWAY_TOKEN
if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
  echo "start-canvas-proxy: OPENCLAW_GATEWAY_TOKEN 未设置" >&2
  exit 1
fi

mkdir -p "$ROOT/logs" \
  "$ROOT/temp_client_body" "$ROOT/temp_proxy" \
  "$ROOT/temp_fastcgi" "$ROOT/temp_uwsgi" "$ROOT/temp_scgi"

python3 - "$ROOT/conf/canvas-proxy.conf" "$OPENCLAW_GATEWAY_TOKEN" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
token = sys.argv[2]
text = path.read_text(encoding="utf-8")
new, n = re.subn(
    r'set \$gateway_token "[^"]*";',
    f'set $gateway_token "{token}";',
    text,
    count=1,
)
if n != 1:
    sys.exit("start-canvas-proxy: 未改到 set $gateway_token")
path.write_text(new, encoding="utf-8")
PY

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  nginx -c "$CONF" -s reload
  echo "canvas-proxy reloaded on 0.0.0.0:18999"
  exit 0
fi

if command -v nginx >/dev/null 2>&1; then
  nginx -t -c "$CONF"
  nginx -c "$CONF"
  echo "canvas-proxy (nginx) listening on 0.0.0.0:18999"
  exit 0
fi

PY_PIDFILE="$ROOT/canvas-proxy-python.pid"
if [[ -f "$PY_PIDFILE" ]] && kill -0 "$(cat "$PY_PIDFILE")" 2>/dev/null; then
  echo "canvas-proxy (python) already running"
  exit 0
fi

echo "nginx 未安装，改用 python canvas_proxy.py"
cd "$ROOT"
nohup python3 "$ROOT/canvas_proxy.py" >>"$ROOT/logs/canvas-proxy-python.log" 2>&1 &
echo $! >"$ROOT/canvas-proxy-python.pid"
sleep 0.3
echo "canvas-proxy (python) listening on 0.0.0.0:18999"
