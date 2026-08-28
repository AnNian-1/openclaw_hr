#!/usr/bin/env bash
# 培训域唯一推荐 exec 入口：ADDIE 物料包由脚本编排，不把 8 次长文写进一次 Agent 会话。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cmd="${1:-}"
shift || true
case "$cmd" in
  generate)
    exec python3 "$ROOT/skills/generating-training-materials/scripts/generate_pack.py" "$@"
    ;;
  self-check)
    theme="${1:-信息安全意识}"
    exec python3 "$ROOT/skills/generating-training-materials/scripts/self_check.py" \
      --outdir "$ROOT/training-materials/$theme"
    ;;
  *)
    echo "usage: scripts/training-run.sh generate [--theme 主题] [--force] | self-check [主题]" >&2
    exit 2
    ;;
esac
