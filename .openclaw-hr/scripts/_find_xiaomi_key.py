#!/usr/bin/env python3
from pathlib import Path

need = "XIAOMI_API_KEY"
found_proc = False
for pid in Path("/proc").iterdir():
    if not pid.name.isdigit():
        continue
    envp = pid / "environ"
    try:
        data = envp.read_bytes()
    except Exception:
        continue
    for item in data.split(b"\0"):
        if item.startswith(need.encode() + b"="):
            val = item.split(b"=", 1)[1]
            print("proc", pid.name, "has_key", bool(val), "len", len(val))
            found_proc = True
print("proc_found", found_proc)

roots = [Path("/home/annian"), Path("/root"), Path("/opt/openclaw-hr")]
hits = []
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in ("node_modules", ".git", "logs")):
            continue
        if p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if need in text:
            hits.append(str(p))
print("file_hits", len(hits))
for h in hits[:40]:
    print(h)
