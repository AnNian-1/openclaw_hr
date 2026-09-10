#!/usr/bin/env python3
"""
record-pending-approval.py —— halt 时把 stub 当前快照落盘到 pending-approvals/

由 hr-onboarding.lobster 的两个 approval: true 步骤调用（start→halt 那一瞬）：
    run: python3 $STUB/record-pending-approval.py contract <pinyin>
    run: python3 $STUB/record-pending-approval.py account  <pinyin>

负责把"halt 时这一刻"的 stub 快照落盘到：
    $WORKSPACE/pending-approvals/<pinyin>-<gate>.json

快照范围：
  · contract 门：contract.json 单文件
  · account 门：account + device + training 三份（与 build-approval-prompt 保鲜范围一致）

文件里存：
  - halted_at 这一次 halt 的上海时区时间（+08:00）
  - pre_halt_snapshot stub halt 那一刻的内容（供 querying-onboarding-status diff）
  - stub_prepared_at / stub_updated_at_pre_halt（多文件时取最早 prepared / 最晚 updated）
"""
import datetime as dt
import json
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _read_state(path):
    if not os.path.exists(path):
        sys.stderr.write(
            f"[record-pending-approval] 缺少状态文件：{path}\n"
            "——通常因为尚未快照 HCM，或 stub 被人手动删了。"
            "请重新执行 run-onboarding.sh start ... 让 prep 从 HCM 重写 stub-state。\n"
        )
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _snapshot_for_gate(state_dir, pinyin, gate):
    base = os.path.join(state_dir, pinyin)
    if gate == "contract":
        return _read_state(os.path.join(base, "contract.json"))
    # account 门：三份并行准备物料一起落盘
    return {
        "account": _read_state(os.path.join(base, "account.json")),
        "device": _read_state(os.path.join(base, "device.json")),
        "training": _read_state(os.path.join(base, "training.json")),
    }


def _time_bounds(snapshot, gate):
    """返回 (prepared_at, updated_at)。account 门取三份里最早 prepared / 最晚 updated。"""
    if gate == "contract":
        return snapshot.get("prepared_at"), snapshot.get("updated_at")
    prepareds, updateds = [], []
    for key in ("account", "device", "training"):
        part = snapshot.get(key) or {}
        if part.get("prepared_at"):
            prepareds.append(part["prepared_at"])
        if part.get("updated_at"):
            updateds.append(part["updated_at"])
    return (
        min(prepareds) if prepareds else None,
        max(updateds) if updateds else None,
    )


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: record-pending-approval.py <gate> <pinyin>\n")
        sys.exit(1)
    gate, pinyin = sys.argv[1], sys.argv[2]
    if gate not in ("contract", "account"):
        sys.stderr.write(f"[record-pending-approval] 未知 gate: {gate}\n")
        sys.exit(1)

    state_dir = os.environ.get("STATE")
    workspace = os.environ.get("WORKSPACE")
    if not (state_dir and workspace):
        sys.stderr.write(
            "[record-pending-approval] 缺少环境变量：$STATE / $WORKSPACE\n"
        )
        sys.exit(2)

    pre_halt_snapshot = _snapshot_for_gate(state_dir, pinyin, gate)
    prepared_at, updated_at = _time_bounds(pre_halt_snapshot, gate)

    pending_dir = os.path.join(workspace, "pending-approvals")
    pathlib.Path(pending_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(pending_dir, f"{pinyin}-{gate}.json")

    record = {
        "candidate_pinyin": pinyin,
        "gate": gate,
        "halted_at": dt.datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "stub_prepared_at": prepared_at,
        "stub_updated_at_pre_halt": updated_at,
        "resume_token": None,  # lobster halt 后由 update-workflow.py attach 回填
        "pre_halt_snapshot": pre_halt_snapshot,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"[record-pending-approval] {gate} 落盘到 {out_path}")
    print(json.dumps({"recorded": out_path, "halted_at": record["halted_at"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
