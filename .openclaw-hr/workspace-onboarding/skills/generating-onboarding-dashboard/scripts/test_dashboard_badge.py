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


def _card(**kwargs):
    base = {
        "name": "员工1",
        "role": "后端工程师",
        "pinyin": "yuangong1",
        "hcm_status": "onboarding",
        "prep": [
            {"label": "合同签署", "raw": "待审批", "cls": "pending"},
            {"label": "IT 账号", "raw": "待审批", "cls": "pending"},
            {"label": "行政设备", "raw": "已配齐", "cls": "done"},
            {"label": "Buddy 匹配", "raw": "pending", "cls": "pending"},
            {"label": "入职培训", "raw": "已排期", "cls": "done"},
        ],
        "done_count": 2,
        "pct": 40,
        "badge": {"text": "入职中 2/5", "cls": "wf-active"},
        "gate_badge": None,
        "reviews": [],
        "review_done": 0,
        "review_armed": False,
    }
    base.update(kwargs)
    return dash.render_card(base)


def test_unarmed_review_hides_four_nodes():
    html = _card(
        hcm_status="cancelled",
        gate_badge={"text": "审批已取消", "cls": "wf-cancel"},
        reviews=[{"label": "第 7 天", "raw": "未开通", "cls": "pending"}] * 4,
        review_armed=False,
    )
    assert "试用期跟进" in html
    assert "未开通" in html
    assert "入职准备还没办完" in html
    assert "入职已取消，不开通" not in html
    assert "第 7 天" not in html
    assert "7/30/60/90" not in html
    assert html.count("node-label") == 5
    assert "审批已取消" in html


def test_armed_review_shows_days():
    html = _card(
        review_armed=True,
        review_done=1,
        reviews=[
            {"label": "第 7 天", "raw": "正常", "cls": "done"},
            {"label": "第 30 天", "raw": "未到点", "cls": "pending"},
            {"label": "第 60 天", "raw": "未到点", "cls": "pending"},
            {"label": "第 90 天", "raw": "未到点", "cls": "pending"},
        ],
    )
    assert "第 7 天" in html
    assert "7/30/60/90" in html
    assert "1/4 已回填" in html


if __name__ == "__main__":
    test_data_status_overrides_in_progress()
    test_hcm_badge_not_workflow_completed()
    test_gate_timeout_copy()
    test_unarmed_review_hides_four_nodes()
    test_armed_review_shows_days()
    print("ok")
