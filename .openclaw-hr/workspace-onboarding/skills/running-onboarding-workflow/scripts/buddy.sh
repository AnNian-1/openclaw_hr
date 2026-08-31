#!/bin/bash
# 只读快照 HCM Buddy 节点，不编造导师。
NAME="${1:-员工}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PINYIN="$(basename "${STUB_STATE_DIR:-}")"
exec python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$PINYIN" --name "$NAME" --nodes buddy
