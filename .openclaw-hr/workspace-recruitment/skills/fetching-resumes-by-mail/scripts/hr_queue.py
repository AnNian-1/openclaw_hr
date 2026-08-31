#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HR 待办 + 覆盖后的下游重跑清单。

needs-hr.jsonl：不确定项，流水线照常跑，HR 拍板后再改。
needs-pipeline.jsonl：同一人覆盖后要重解析/增量评分的 stem。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

QUEUE_NAME = "needs-hr.jsonl"
PIPELINE_NAME = "needs-pipeline.jsonl"
IDENTITY_NAME = ".identity.json"


def queue_path(inbox_dir: Path) -> Path:
    return inbox_dir / QUEUE_NAME


def pipeline_path(inbox_dir: Path) -> Path:
    return inbox_dir / PIPELINE_NAME


def identity_path(inbox_dir: Path) -> Path:
    return inbox_dir / IDENTITY_NAME


def load_identity(inbox_dir: Path) -> Dict[str, Any]:
    p = identity_path(inbox_dir)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_identity(inbox_dir: Path, data: Dict[str, Any]) -> None:
    identity_path(inbox_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_hr(inbox_dir: Path, rec: Dict[str, Any]) -> Dict[str, Any]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    row = dict(rec)
    row.setdefault("status", "pending")
    row.setdefault("ts", _stamp())
    blob = json.dumps(row, ensure_ascii=False, sort_keys=True)
    row.setdefault("id", hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12])
    with queue_path(inbox_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[needs-hr] {row.get('kind')} id={row['id']} {row.get('name', '')}", file=sys.stderr)
    return row


def append_pipeline(inbox_dir: Path, rec: Dict[str, Any]) -> Dict[str, Any]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    row = dict(rec)
    row.setdefault("status", "pending")
    row.setdefault("ts", _stamp())
    row.setdefault("action", "reparse-score")
    with pipeline_path(inbox_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        f"[needs-pipeline] {row.get('saved_name') or row.get('stem')} 待重解析评分",
        file=sys.stderr,
    )
    return row


def _read_jsonl(path: Path, *, pending_only: bool = True) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if pending_only and obj.get("status", "pending") != "pending":
            continue
        out.append(obj)
    return out


def list_pipeline(inbox_dir: Path, *, pending_only: bool = True) -> List[Dict[str, Any]]:
    return _read_jsonl(pipeline_path(inbox_dir), pending_only=pending_only)


def list_records(inbox_dir: Path, *, pending_only: bool = True) -> List[Dict[str, Any]]:
    return _read_jsonl(queue_path(inbox_dir), pending_only=pending_only)


def mark_resolved(inbox_dir: Path, item_id: str, resolution: str) -> bool:
    p = queue_path(inbox_dir)
    if not p.is_file():
        return False
    found = False
    new_lines: List[str] = []
    now = _stamp()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        if obj.get("id") == item_id:
            obj["status"] = "resolved"
            obj["resolution"] = resolution
            obj["resolved_at"] = now
            found = True
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    if found:
        p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return found


def mark_pipeline_done(inbox_dir: Path, stem: str) -> int:
    p = pipeline_path(inbox_dir)
    if not p.is_file():
        return 0
    n = 0
    now = _stamp()
    new_lines: List[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        if obj.get("status", "pending") == "pending" and (
            obj.get("stem") == stem or Path(str(obj.get("saved_name") or "")).stem == stem
        ):
            obj["status"] = "done"
            obj["done_at"] = now
            n += 1
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="needs-hr / needs-pipeline")
    parser.add_argument("--inbox-dir", default="./inbox")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="pending HR 待办")
    sub.add_parser("list-pipeline", help="覆盖后待重解析评分的 stem")
    p_res = sub.add_parser("resolve", help="标记一条 HR 待办已拍板")
    p_res.add_argument("id")
    p_res.add_argument("--resolution", required=True)
    p_done = sub.add_parser("pipeline-done", help="该 stem 已重解析评分")
    p_done.add_argument("stem")
    args = parser.parse_args()
    inbox = Path(args.inbox_dir).resolve()
    if args.cmd == "list":
        rows = list_records(inbox, pending_only=True)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        print(f"[needs-hr] pending {len(rows)} 条", file=sys.stderr)
        return 0
    if args.cmd == "list-pipeline":
        rows = list_pipeline(inbox, pending_only=True)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        print(f"[needs-pipeline] pending {len(rows)} 条", file=sys.stderr)
        return 0
    if args.cmd == "resolve":
        ok = mark_resolved(inbox, args.id, args.resolution)
        if not ok:
            print(f"找不到 id={args.id}", file=sys.stderr)
            return 1
        print(f"已标记 resolved: {args.id}")
        return 0
    if args.cmd == "pipeline-done":
        n = mark_pipeline_done(inbox, args.stem)
        print(f"pipeline-done {args.stem}: {n} 条")
        return 0 if n else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
