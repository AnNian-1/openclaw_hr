#!/bin/bash
# 只读快照 HCM 行政设备节点，不编造已配齐。
NAME="${1:-员工}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PINYIN="$(basename "${STUB_STATE_DIR:-}")"
exec python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$PINYIN" --name "$NAME" --nodes device
