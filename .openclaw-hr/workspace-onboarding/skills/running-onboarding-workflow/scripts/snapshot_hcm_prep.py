#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 HCM 只读快照五部门节点到 stub-state，不编造部门产出。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import hcm_api

SHANGHAI = ZoneInfo("Asia/Shanghai")
STATUS_LABELS = {
    "pending": "未开始",
    "in_progress": "进行中",
    "completed": "已完成",
    "paused": "暂停",
    "rejected": "否决",
}

SYSTEM_NAME = {
    "contract": "合同文件",
    "account": "IT账号",
    "device": "行政设备",
    "training": "培训安排",
    "buddy": "Buddy匹配",
}


def _now():
    return datetime.now(SHANGHAI).replace(microsecond=0).isoformat()


def _state_dir():
    d = os.environ.get("STUB_STATE_DIR")
    if not d:
        sys.stderr.write("[snapshot-hcm] 缺少 STUB_STATE_DIR\n")
        sys.exit(2)
    os.makedirs(d, exist_ok=True)
    return d


def snapshot_one(pinyin: str, node_type: str, name: str, summary: dict) -> dict:
    info = summary["nodes"].get(node_type) or {}
    hcm_status = info.get("status") or "pending"
    data = dict(info.get("data") or {})
    now = _now()
    rec = {
        "system": SYSTEM_NAME.get(node_type, node_type),
        "candidate": summary.get("name") or name,
        "hcm_status": hcm_status,
        "status": STATUS_LABELS.get(hcm_status, hcm_status),
        "source": "hcm",
        "updated_at": now,
        **{k: v for k, v in data.items() if k not in ("status", "system", "candidate")},
    }
    path = os.path.join(_state_dir(), f"{node_type}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    label = hcm_api.NODE_LABELS.get(node_type, node_type)
    print(f"[HCM] {label}: {rec['status']} ({hcm_status})", file=sys.stderr)
    return rec


def print_report(summary: dict) -> None:
    print("=== HCM 五部门节点（只读，未完成请催对应部门）===", file=sys.stderr)
    for t in hcm_api.PREP_NODE_TYPES:
        n = summary["nodes"].get(t) or {}
        st = n.get("status", "pending")
        print(f"  {n.get('label', t):8s} {STATUS_LABELS.get(st, st)}", file=sys.stderr)
    pending = summary.get("pending") or []
    if pending:
        names = [hcm_api.NODE_LABELS.get(t, t) for t in pending]
        print(f"尚未完成：{', '.join(names)}", file=sys.stderr)
    else:
        print("五节点均已 completed。", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pinyin")
    parser.add_argument("--name", default="")
    parser.add_argument("--nodes", default="contract,account,device,training,buddy")
    parser.add_argument(
        "--require-gate",
        default="",
        help="逗号分隔；这些节点须 in_progress 或 completed，否则 exit 6",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="把摘要打到 stdout（默认只写 stderr，避免污染 lobster 审批 JSON）",
    )
    args = parser.parse_args()
    types = [t.strip() for t in args.nodes.split(",") if t.strip()]
    summary = hcm_api.summarize_prep(args.pinyin)
    if not summary.get("hcm_up"):
        print("[snapshot-hcm] HCM 不可用", file=sys.stderr)
        return 5
    if not summary.get("found"):
        print(f"[snapshot-hcm] 花名册没有拼音 {args.pinyin}", file=sys.stderr)
        return 4
    for t in types:
        snapshot_one(args.pinyin, t, args.name, summary)
    print_report(summary)
    require = [t.strip() for t in args.require_gate.split(",") if t.strip()]
    missing = [t for t in require if not summary.get("gate_ready", {}).get(t)]
    if missing:
        names = [hcm_api.NODE_LABELS.get(t, t) for t in missing]
        print(
            f"[snapshot-hcm] 审批材料未齐（HCM 仍为 pending）：{', '.join(names)}。"
            "请催对应部门在 HCM 填写后再启动/继续审批。入职小慧不代替部门执行。",
            file=sys.stderr,
        )
        return 6
    payload = {
        "ok": True,
        "all_completed": summary["all_completed"],
        "pending": summary["pending"],
        "gate_ready": summary["gate_ready"],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
