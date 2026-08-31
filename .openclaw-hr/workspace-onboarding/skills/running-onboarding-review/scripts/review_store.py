#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local probation review table for onboarding workspace.

Truth source for 7/30/60/90 day follow-ups. HCM keeps roster + prep nodes only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

REVIEW_DAYS = (7, 30, 60, 90)

FOCUS_BY_DAY: dict[int, str] = {
    7: "完成公司级 Onboarding;导师启动带教;融入团队",
    30: "部门岗位培训;HR 第一次新人关怀沟通",
    60: "带教进展检查;岗位胜任度初评",
    90: "导师带教结束;6 个月试用期者中期反馈",
}


def workspace_root(explicit: str | None = None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    env = os.environ.get("ONBOARDING_WORKSPACE") or os.environ.get("WORKSPACE")
    if env:
        return os.path.abspath(env)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def table_path(ws: str | None = None) -> str:
    return os.path.join(workspace_root(ws), "review-state", "reviews.json")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _empty_table() -> dict[str, Any]:
    return {"version": 1, "records": [], "armed": {}}


def load_table(ws: str | None = None) -> dict[str, Any]:
    path = table_path(ws)
    if not os.path.exists(path):
        return _empty_table()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return _empty_table()
    data.setdefault("version", 1)
    data.setdefault("records", [])
    data.setdefault("armed", {})
    return data


def save_table(data: dict[str, Any], ws: str | None = None) -> None:
    path = table_path(ws)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _key(pinyin: str, day: int) -> tuple[str, int]:
    return (pinyin.strip().lower(), int(day))


def find_record(records: list[dict[str, Any]], pinyin: str, day: int) -> dict[str, Any] | None:
    pin = pinyin.strip().lower()
    for rec in records:
        if rec.get("pinyin", "").strip().lower() == pin and int(rec.get("day", 0)) == int(day):
            return rec
    return None


def ensure(name: str, pinyin: str, ws: str | None = None) -> list[dict[str, Any]]:
    data = load_table(ws)
    records: list[dict[str, Any]] = data["records"]
    created: list[dict[str, Any]] = []
    pin = pinyin.strip().lower()
    for day in REVIEW_DAYS:
        if find_record(records, pin, day):
            continue
        rec = {
            "name": name,
            "pinyin": pin,
            "day": day,
            "status": "pending",
            "focus": FOCUS_BY_DAY[day],
            "content": None,
            "triggered_at": None,
            "completed_at": None,
        }
        records.append(rec)
        created.append(rec)
    if created:
        save_table(data, ws)
    return created


def get(pinyin: str, day: int, ws: str | None = None) -> dict[str, Any] | None:
    data = load_table(ws)
    return find_record(data["records"], pinyin, day)


def list_records(
    *,
    pinyin: str | None = None,
    pending_only: bool = False,
    ws: str | None = None,
) -> list[dict[str, Any]]:
    data = load_table(ws)
    out = data["records"]
    if pinyin:
        pin = pinyin.strip().lower()
        out = [r for r in out if r.get("pinyin", "").strip().lower() == pin]
    if pending_only:
        out = [r for r in out if r.get("status") == "pending"]
    return sorted(out, key=lambda r: (r.get("pinyin", ""), int(r.get("day", 0))))


def all_reviews_map(pinyin: str, ws: str | None = None) -> dict[str, str]:
    return {f"day{d}": (get(pinyin, d, ws) or {}).get("status", "pending") for d in REVIEW_DAYS}


def touch_triggered(pinyin: str, day: int, ws: str | None = None) -> dict[str, Any] | None:
    data = load_table(ws)
    rec = find_record(data["records"], pinyin, day)
    if not rec:
        return None
    if not rec.get("triggered_at"):
        rec["triggered_at"] = _utcnow_iso()
        save_table(data, ws)
    return rec


def mark_done(
    name: str,
    pinyin: str,
    day: int,
    content: str | None = None,
    ws: str | None = None,
) -> dict[str, Any]:
    if int(day) not in REVIEW_DAYS:
        raise ValueError(f"非法 day={day}")
    data = load_table(ws)
    rec = find_record(data["records"], pinyin, day)
    if not rec:
        ensure(name, pinyin, ws)
        data = load_table(ws)
        rec = find_record(data["records"], pinyin, day)
    if not rec:
        raise RuntimeError("ensure 后仍找不到记录")
    rec["name"] = name
    rec["status"] = "completed"
    rec["completed_at"] = _utcnow_iso()
    if content is not None:
        rec["content"] = content
    save_table(data, ws)
    return rec


def is_armed(pinyin: str, ws: str | None = None) -> bool:
    data = load_table(ws)
    return pinyin.strip().lower() in (data.get("armed") or {})


def mark_armed(pinyin: str, ws: str | None = None) -> None:
    data = load_table(ws)
    data.setdefault("armed", {})
    data["armed"][pinyin.strip().lower()] = {"scheduled_at": _utcnow_iso()}
    save_table(data, ws)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="入职试用期跟进本地表")
    parser.add_argument("--workspace", default=None, help="workspace-onboarding 根目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出记录")
    p_list.add_argument("--pending", action="store_true", help="仅 pending")
    p_list.add_argument("--pinyin", default=None)

    p_get = sub.add_parser("get", help="按拼音+天数查询")
    p_get.add_argument("pinyin")
    p_get.add_argument("day", type=int)

    p_ensure = sub.add_parser("ensure", help="确保 7/30/60/90 四行 pending 存在")
    p_ensure.add_argument("name")
    p_ensure.add_argument("pinyin")

    p_armed = sub.add_parser("is-armed", help="是否已挂过跟进 Cron")
    p_armed.add_argument("pinyin")
    p_mark = sub.add_parser("mark-armed", help="标记已注册 Cron")
    p_mark.add_argument("pinyin")
    p_done = sub.add_parser("mark-done", help="HR 确认后标为已完成")
    p_done.add_argument("name")
    p_done.add_argument("pinyin")
    p_done.add_argument("day", type=int)
    p_done.add_argument("--content", default=None)

    args = parser.parse_args(argv)
    ws = args.workspace

    try:
        if args.cmd == "list":
            rows = list_records(pinyin=args.pinyin, pending_only=args.pending, ws=ws)
            print(json.dumps({"ok": True, "records": rows}, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "get":
            rec = get(args.pinyin, args.day, ws=ws)
            if not rec:
                print(json.dumps({"ok": False, "error": "not_found"}, ensure_ascii=False))
                return 1
            print(json.dumps({"ok": True, "record": rec}, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "ensure":
            created = ensure(args.name, args.pinyin, ws=ws)
            print(json.dumps({
                "ok": True,
                "created": len(created),
                "records": created,
            }, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "mark-done":
            rec = mark_done(args.name, args.pinyin, args.day, content=args.content, ws=ws)
            print(json.dumps({"ok": True, "record": rec}, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "is-armed":
            print(json.dumps({"ok": True, "armed": is_armed(args.pinyin, ws=ws)}, ensure_ascii=False))
            return 0
        if args.cmd == "mark-armed":
            mark_armed(args.pinyin, ws=ws)
            print(json.dumps({"ok": True, "armed": True}, ensure_ascii=False))
            return 0
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
