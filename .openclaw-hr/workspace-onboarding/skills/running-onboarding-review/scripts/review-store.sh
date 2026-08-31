#!/usr/bin/env bash
# review-store.sh — 试用期跟进本地表 CLI（Agent allowlist 入口）
# 用法:
#   review-store.sh list [--pending] [--pinyin <pinyin>]
#   review-store.sh get <pinyin> <day>
#   review-store.sh ensure <name> <pinyin>
#   review-store.sh mark-done <name> <pinyin> <day> [--content "..."]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ONBOARDING_WORKSPACE:-${WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}}"

exec python3 "$SCRIPT_DIR/review_store.py" --workspace "$WORKSPACE" "$@"
