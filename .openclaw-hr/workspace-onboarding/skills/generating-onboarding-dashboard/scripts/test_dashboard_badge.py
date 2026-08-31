#!/usr/bin/env python3
"""看板角标：HCM 5 节点为主，data.status 优先，审批门单独标。"""
import datetime
import importlib.util
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dash", HERE / "build-dashboard.py")
dash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dash)


def test_data_status_overrides_in_progress():
    display, cls = dash.node_display_and_cls({
        "status": "in_progress",
        "data": {"status": "已审批"},
    })
    assert display == "已审批"
    assert cls == "done"


def test_hcm_badge_not_workflow_completed():
    prep = [{"cls": "pending"}] * 5
    b = dash.hcm_prep_badge(prep)
    assert b["text"].startswith("待启动")
    mixed = [{"cls": "done"}] * 2 + [{"cls": "pending"}] * 3
    b2 = dash.hcm_prep_badge(mixed)
    assert b2["text"].startswith("入职中")
    done = [{"cls": "done"}] * 5
    assert dash.hcm_prep_badge(done)["text"].startswith("已完成")


def test_gate_timeout_copy():
    halted_at = (
        datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
        - datetime.timedelta(days=4)
    ).isoformat(timespec="seconds")
    g = dash.gate_badge({
        "status": "halted",
        "current_step": "contract_gate",
        "halted_at": halted_at,
    })
    assert g and "请催办" in g["text"]


if __name__ == "__main__":
    test_data_status_overrides_in_progress()
    test_hcm_badge_not_workflow_completed()
    test_gate_timeout_copy()
    print("ok")
