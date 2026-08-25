#!/usr/bin/env python3
"""
refresh-gate-stubs.py —— 按审批门重跑对应 stub shell，刷新落盘后再拼 prompt

供 query / emit-approval-verbatim 在 build-approval-prompt 之前调用，
保证 HR 看到的审批正文基于「刚刷新」的 stub，而不是陈旧盘面。

用法：
  refresh-gate-stubs.py <contract|account> <pinyin>

环境：
  STATE           —— stub-state 根目录（必填）
  STUB_STATE_DIR  —— 可选；候选人目录，缺省用 STATE/<pinyin>

门 → shell（halt 中刷新保持「待审批」，不假装已批过）：
  contract → contract.sh（status=待审批）
  account  → it-account.sh（待审批）+ device.sh + training.sh
"""
import json
import os
import subprocess
import sys


def _scripts_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _identity(state_dir, pinyin):
    """从 workflow / 已有 stub 拼 shell 参数。"""
    base = os.path.join(state_dir, pinyin)
    wf = _load_json(os.path.join(base, "workflow.json"))
    contract = _load_json(os.path.join(base, "contract.json"))
    account = _load_json(os.path.join(base, "account.json"))
    name = wf.get("candidate") or contract.get("candidate") or account.get("candidate") or pinyin
    role = wf.get("role") or contract.get("role") or "岗位"
    salary = wf.get("salary") or contract.get("salary") or "面议"
    return name, role, salary


def refresh(gate, pinyin, state_dir):
    scripts = _scripts_dir()
    stub_dir = os.environ.get("STUB_STATE_DIR")
    if not stub_dir or os.path.basename(stub_dir.rstrip("/")) != pinyin:
        stub_dir = os.path.join(state_dir, pinyin)
    env = {
        **os.environ,
        "STATE": state_dir,
        "STUB_STATE_DIR": stub_dir,
    }
    name, role, salary = _identity(state_dir, pinyin)
    runs = []
    if gate == "contract":
        runs.append(["bash", os.path.join(scripts, "contract.sh"),
                     name, role, salary, "待审批"])
    elif gate == "account":
        runs.append(["bash", os.path.join(scripts, "it-account.sh"),
                     name, pinyin, "待审批"])
        runs.append(["bash", os.path.join(scripts, "device.sh"), name])
        runs.append(["bash", os.path.join(scripts, "training.sh"), name])
    else:
        sys.stderr.write(f"[refresh-gate-stubs] 未知 gate: {gate}\n")
        return 1

    for cmd in runs:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        if proc.stdout.strip():
            sys.stderr.write(proc.stdout if proc.stdout.endswith("\n")
                             else proc.stdout + "\n")
        if proc.returncode != 0:
            sys.stderr.write(
                f"[refresh-gate-stubs] 失败：{' '.join(cmd)}\n"
                f"{proc.stderr.strip()}\n"
            )
            return proc.returncode or 1
    sys.stderr.write(f"[refresh-gate-stubs] {gate}/{pinyin} 落盘已刷新\n")
    return 0


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: refresh-gate-stubs.py <contract|account> <pinyin>\n")
        sys.exit(1)
    gate, pinyin = sys.argv[1], sys.argv[2]
    state_dir = os.environ.get("STATE")
    if not state_dir:
        sys.stderr.write("[refresh-gate-stubs] 缺少 $STATE\n")
        sys.exit(2)
    sys.exit(refresh(gate, pinyin, state_dir))


if __name__ == "__main__":
    main()
