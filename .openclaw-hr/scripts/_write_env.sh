#!/usr/bin/env bash
set -euo pipefail
PROFILE=/opt/openclaw-hr/.openclaw-hr
SRC=/root/hr_claw_hub/openclaw-hr/env.sh

cp "$SRC" "$PROFILE/env.sh"
chown hr:hr "$PROFILE/env.sh"
chmod 640 "$PROFILE/env.sh"

python3 - <<'PY'
from pathlib import Path
p = Path("/opt/openclaw-hr/.openclaw-hr/env.sh")
text = p.read_text()
marker = "# --- local WSL overrides (/opt/openclaw-hr) ---"
if marker in text:
    text = text.split(marker)[0].rstrip() + "\n"
block = """
# --- local WSL overrides (/opt/openclaw-hr) ---
export OPENCLAW_STATE_DIR=/opt/openclaw-hr/.openclaw-hr
export OPENCLAW_CONFIG_PATH=/opt/openclaw-hr/.openclaw-hr/config/openclaw.yaml
export OPENCLAW_HR_BIN=/opt/openclaw-hr/.openclaw-hr/install/node_modules/.bin/openclaw
export PATH=/opt/openclaw-hr/.local/node/node-22/bin:/opt/openclaw-hr/.openclaw-hr/install/node_modules/.bin:$PATH
"""
p.write_text(text + "\n" + block)
print("env overrides written")
PY
