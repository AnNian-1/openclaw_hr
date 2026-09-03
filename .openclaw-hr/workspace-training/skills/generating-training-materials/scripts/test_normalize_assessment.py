#!/usr/bin/env python3
"""【T1】缩写会挡住 self_check；落盘前必须展开。"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generate_pack", HERE / "generate_pack.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

raw = """===FILE: training-materials/06-assessment.md===
# 课测

**1. 【基础】【T1】** 题干
**7. 【中等】【T2 & T5】** 题干
"""
out = mod.normalize_assessment(raw)
assert not out.startswith("===FILE:"), out[:40]
assert "【对应培训目标T1】" in out
assert "【对应培训目标T2 & T5】" in out
assert "【T1】" not in out
# 已写全称的不要叠成「对应培训目标对应培训目标」
twice = mod.normalize_assessment("**1. 【对应培训目标T1】**\n")
assert twice.count("对应培训目标") == 1, twice

legend = mod.normalize_assessment("# 课测\n\n见矩阵 T1 T2 T3 T4 T5。\n")
assert "对应培训目标" in legend

print("ok")
