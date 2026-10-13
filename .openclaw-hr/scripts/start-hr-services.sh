#!/usr/bin/env bash
# 一键后台启动 Gateway :18790 + HCM :8000 / :5174。不启 Canvas。
set -euo pipefail
PROFILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${PROFILE}/scripts/start-gateway-18790.sh"
bash "${PROFILE}/hcm/start.sh"
