#!/bin/bash
# 只读快照 HCM IT 账号节点，不编造工号/邮箱。
NAME="${1:-员工}"
PINYIN="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PINYIN="${PINYIN:-$(basename "${STUB_STATE_DIR:-}")}"
exec python3 "$SCRIPT_DIR/snapshot_hcm_prep.py" "$PINYIN" --name "$NAME" --nodes account
