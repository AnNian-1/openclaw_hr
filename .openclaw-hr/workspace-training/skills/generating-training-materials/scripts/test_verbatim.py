#!/usr/bin/env python3
"""self_check 不把「而非逐字稿」当正文违规。"""
import tempfile
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("self_check", HERE / "self_check.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert not mod.forbidden_verbatim("本手册与大纲逐页对应，**而非逐字稿**。含讲解要点。")
assert mod.forbidden_verbatim("各位同学大家好，下面是逐字稿：今天我们学习……")
print("ok")
