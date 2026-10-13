#!/usr/bin/env bash
set -euo pipefail
NODE22=/home/annian/.nvm/versions/node/v22.23.1/bin
export PATH="${NODE22}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export npm_config_fund=false
unset NPM_CONFIG_PREFIX 2>/dev/null || true
PROFILE=/home/hr/.openclaw-hr

echo "[node] $(command -v node) $(node -v)"
echo "[npm] $(command -v npm) $(npm -v)"

cd "$PROFILE/install"
rm -rf node_modules package-lock.json
echo "[npm] install openclaw@2026.5.12 in install/"
npm install --no-audit --no-fund

mkdir -p "$PROFILE/npm"
cd "$PROFILE/npm"
cat > package.json <<'JSON'
{
  "name": "openclaw-hr-plugins",
  "private": true,
  "dependencies": {
    "@openclaw/feishu": "2026.5.12",
    "@openclaw/lobster": "2026.5.12"
  }
}
JSON
rm -rf node_modules package-lock.json
echo "[npm] install feishu+lobster 2026.5.12 in npm/"
npm install --no-audit --no-fund

BIN="$PROFILE/install/node_modules/.bin/openclaw"
chmod +x "$BIN"
echo "[ok] $($BIN --version)"
