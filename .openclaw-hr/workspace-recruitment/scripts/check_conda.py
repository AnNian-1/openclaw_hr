#!/usr/bin/env python3
"""Check for conda envs that might have funasr."""
import os
import subprocess
from pathlib import Path

home = Path.home()

# Check FUNASR_VENV env
fv = os.environ.get("FUNASR_VENV")
print(f"FUNASR_VENV env: {fv or '(not set)'}")

# Check common conda locations
for base in [
    home / "miniconda3" / "envs",
    home / "anaconda3" / "envs",
    Path("/usr/local/miniconda3/envs"),
    home / ".local" / "miniconda3" / "envs",
]:
    if base.is_dir():
        envs = [d.name for d in base.iterdir() if d.is_dir()]
        print(f"{base}: {envs}")
        for e in envs:
            py = base / e / "bin" / "python3"
            if py.is_file():
                print(f"  {e} -> {py}")
    else:
        print(f"{base}: (not found)")

# Check if default_script's venv finder works
print("\n--- Script's default_funasr_venv() logic ---")
for p in [
    home / "miniconda3" / "envs" / "funasr_me",
    Path("/usr/local/miniconda3/envs/funasr_me"),
    home / ".local" / "miniconda3" / "envs" / "funasr_me",
]:
    has_py = (p / "bin" / "python3").is_file() or (p / "bin" / "python").is_file()
    print(f"  {p}: {'FOUND' if has_py else 'not found'}")
