#!/usr/bin/env bash
# Rewrite old repo roots to this WSL clone.
# Does not touch conda, /opt/node, or /opt/hr-ops.
# Old roots are split so this file cannot rewrite itself.
set -euo pipefail
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
python3 - "$SELF" <<'PY'
from pathlib import Path
import sys

self = Path(sys.argv[1]).resolve()
root = Path("/opt/openclaw-hr")
skip_dir_names = {
    ".git",
    "node_modules",
    ".cache",
    ".npm",
    ".local",
    "pre_docs",
    "openclaw-rh-20260807",
    "sessions",
    "memory",
    "logs",
}
skip_file_suffixes = {".sqlite", ".7z", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".woff", ".woff2", ".pyc"}
text_suffixes = {
    ".yaml", ".yml", ".json", ".sh", ".conf", ".md", ".py", ".cjs", ".js",
    ".example", ".txt", ".html", ".lobster", ".csv", ".toml", ".last-good",
}
old_wsl = "/home/" + "yhwz/openclaw-hr"
old_opt = "/opt/" + "openclaw-hr"
replacements = [
    (old_wsl, "/opt/openclaw-hr"),
    (old_opt, "/opt/openclaw-hr"),
]
changed = []
for p in root.rglob("*"):
    if not p.is_file():
        continue
    if p.resolve() == self:
        continue
    if any(part in skip_dir_names for part in p.parts):
        continue
    if p.suffix.lower() in skip_file_suffixes:
        continue
    if p.suffix.lower() not in text_suffixes and p.name not in {"installs.json", "env.sh"}:
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    orig = text
    for a, b in replacements:
        text = text.replace(a, b)
    if text != orig:
        p.write_text(text, encoding="utf-8")
        changed.append(str(p.relative_to(root)))
print("files_changed", len(changed))
for rel in changed:
    print(rel)
PY
