#!/usr/bin/env bash
# 360 反馈看板生成包装脚本 —— generating-360-dashboard Skill 的入口。
# 用法:
#   build_dashboard.sh <person_dir|aggregated_json> [--publish] [--force]
#   build_dashboard.sh <person_dir|aggregated_json> [out_html] [--publish] [--force]
#
# --publish: 生成后发布到 Canvas（id=feedback-360-<slug>）
# --force:   覆盖已有 Canvas 文档（仅与 --publish 联用）
#
# 人员目录约定：feedback-360/source_feedback/<slug>/
#   同目录读 aggregated-data.json + aggregated-report.md
#   缺省写出同目录 report.html，发布 id 取目录名 slug
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PUBLISH=0
FORCE=0
TARGET=""
OUT=""

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --publish) PUBLISH=1 ;;
    --force)   FORCE=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "[dashboard] 未知参数: $arg" >&2
      exit 1
      ;;
    *)
      if [ -z "$TARGET" ]; then
        TARGET="$arg"
      elif [ -z "$OUT" ]; then
        OUT="$arg"
      else
        echo "[dashboard] 多余的路径参数: $arg" >&2
        exit 1
      fi
      ;;
  esac
done

if [ -z "$TARGET" ]; then
  echo "[dashboard] 缺少人员目录或 aggregated-data.json 路径" >&2
  usage >&2
  exit 1
fi

# 解析人员目录与 slug（用于 canvas-id）
if [ -d "$TARGET" ]; then
  PERSON_DIR="$(cd "$TARGET" && pwd)"
elif [ -f "$TARGET" ]; then
  PERSON_DIR="$(cd "$(dirname "$TARGET")" && pwd)"
else
  echo "[dashboard] 路径不存在: $TARGET" >&2
  exit 2
fi
SLUG="$(basename "$PERSON_DIR")"
CANVAS_ID="feedback-360-${SLUG}"

# 校验 slug 为 ASCII（Canvas id 硬约束）
if ! [[ "$SLUG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "[dashboard] 人员目录名 '$SLUG' 含非 ASCII，无法派生 canvas-id。" >&2
  echo "            请使用拼音 slug（如 zhanglei），目录：source_feedback/<slug>/" >&2
  exit 3
fi

BUILD_ARGS=("$TARGET")
if [ -n "$OUT" ]; then
  BUILD_ARGS+=("$OUT")
fi

python3 "$SCRIPT_DIR/build_dashboard.py" "${BUILD_ARGS[@]}"

HTML_OUT="${OUT:-$PERSON_DIR/report.html}"
if [ ! -f "$HTML_OUT" ]; then
  echo "[dashboard] 未找到生成的 HTML: $HTML_OUT" >&2
  exit 2
fi

if [ "$PUBLISH" -eq 1 ]; then
  FORCE_FLAG=()
  if [ "$FORCE" -eq 1 ]; then
    FORCE_FLAG=(--force)
  fi
  echo "[dashboard] 发布到 Canvas: $CANVAS_ID"
  python3 "$SCRIPT_DIR/publish_to_canvas.py" "$HTML_OUT" "$CANVAS_ID" "${FORCE_FLAG[@]}"
fi
