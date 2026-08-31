#!/bin/bash
# 只读快照 HCM 合同节点，不编造合同内容。
NAME="${1:-员工}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PINYIN="$(basename "${STUB_STATE_DIR:-}")"
exec python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$PINYIN" --name "$NAME" --nodes contract
