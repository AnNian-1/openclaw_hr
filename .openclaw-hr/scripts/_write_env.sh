#!/usr/bin/env bash
set -euo pipefail
PROFILE=/home/hr/.openclaw-hr
SRC=/root/hr_claw_hub/openclaw-hr/env.sh

cp "$SRC" "$PROFILE/env.sh"
chown hr:hr "$PROFILE/env.sh"
chmod 640 "$PROFILE/env.sh"

python3 - <<'PY'
from pathlib import Path
p = Path("/home/hr/.openclaw-hr/env.sh")
text = p.read_text()
marker = "# --- local WSL overrides (/home/hr) ---"
if marker in text:
    text = text.split(marker)[0].rstrip() + "\n"
block = """
# --- local WSL overrides (/home/hr) ---
export OPENCLAW_STATE_DIR=/home/hr/.openclaw-hr
export OPENCLAW_CONFIG_PATH=/home/hr/.openclaw-hr/config/openclaw.yaml
export OPENCLAW_HR_BIN=/home/hr/.openclaw-hr/install/node_modules/.bin/openclaw
export PATH=/home/annian/.nvm/versions/node/v22.23.1/bin:/home/hr/.openclaw-hr/install/node_modules/.bin:$PATH
"""
p.write_text(text + "\n" + block)
print("env overrides written")
PY
