#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local probation review table for onboarding workspace.

Truth source for 7/30/60/90 day follow-ups. HCM keeps roster + prep nodes only.
Cron only marks due / triggered_at. HR backfill is CLI (`record` / `mark-done`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

REVIEW_DAYS = (7, 30, 60, 90)
SHANGHAI = ZoneInfo("Asia/Shanghai")

FOCUS_BY_DAY: dict[int, str] = {
    7: "完成公司级 Onboarding;导师启动带教;融入团队",
    30: "部门岗位培训;HR 第一次新人关怀沟通",
    60: "带教进展检查;岗位胜任度初评",
    90: "导师带教结束;6 个月试用期者中期反馈",
}

OUTCOMES = ("ok", "watch", "risk", "skipped")
CHECKLIST_STATES = ("done", "not_done", "na")
OPEN_STATUSES = ("pending", "due")
DONE_STATUSES = ("completed", "skipped")


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


def default_checklist(day: int) -> list[dict[str, str]]:
    focus = FOCUS_BY_DAY.get(int(day), "")
    items = [part.strip() for part in focus.split(";") if part.strip()]
    return [{"item": item, "state": "not_done", "note": ""} for item in items]


def _empty_table() -> dict[str, Any]:
    return {"version": 2, "records": [], "armed": {}}


def _normalize_checklist(raw: Any, day: int) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        return default_checklist(day)
    out: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or "").strip()
        if not item:
            continue
        state = str(row.get("state") or "not_done").strip()
        if state not in CHECKLIST_STATES:
            state = "not_done"
        out.append({"item": item, "state": state, "note": str(row.get("note") or "")})
    return out or default_checklist(day)


def normalize_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Fill new fields on old rows. Does not persist by itself."""
    day = int(rec.get("day") or 0)
    rec.setdefault("status", "pending")
    rec.setdefault("focus", FOCUS_BY_DAY.get(day, ""))
    rec.setdefault("content", None)
    rec.setdefault("triggered_at", None)
    rec.setdefault("completed_at", None)
    rec.setdefault("outcome", None)
    rec.setdefault("next_action", None)
    rec.setdefault("next_action_due", None)
    rec.setdefault("reviewer", None)
    rec["checklist"] = _normalize_checklist(rec.get("checklist"), day)
    if rec.get("summary") in (None, "") and rec.get("content"):
        rec["summary"] = rec["content"]
    else:
        rec.setdefault("summary", rec.get("content"))
    rec["display_status"] = display_status(rec)
    return rec


def display_status(rec: dict[str, Any]) -> str:
    """Stored status, with overdue derived from due + triggered_at (Shanghai date)."""
    status = rec.get("status") or "pending"
    if status != "due":
        return status
    raw = rec.get("triggered_at")
    if not raw:
        return "due"
    try:
        triggered = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return "due"
    if triggered.tzinfo is None:
        triggered = triggered.replace(tzinfo=timezone.utc)
    trig_day = triggered.astimezone(SHANGHAI).date()
    today = datetime.now(SHANGHAI).date()
    if trig_day < today:
        return "overdue"
    return "due"


def load_table(ws: str | None = None) -> dict[str, Any]:
    path = table_path(ws)
    if not os.path.exists(path):
        return _empty_table()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return _empty_table()
    data.setdefault("version", 2)
    data.setdefault("records", [])
    data.setdefault("armed", {})
    for rec in data["records"]:
        if isinstance(rec, dict):
            normalize_record(rec)
    return data


def save_table(data: dict[str, Any], ws: str | None = None) -> None:
    path = table_path(ws)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "version": 2,
        "records": data.get("records") or [],
        "armed": data.get("armed") or {},
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def find_record(records: list[dict[str, Any]], pinyin: str, day: int) -> dict[str, Any] | None:
    pin = pinyin.strip().lower()
    for rec in records:
        if rec.get("pinyin", "").strip().lower() == pin and int(rec.get("day", 0)) == int(day):
            return rec
    return None


def _new_record(name: str, pinyin: str, day: int) -> dict[str, Any]:
    rec = {
        "name": name,
        "pinyin": pinyin,
        "day": day,
        "status": "pending",
        "focus": FOCUS_BY_DAY[day],
        "content": None,
        "summary": None,
        "outcome": None,
        "checklist": default_checklist(day),
        "next_action": None,
        "next_action_due": None,
        "reviewer": None,
        "triggered_at": None,
        "completed_at": None,
    }
    return normalize_record(rec)


def ensure(name: str, pinyin: str, ws: str | None = None) -> list[dict[str, Any]]:
    data = load_table(ws)
    records: list[dict[str, Any]] = data["records"]
    created: list[dict[str, Any]] = []
    pin = pinyin.strip().lower()
    for day in REVIEW_DAYS:
        rec = find_record(records, pin, day)
        if rec:
            rec["name"] = name
            continue
        rec = _new_record(name, pin, day)
        records.append(rec)
        created.append(rec)
    save_table(data, ws)
    return created


def get(pinyin: str, day: int, ws: str | None = None) -> dict[str, Any] | None:
    data = load_table(ws)
    rec = find_record(data["records"], pinyin, day)
    return rec


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
        out = [r for r in out if (r.get("status") or "pending") in OPEN_STATUSES]
    return sorted(out, key=lambda r: (r.get("pinyin", ""), int(r.get("day", 0))))


def all_reviews_map(pinyin: str, ws: str | None = None) -> dict[str, str]:
    return {f"day{d}": display_status(get(pinyin, d, ws) or {"status": "pending"}) for d in REVIEW_DAYS}


def touch_triggered(pinyin: str, day: int, ws: str | None = None) -> dict[str, Any] | None:
    """Cron/query first fire: stamp triggered_at and pending → due. Never completes."""
    data = load_table(ws)
    rec = find_record(data["records"], pinyin, day)
    if not rec:
        return None
    changed = False
    if not rec.get("triggered_at"):
        rec["triggered_at"] = _utcnow_iso()
        changed = True
    if rec.get("status") == "pending":
        rec["status"] = "due"
        changed = True
    if changed:
        save_table(data, ws)
    return normalize_record(rec)


def record(
    name: str,
    pinyin: str,
    day: int,
    *,
    outcome: str,
    summary: str | None = None,
    checklist: list[dict[str, str]] | None = None,
    next_action: str | None = None,
    next_action_due: str | None = None,
    reviewer: str | None = None,
    ws: str | None = None,
) -> dict[str, Any]:
    if int(day) not in REVIEW_DAYS:
        raise ValueError(f"非法 day={day}")
    outcome_n = (outcome or "").strip().lower()
    if outcome_n not in OUTCOMES:
        raise ValueError(f"非法 outcome={outcome}，允许 {', '.join(OUTCOMES)}")
    data = load_table(ws)
    rec = find_record(data["records"], pinyin, day)
    if not rec:
        ensure(name, pinyin, ws)
        data = load_table(ws)
        rec = find_record(data["records"], pinyin, day)
    if not rec:
        raise RuntimeError("ensure 后仍找不到记录")
    rec["name"] = name
    rec["outcome"] = outcome_n
    rec["status"] = "skipped" if outcome_n == "skipped" else "completed"
    rec["completed_at"] = _utcnow_iso()
    if summary is not None:
        rec["summary"] = summary
        rec["content"] = summary
    if checklist is not None:
        rec["checklist"] = _normalize_checklist(checklist, int(day))
    if next_action is not None:
        rec["next_action"] = next_action
    if next_action_due is not None:
        rec["next_action_due"] = next_action_due
    if reviewer is not None:
        rec["reviewer"] = reviewer
    save_table(data, ws)
    return normalize_record(rec)


def mark_done(
    name: str,
    pinyin: str,
    day: int,
    content: str | None = None,
    ws: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible complete: outcome=ok, summary from --content."""
    return record(name, pinyin, day, outcome="ok", summary=content, ws=ws)


def is_armed(pinyin: str, ws: str | None = None) -> bool:
    data = load_table(ws)
    return pinyin.strip().lower() in (data.get("armed") or {})


def mark_armed(pinyin: str, ws: str | None = None) -> None:
    data = load_table(ws)
    data.setdefault("armed", {})
    data["armed"][pinyin.strip().lower()] = {"scheduled_at": _utcnow_iso()}
    save_table(data, ws)


def _parse_checklist_arg(raw: str | None, day: int) -> list[dict[str, str]] | None:
    if raw is None:
        return None
    parsed = json.loads(raw)
    return _normalize_checklist(parsed, day)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="入职试用期跟进本地表")
    parser.add_argument("--workspace", default=None, help="workspace-onboarding 根目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出记录")
    p_list.add_argument("--pending", action="store_true", help="仅 pending/due（尚未回填）")
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
    p_done = sub.add_parser("mark-done", help="兼容：标 completed + outcome=ok")
    p_done.add_argument("name")
    p_done.add_argument("pinyin")
    p_done.add_argument("day", type=int)
    p_done.add_argument("--content", default=None)

    p_rec = sub.add_parser("record", help="HR 回填结论（CLI）；飞书不走这条")
    p_rec.add_argument("name")
    p_rec.add_argument("pinyin")
    p_rec.add_argument("day", type=int)
    p_rec.add_argument("--outcome", required=True, help="ok / watch / risk / skipped")
    p_rec.add_argument("--summary", default=None, help="纪要")
    p_rec.add_argument("--content", default=None, help="纪要别名（同 --summary）")
    p_rec.add_argument("--checklist-json", default=None, help='[{"item":"...","state":"done|not_done|na","note":""}]')
    p_rec.add_argument("--next-action", default=None)
    p_rec.add_argument("--next-action-due", default=None, help="YYYY-MM-DD")
    p_rec.add_argument("--reviewer", default=None)

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
        if args.cmd == "record":
            summary = args.summary if args.summary is not None else args.content
            rec = record(
                args.name,
                args.pinyin,
                args.day,
                outcome=args.outcome,
                summary=summary,
                checklist=_parse_checklist_arg(args.checklist_json, args.day),
                next_action=args.next_action,
                next_action_due=args.next_action_due,
                reviewer=args.reviewer,
                ws=ws,
            )
            print(json.dumps({"ok": True, "record": rec}, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "is-armed":
            print(json.dumps({"ok": True, "armed": is_armed(args.pinyin, ws=ws)}, ensure_ascii=False))
            return 0
        if args.cmd == "mark-armed":
            mark_armed(args.pinyin, ws=ws)
            print(json.dumps({"ok": True, "armed": True}, ensure_ascii=False))
            return 0
    except (ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
