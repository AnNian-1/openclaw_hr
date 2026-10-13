#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只请求 HCM 已冻结月报 API，转成 pandas frames。不读 CSV。"""

import json
import urllib.error
import urllib.request


def _http_json(url: str, method: str = "GET", timeout: float = 30) -> dict:
    headers = {"Accept": "application/json"}
    kwargs = {"headers": headers, "method": method}
    if method == "POST":
        kwargs["data"] = b""
    req = urllib.request.Request(url, **kwargs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"[ERROR] HCM HTTP {exc.code} {url}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"[ERROR] HCM 不可达: {url}\n{exc.reason}\n请先启动 HCM 并冻结对应月份。禁止回退 CSV。"
        ) from exc


def freeze_month(base_url: str, month: str) -> dict:
    return _http_json(f"{base_url.rstrip('/')}/api/reports/monthly/{month}/freeze", method="POST")


def fetch_monthly_payload(base_url: str, month: str) -> dict:
    if not month:
        raise SystemExit("[ERROR] 必须指定月份 YYYY-MM，禁止默认读上一期冻结")
    payload = _http_json(f"{base_url.rstrip('/')}/api/reports/monthly/{month}")
    if payload.get("source") != "HCM":
        raise SystemExit("[ERROR] 拒绝非 HCM 来源的月报 payload")
    if payload.get("month") and payload["month"] != month:
        raise SystemExit(f"[ERROR] HCM 返回月份 {payload.get('month')} 与请求 {month} 不一致")
    if not payload.get("report_run_id"):
        raise SystemExit("[ERROR] 响应缺少 report_run_id")
    return payload


def frames_from_payload(payload: dict) -> dict:
    import pandas as pd

    return {
        "funnel": pd.DataFrame(payload["recruitment_funnel"]),
        "positions": pd.DataFrame(payload["positions_progress"]),
        "retention": pd.DataFrame(payload["onboarding_retention"]),
        "training": pd.DataFrame(payload["training_completion"]),
        "cost": pd.DataFrame(payload["hiring_cost"]),
        "attrition": pd.DataFrame(payload["attrition"]),
    }


def load_six_frames(*, hcm_base: str, month: str):
    payload = fetch_monthly_payload(hcm_base, month)
    meta = {
        "metric_version": payload.get("metric_version"),
        "report_run_id": payload.get("report_run_id"),
        "frozen_at": payload.get("frozen_at"),
        "source": "HCM",
        "node_audit": payload.get("node_audit") or {},
    }
    return frames_from_payload(payload), meta
