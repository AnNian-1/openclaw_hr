#!/usr/bin/env python3
"""
emit-approval-verbatim.py —— 输出「禁止改写」标记块给 Agent

标记块给 Agent 解析用；SKILL 要求：交给用户时**去掉标记行**，只原样保留
---PROMPT--- / ---RESUME_TOKEN--- 之间的正文，并用简洁 Markdown 排版。

用法：emit-approval-verbatim.py <pinyin>
全部写到 stderr，不污染 lobster / query 的 JSON stdout。

注意：门对应 shell 刷新必须在 VERBATIM 标记块之外执行，
否则 refresh 日志会污染 ---PROMPT--- 正文。
"""
import json
import os
import subprocess
import sys

APPROVAL_GATES = {
    "contract_gate": "contract",
    "account_gate": "account",
}

STEP_CN = {
    "prep": "入职准备",
    "contract_gate": "合同审批门",
    "account_gate": "账号权限审批门",
    "buddy": "Buddy 匹配",
    "complete": "归档完成",
}

STATUS_CN = {
    "started": "进行中",
    "halted": "待审批（已暂停）",
    "completed": "已完成",
    "cancelled": "已取消",
}


def _out(msg=""):
    sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")


def _state_dir(pinyin):
    stub = os.environ.get("STUB_STATE_DIR")
    if stub and os.path.basename(stub.rstrip("/")) == pinyin:
        return stub
    state = os.environ.get("STATE")
    if state:
        return os.path.join(state, pinyin)
    sys.stderr.write("[emit-approval-verbatim] 缺少 $STATE 或 $STUB_STATE_DIR\n")
    sys.exit(2)


def _scripts_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _state_root(pinyin):
    state_root = os.environ.get("STATE")
    if not state_root:
        stub = os.environ.get("STUB_STATE_DIR") or _state_dir(pinyin)
        state_root = os.path.dirname(stub.rstrip("/"))
    return state_root


def _refresh_gate(gate, pinyin):
    """在标记块之外刷新落盘；日志可出现在 STATUS 之前。"""
    env = {
        **os.environ,
        "STATE": _state_root(pinyin),
        "STUB_STATE_DIR": _state_dir(pinyin),
    }
    refresh = os.path.join(_scripts_dir(), "refresh-gate-stubs.py")
    if not os.path.isfile(refresh):
        _out(f"[emit-approval-verbatim] 跳过刷新：无 {refresh}")
        return
    subprocess.run(["python3", refresh, gate, pinyin], env=env, timeout=60)


def _build_prompt(gate, pinyin):
    """只读当前 stub 拼 prompt（调用方须已 refresh）。"""
    env = {**os.environ, "STATE": _state_root(pinyin)}
    proc = subprocess.run(
        ["python3", os.path.join(_scripts_dir(), "build-approval-prompt.py"), gate, pinyin],
        env=env, capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        return None, proc.stderr.strip()
    try:
        return json.loads(proc.stdout.strip()), None
    except json.JSONDecodeError:
        return None, "build-approval-prompt 输出非 JSON"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: emit-approval-verbatim.py <pinyin>\n")
        sys.exit(1)
    pinyin = sys.argv[1]
    path = os.path.join(_state_dir(pinyin), "workflow.json")
    if not os.path.exists(path):
        sys.stderr.write(f"[emit-approval-verbatim] 无 workflow.json：{path}\n")
        sys.exit(3)
    with open(path, encoding="utf-8") as f:
        wf = json.load(f)

    name = wf.get("candidate") or pinyin
    status = wf.get("status")
    step = wf.get("current_step")
    status_cn = STATUS_CN.get(status, status)
    step_cn = STEP_CN.get(step, step)
    gate = APPROVAL_GATES.get(step)

    # 刷新必须在 VERBATIM 之前，避免日志落入 ---PROMPT---
    if status == "halted" and gate:
        _refresh_gate(gate, pinyin)

    _out("===== AGENT_VERBATIM_BEGIN =====")
    _out("---STATUS---")
    _out(f"候选人：{name}（{pinyin}）")
    _out(f"流程状态：{status_cn}")
    _out(f"当前节点：{step_cn}（{step}）")
    if status == "halted" and wf.get("halted_at"):
        _out(f"暂停于：{wf.get('halted_at')}")
    if wf.get("approval_id"):
        _out(f"approval_id：{wf.get('approval_id')}")
    _out("---END_STATUS---")

    _out("---PROMPT---")
    if status == "halted" and gate:
        payload, err = _build_prompt(gate, pinyin)
        if payload and payload.get("prompt"):
            _out(payload["prompt"])
        else:
            _out(f"[emit-approval-verbatim] 无法渲染 prompt：{err}")
    else:
        _out("（当前不在审批门，无待审正文）")
    _out("---END_PROMPT---")

    _out("---RESUME_TOKEN---")
    tok = wf.get("resume_token")
    _out(tok if tok else "（无 resume_token）")
    _out("---END_RESUME_TOKEN---")
    _out("===== AGENT_VERBATIM_END =====")
    _out(
        "[display-hint] 对用户展示时：隐藏所有 ---XXX--- / ===== 标记行；"
        "STATUS 做成 2～4 条短列表；PROMPT 原样放在引用块；"
        "RESUME_TOKEN 放进 markdown 代码块便于复制；禁止改写 PROMPT 正文。"
    )


if __name__ == "__main__":
    main()
