#!/usr/bin/env bash
# review-store.sh — 试用期跟进本地表 CLI（回填只走 CLI，飞书只催办）
# 用法:
#   review-store.sh list [--pending] [--pinyin <pinyin>]
#   review-store.sh get <pinyin> <day>
#   review-store.sh ensure <name> <pinyin>
#   review-store.sh record <name> <pinyin> <day> --outcome ok|watch|risk|skipped \
#       [--summary "..."] [--checklist-json '[...]'] [--next-action "..."] \
#       [--next-action-due YYYY-MM-DD] [--reviewer "..."]
#   review-store.sh mark-done <name> <pinyin> <day> [--content "..."]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ONBOARDING_WORKSPACE:-${WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}}"

exec python3 "$SCRIPT_DIR/review_store.py" --workspace "$WORKSPACE" "$@"
