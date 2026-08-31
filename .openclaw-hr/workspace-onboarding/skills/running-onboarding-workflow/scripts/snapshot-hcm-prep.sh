#!/usr/bin/env bash
# snapshot-hcm-prep.sh — 从 HCM 快照节点到 stub-state，不编造
# 用法: snapshot-hcm-prep.sh <pinyin> [--name 姓名] [--nodes contract,account] [--require-gate contract]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$@"
