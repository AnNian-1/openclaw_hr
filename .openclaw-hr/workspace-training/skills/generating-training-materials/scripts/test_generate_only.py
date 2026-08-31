#!/usr/bin/env python3
"""--only 解析不扩成全套。"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generate_pack", HERE / "generate_pack.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

wanted = mod.parse_only("学员手册,测试题")
assert wanted == {"05-participant-handbook.md", "06-assessment.md"}, wanted
stages = [
    {"id": "t3", "outputs": ["04-instructor-manual.md"]},
    {"id": "t4", "outputs": ["05-participant-handbook.md"]},
    {"id": "t5", "outputs": ["06-assessment.md"]},
    {"id": "t6", "outputs": ["07-delivery-guide.md"]},
]
sel = mod.stages_for_outputs(wanted, stages)
assert [s["id"] for s in sel] == ["t4", "t5"], sel
print("ok")
