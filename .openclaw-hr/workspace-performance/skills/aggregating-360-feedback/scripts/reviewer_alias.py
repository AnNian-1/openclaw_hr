#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""360 评估人代号：领导N / 同事N / 下属N / 自评。

测试时 Agent 会自己填反馈表。真实姓名既不能写进 DOCX/JSON，
也不能出现在聚合结果和看板。文件名约定：
  manager.json → 领导1
  peer-01.json → 同事1
  report-02.json → 下属2
  self.json → 自评
同视角多人在表内直接写同事1、同事2（或下属1、下属2）；
解析时若已是合法代号，按该编号落盘，不再按姓名重排。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SKIP_JSON_NAMES = {"aggregated-data.json"}

ALIAS_RE = re.compile(r"^(领导|同事|下属)\d+$|^自评$")

_STEM_ALIAS = {
    "manager": "领导1",
    "self": "自评",
}

_RELATION_PREFIX = {
    "peer": "同事",
    "report": "下属",
}


def alias_from_json_name(filename: str) -> str | None:
    stem = Path(filename).stem
    if stem in _STEM_ALIAS:
        return _STEM_ALIAS[stem]
    m = re.fullmatch(r"peer-(\d+)", stem)
    if m:
        return f"同事{int(m.group(1))}"
    m = re.fullmatch(r"report-(\d+)", stem)
    if m:
        return f"下属{int(m.group(1))}"
    return None


def is_role_alias(value: str | None) -> bool:
    return bool(value and ALIAS_RE.fullmatch(str(value).strip()))


def looks_like_person_name(value: str | None) -> bool:
    if not value or is_role_alias(value):
        return False
    head = re.split(r"[（(]", str(value).strip(), maxsplit=1)[0].strip()
    if re.fullmatch(r"员工\d+", head):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", head))


def parse_role_number(alias: str | None, prefix: str) -> int | None:
    m = re.fullmatch(rf"{re.escape(prefix)}(\d+)", str(alias or "").strip())
    if not m:
        return None
    n = int(m.group(1))
    return n if n >= 1 else None


def assign_numbered_json_names(items: list[dict], relation: str, prefix: str) -> None:
    """peer/report：表内已写 同事N/下属N 则沿用编号；其余按别名+源文件名补号。"""
    taken: dict[int, dict] = {}
    unlabeled: list[dict] = []
    for item in items:
        n = parse_role_number(item.get("reviewer_alias"), prefix)
        if n is None:
            unlabeled.append(item)
            continue
        if n in taken:
            a = taken[n].get("_source_docx") or "?"
            b = item.get("_source_docx") or "?"
            raise ValueError(f"{prefix}{n} 重复：{a} 与 {b}")
        taken[n] = item
    unlabeled.sort(
        key=lambda r: (
            (r.get("reviewer_alias") or ""),
            (r.get("_source_docx") or ""),
        )
    )
    n = 1
    for item in unlabeled:
        while n in taken:
            n += 1
        taken[n] = item
        n += 1
    for num, item in taken.items():
        item["_json_name"] = f"{relation}-{num:02d}.json"


def assign_alias_from_json_name(row: dict, json_name: str) -> str:
    alias = alias_from_json_name(json_name)
    if not alias:
        raise ValueError(
            f"{json_name}: 文件名须为 manager.json / peer-NN.json / "
            "report-NN.json / self.json，才能得到 领导N/同事N/下属N/自评"
        )
    row["reviewer_alias"] = alias
    return alias


def anonymize_feedback_dir(json_dir: str | Path) -> list[tuple[str, str, str]]:
    """把目录内单份反馈的 reviewer_alias 改成角色代号。返回 (file, old, new)。"""
    root = Path(json_dir)
    changed: list[tuple[str, str, str]] = []
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_") or path.name.startswith("aggregated-"):
            continue
        if path.name in SKIP_JSON_NAMES:
            continue
        expected = alias_from_json_name(path.name)
        if not expected:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "reviewer_relation" not in data:
            continue
        old = str(data.get("reviewer_alias") or "")
        if old == expected:
            continue
        data["reviewer_alias"] = expected
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed.append((path.name, old, expected))
    return changed
