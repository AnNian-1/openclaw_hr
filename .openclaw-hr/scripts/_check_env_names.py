from pathlib import Path

text = Path("/home/hr/.openclaw-hr/env.sh").read_text()
watch = {"OPENCLAW_STATE_DIR", "OPENCLAW_CONFIG_PATH", "OPENCLAW_HR_BIN", "PATH"}
for line in text.splitlines():
    s = line.strip()
    if not s.startswith("export ") or "=" not in s:
        continue
    k, v = s[7:].split("=", 1)
    if k in watch:
        empty = not bool(v.strip().strip('"').strip("'"))
        print(f"{k} empty={empty} len={len(v)}")
