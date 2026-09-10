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
assert mod.parse_only("评估反馈表") == {"08-evaluation-form.md"}
assert mod.parse_only("08") == {"08-evaluation-form.md"}
stages = [
    {"id": "t3", "outputs": ["04-instructor-manual.md"]},
    {"id": "t4", "outputs": ["05-participant-handbook.md"]},
    {"id": "t5", "outputs": ["06-assessment.md"]},
    {"id": "t6", "outputs": ["07-delivery-guide.md"]},
    {"id": "t7", "outputs": ["08-evaluation-form.md"]},
]
sel = mod.stages_for_outputs(wanted, stages)
assert [s["id"] for s in sel] == ["t4", "t5"], sel
sel08 = mod.stages_for_outputs({"08-evaluation-form.md"}, stages)
assert [s["id"] for s in sel08] == ["t7"], sel08

# 点名 08 时，未点名文件缺失不得把 RESULT 打成 failure
import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    (out / "08-evaluation-form.md").write_text(
        "> AI 辅助生成、讲师审核后交付\n\n" + ("评估项\n" * 20),
        encoding="utf-8",
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mod.emit_result(
            out, True, extra="self_check_exit=0", wanted={"08-evaluation-form.md"}
        )
    text = buf.getvalue()
    assert code == 0, (code, text)
    assert "RESULT: success" in text, text
    assert "08-evaluation-form.md" in text
    assert "01-needs-analysis.md" not in text.split("MISSING:", 1)[-1]
print("ok")
