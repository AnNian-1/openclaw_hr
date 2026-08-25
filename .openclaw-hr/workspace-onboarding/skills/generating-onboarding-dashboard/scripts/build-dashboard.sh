#!/usr/bin/env bash
# 入职进度看板生成包装脚本 —— generating-onboarding-dashboard Skill 的入口。
# 用法:
#   build-dashboard.sh [输出 HTML 路径]
#   build-dashboard.sh [--publish] [--force]
#   build-dashboard.sh [输出 HTML 路径] --publish [--force]
# 不传输出路径时,看板写到 <workspace>/onboarding-dashboard.html
# --publish: 生成后发布到 Canvas（id=onboarding-dashboard）
# --force:   覆盖已有 Canvas 文档（仅与 --publish 联用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ONBOARDING_WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
export ONBOARDING_WORKSPACE="$WORKSPACE"

PUBLISH=0
FORCE=0
OUT=""

for arg in "$@"; do
  case "$arg" in
    --publish) PUBLISH=1 ;;
    --force)   FORCE=1 ;;
    -h|--help)
      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "[dashboard] 未知参数: $arg" >&2
      exit 1
      ;;
    *)
      if [ -n "$OUT" ]; then
        echo "[dashboard] 多余的路径参数: $arg" >&2
        exit 1
      fi
      OUT="$arg"
      ;;
  esac
done

OUT="${OUT:-$WORKSPACE/onboarding-dashboard.html}"

python3 "$SCRIPT_DIR/build-dashboard.py" "$OUT"

if [ "$PUBLISH" -eq 1 ]; then
  FORCE_FLAG=()
  if [ "$FORCE" -eq 1 ]; then
    FORCE_FLAG=(--force)
  fi
  echo "[dashboard] 发布到 Canvas: onboarding-dashboard"
  python3 "$SCRIPT_DIR/publish_to_canvas.py" "$OUT" onboarding-dashboard "${FORCE_FLAG[@]}"
fi
