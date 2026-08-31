#!/usr/bin/env python3
"""
update-workflow.py —— 在 stub-state/<pinyin>/workflow.json 追加流程扭转事件

由 hr-onboarding.lobster 各节点调用，把候选人入职流程的状态机落盘到
候选人目录下（与 contract.json / account.json 平级）。

用法：
  update-workflow.py init  <pinyin> <name> <role> <salary>
      —— start 时创建/重置 workflow.json（status=started）

  update-workflow.py event <pinyin> <step> <action> [note]
      —— 追加一条事件，并刷新 current_step / status / halted_at / completed_at

  update-workflow.py attach <pinyin> <lobster_json_file>
      —— lobster 返回之后由 run-onboarding.sh 调用：
         needs_approval → 写入 approval_id + resume_token
         ok / cancelled  → 清空这两个字段

  step ∈ {prep, contract_gate, account_gate, buddy, complete}
  action ∈ {started, completed, halted, approved, rejected, waiting}

环境变量：
  STUB_STATE_DIR —— 优先；指向 stub-state/<pinyin>/
  STATE          —— 回退；拼 STATE/<pinyin>/

workflow.json 结构（full-trail）：
  {
    "candidate", "pinyin", "role", "salary",
    "status": "started|halted|completed|cancelled|waiting_departments",
    "current_step": "prep|contract_gate|account_gate|buddy|complete",
    "started_at", "updated_at", "halted_at", "completed_at",
    "approval_id", "resume_token",   # lobster halt 后由 attach 回写
    "events": [ {"at", "step", "action", "note"}, ... ]
  }
"""
import base64
import datetime as dt
import glob
import json
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

VALID_STEPS = ("prep", "contract_gate", "account_gate", "buddy", "complete")
VALID_ACTIONS = ("started", "completed", "halted", "approved", "rejected", "waiting")
# 只有这两道 HiTL 审批门才需要 approval_id / resume_token；
# 其它节点（prep/buddy/complete）永不查 ~/.lobster/state。
APPROVAL_GATES = ("contract_gate", "account_gate")
LOBSTER_STATE_DIR = os.path.join(os.path.expanduser("~"), ".lobster", "state")


def _now():
    """落盘用上海时区，形如 2026-07-17T21:06:00+08:00。"""
    return dt.datetime.now(SHANGHAI).isoformat(timespec="seconds")


def _encode_resume_token(state_key):
    """按 lobster 约定把 stateKey 编成 resumeToken（标准 base64，去 padding）。"""
    payload = {
        "protocolVersion": 1,
        "v": 1,
        "kind": "workflow-file",
        "stateKey": state_key,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii").rstrip("=")


def lookup_lobster_approval(pinyin, step):
    """从 ~/.lobster/state/ 兜底查找当前门的 approval_id + resume_token。

    何时调用（重要）：
      · 仅当候选人 status=halted 且 current_step ∈ {contract_gate, account_gate}
      · prep / buddy / complete 绝不调用——这两道门以外 lobster 不会留有效 resume

    匹配规则：
      1. workflow_resume_*.json 的 args.pinyin == pinyin
      2. approvalStepId == step（卡在哪道门）
      3. 该门尚未 approved（避免命中已走过的旧快照）
      4. 按 createdAt 取最新一条
      5. 再扫 approval_*.json 反查 approval_id（stateKey 对齐）

    返回 dict 或 None：
      {approval_id, resume_token, state_key, created_at, source: \"lobster\"}
    """
    if step not in APPROVAL_GATES:
        return None
    if not os.path.isdir(LOBSTER_STATE_DIR):
        return None

    candidates = []
    for path in glob.glob(os.path.join(LOBSTER_STATE_DIR, "workflow_resume_*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        args = d.get("args") or {}
        if args.get("pinyin") != pinyin:
            continue
        if d.get("approvalStepId") != step:
            continue
        step_info = (d.get("steps") or {}).get(step) or {}
        if step_info.get("approved") is True:
            continue  # 已批准的旧快照，跳过
        state_key = os.path.splitext(os.path.basename(path))[0]
        candidates.append((d.get("createdAt") or "", state_key, d))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    created_at, state_key, _ = candidates[0]

    approval_id = None
    for ap in glob.glob(os.path.join(LOBSTER_STATE_DIR, "approval_*.json")):
        try:
            with open(ap, encoding="utf-8") as f:
                ad = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if ad.get("stateKey") == state_key:
            approval_id = os.path.basename(ap)[len("approval_"):-len(".json")]
            break

    return {
        "approval_id": approval_id,
        "resume_token": _encode_resume_token(state_key),
        "state_key": state_key,
        "created_at": created_at,
        "source": "lobster",
    }


def ensure_approval_tokens(pinyin, data, persist=True):
    """若 workflow 卡在两道门且缺 token，则从 ~/.lobster 兜底补齐。

    返回 (data, filled: bool, source: str|None)
    """
    if not data:
        return data, False, None
    if data.get("status") != "halted":
        return data, False, None
    step = data.get("current_step")
    if step not in APPROVAL_GATES:
        return data, False, None
    if data.get("approval_id") and data.get("resume_token"):
        return data, False, "workflow.json"

    hit = lookup_lobster_approval(pinyin, step)
    if not hit:
        return data, False, None

    data["approval_id"] = hit.get("approval_id")
    data["resume_token"] = hit.get("resume_token")
    data["updated_at"] = _now()
    if persist:
        _save(_path(pinyin), data)
    return data, True, "lobster"


def _state_dir(pinyin):
    stub = os.environ.get("STUB_STATE_DIR")
    # 只有目录名恰好是本候选人拼音时才用 STUB_STATE_DIR，
    # 避免 export 残留导致 lookup/query 读到别人的目录。
    if stub and os.path.basename(stub.rstrip("/")) == pinyin:
        return stub
    state = os.environ.get("STATE")
    if state:
        return os.path.join(state, pinyin)
    if stub:
        # 兼容：没 STATE 时退回 STUB_STATE_DIR（单候选人场景）
        return stub
    sys.stderr.write(
        "[update-workflow] 缺少 $STUB_STATE_DIR 或 $STATE 环境变量。\n"
    )
    sys.exit(2)


def _workspace_root():
    ws = os.environ.get("WORKSPACE")
    if ws:
        return os.path.abspath(ws)
    state = os.environ.get("STATE")
    if state:
        return os.path.dirname(os.path.abspath(state))
    stub = os.environ.get("STUB_STATE_DIR")
    if stub:
        return os.path.dirname(os.path.dirname(os.path.abspath(stub)))
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def _clear_pending_approvals(pinyin):
    pending = os.path.join(_workspace_root(), "pending-approvals")
    removed = []
    for gate in ("contract", "account"):
        path = os.path.join(pending, f"{pinyin}-{gate}.json")
        try:
            os.remove(path)
            removed.append(os.path.basename(path))
        except FileNotFoundError:
            pass
    if removed:
        print(
            f"[update-workflow] 已清理 pending-approvals: {', '.join(removed)}",
            file=sys.stderr,
        )
    return removed


def cmd_cleanup_stale_pending():
    """cancelled/completed 或无 workflow 的 pending 快照删掉；halted 保留。"""
    ws = _workspace_root()
    pending = os.path.join(ws, "pending-approvals")
    state_root = os.path.join(ws, "stub-state")
    removed = []
    if os.path.isdir(pending):
        for name in sorted(os.listdir(pending)):
            if not name.endswith(".json"):
                continue
            pinyin = None
            for gate in ("contract", "account"):
                suf = f"-{gate}.json"
                if name.endswith(suf):
                    pinyin = name[: -len(suf)]
                    break
            if not pinyin:
                continue
            wf = _load(os.path.join(state_root, pinyin, "workflow.json"))
            stale = wf is None or wf.get("status") in ("cancelled", "completed")
            if stale:
                os.remove(os.path.join(pending, name))
                removed.append(name)
                print(f"[update-workflow] 清理陈旧 pending: {name}", file=sys.stderr)
    print(json.dumps({"removed": removed}, ensure_ascii=False))


def _path(pinyin):
    return os.path.join(_state_dir(pinyin), "workflow.json")


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    pathlib.Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pinyin_from_resume_token(token):
    """从 resumeToken 解码 stateKey → 读 ~/.lobster/state/<key>.json → args.pinyin"""
    if not token:
        return None
    try:
        pad = "=" * (-len(token) % 4)
        payload = json.loads(base64.b64decode(token + pad))
        state_key = payload.get("stateKey")
        if not state_key:
            return None
        state_path = os.path.join(os.path.expanduser("~/.lobster/state"), f"{state_key}.json")
        if not os.path.exists(state_path):
            return None
        with open(state_path, encoding="utf-8") as f:
            st = json.load(f)
        return (st.get("args") or {}).get("pinyin")
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def cmd_init(pinyin, name, role, salary):
    path = _path(pinyin)
    now = _now()
    data = {
        "candidate": name,
        "pinyin": pinyin,
        "role": role,
        "salary": salary,
        "status": "started",
        "current_step": "prep",
        "started_at": now,
        "updated_at": now,
        "halted_at": None,
        "completed_at": None,
        "approval_id": None,
        "resume_token": None,
        "events": [
            {
                "at": now,
                "step": "prep",
                "action": "started",
                "note": f"入职流程启动：{name}（{role}, {salary}）",
            }
        ],
    }
    _save(path, data)
    print(f"[update-workflow] init → {path}", file=sys.stderr)
    print(json.dumps({"path": path, "status": "started"}, ensure_ascii=False))


def cmd_event(pinyin, step, action, note=""):
    if step not in VALID_STEPS:
        sys.stderr.write(f"[update-workflow] 未知 step: {step}\n")
        sys.exit(1)
    if action not in VALID_ACTIONS:
        sys.stderr.write(f"[update-workflow] 未知 action: {action}\n")
        sys.exit(1)

    path = _path(pinyin)
    data = _load(path)
    if data is None:
        now = _now()
        data = {
            "candidate": pinyin,
            "pinyin": pinyin,
            "role": "",
            "salary": "",
            "status": "started",
            "current_step": step,
            "started_at": now,
            "updated_at": now,
            "halted_at": None,
            "completed_at": None,
            "approval_id": None,
            "resume_token": None,
            "events": [],
        }

    now = _now()
    data["events"].append({
        "at": now,
        "step": step,
        "action": action,
        "note": note or "",
    })
    data["current_step"] = step
    data["updated_at"] = now

    if action == "halted":
        data["status"] = "halted"
        data["halted_at"] = now
        data["completed_at"] = None
        # approval_id / resume_token 此时还没有——等 lobster 返回后由 attach 回写
    elif action == "waiting":
        data["status"] = "waiting_departments"
        data["halted_at"] = None
    elif action == "rejected":
        data["status"] = "cancelled"
        data["halted_at"] = None
        data["approval_id"] = None
        data["resume_token"] = None
    elif action == "completed" and step == "complete":
        data["status"] = "completed"
        data["halted_at"] = None
        data["completed_at"] = now
        data["approval_id"] = None
        data["resume_token"] = None
    elif action in ("approved", "completed", "started"):
        if data.get("status") == "halted":
            data["status"] = "started"
            data["halted_at"] = None
        # 走出旧门时先清空旧 token，下一门 halt 后再由 attach 写入新的
        data["approval_id"] = None
        data["resume_token"] = None

    _save(path, data)
    if data.get("status") in ("cancelled", "completed"):
        _clear_pending_approvals(pinyin)
    print(f"[update-workflow] {step}/{action} → {path} (status={data['status']})", file=sys.stderr)
    print(json.dumps({
        "path": path,
        "status": data["status"],
        "current_step": data["current_step"],
        "halted_at": data.get("halted_at"),
    }, ensure_ascii=False))


def cmd_attach(pinyin, lobster_json_path):
    """lobster 返回后回写 approval_id / resume_token。"""
    if not os.path.exists(lobster_json_path):
        sys.stderr.write(f"[update-workflow] 找不到 lobster 输出：{lobster_json_path}\n")
        sys.exit(2)
    with open(lobster_json_path, encoding="utf-8") as f:
        raw = f.read().strip()
    # lobster 默认输出整段 JSON（可能带缩进）；优先整段解析
    lobster = None
    try:
        lobster = json.loads(raw)
    except json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    lobster = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    if lobster is None:
        sys.stderr.write("[update-workflow] attach：无法解析 lobster JSON 输出\n")
        sys.exit(2)

    path = _path(pinyin)
    data = _load(path)
    if data is None:
        sys.stderr.write(f"[update-workflow] attach：找不到 {path}，跳过\n")
        sys.exit(0)

    status = lobster.get("status")
    now = _now()
    data["updated_at"] = now

    if status == "needs_approval":
        ra = lobster.get("requiresApproval") or {}
        data["approval_id"] = ra.get("approvalId")
        data["resume_token"] = ra.get("resumeToken")
        if data.get("status") != "halted":
            data["status"] = "halted"
            data["halted_at"] = data.get("halted_at") or now
        # 兜底：stdout 里缺字段时，仅两道门才查 ~/.lobster/state
        if (not data.get("approval_id") or not data.get("resume_token")) \
                and data.get("current_step") in APPROVAL_GATES:
            data, filled, src = ensure_approval_tokens(pinyin, data, persist=False)
            if filled:
                print(f"[update-workflow] attach 兜底自 {src}", file=sys.stderr)
        print(
            f"[update-workflow] attach approval_id={data['approval_id']} → {path}",
            file=sys.stderr,
        )
    else:
        data["approval_id"] = None
        data["resume_token"] = None
        if status in ("cancelled", "rejected"):
            data["status"] = "cancelled"
            data["halted_at"] = None
            data["events"].append({
                "at": now,
                "step": data.get("current_step") or "unknown",
                "action": "rejected",
                "note": "审批已拒绝，工作流取消",
            })
            print(f"[update-workflow] attach cancelled → {path}", file=sys.stderr)
        else:
            print(f"[update-workflow] attach cleared tokens (status={status}) → {path}",
                  file=sys.stderr)

    _save(path, data)
    if data.get("status") == "cancelled":
        _clear_pending_approvals(pinyin)
    print(json.dumps({
        "path": path,
        "status": data.get("status"),
        "approval_id": data.get("approval_id"),
        "has_resume_token": bool(data.get("resume_token")),
    }, ensure_ascii=False))


def cmd_lookup(pinyin, step=None):
    """手动 / 查询 Skill 调用：按 pinyin(+step) 从 ~/.lobster 查当前门凭证。"""
    if step is None:
        # 没传 step：读 workflow.json 的 current_step；没有则两道门都试
        path = _path(pinyin)
        data = _load(path)
        if data and data.get("current_step") in APPROVAL_GATES:
            step = data["current_step"]
        else:
            for g in APPROVAL_GATES:
                hit = lookup_lobster_approval(pinyin, g)
                if hit:
                    print(json.dumps({"pinyin": pinyin, "step": g, **hit},
                                     ensure_ascii=False))
                    return
            print(json.dumps({"pinyin": pinyin, "found": False,
                              "reason": "两道门在 ~/.lobster/state 均无有效 halt 快照"},
                             ensure_ascii=False))
            sys.exit(4)

    if step not in APPROVAL_GATES:
        sys.stderr.write(
            f"[update-workflow] lookup 只支持两道审批门 {APPROVAL_GATES}，收到：{step}\n"
        )
        sys.exit(1)
    hit = lookup_lobster_approval(pinyin, step)
    if not hit:
        print(json.dumps({
            "pinyin": pinyin, "step": step, "found": False,
            "reason": f"~/.lobster/state 无 pinyin={pinyin} 且 approvalStepId={step} 的有效快照",
        }, ensure_ascii=False))
        sys.exit(4)
    print(json.dumps({"pinyin": pinyin, "step": step, "found": True, **hit},
                     ensure_ascii=False))


def cmd_pinyin_from_token(token):
    pinyin = pinyin_from_resume_token(token)
    if not pinyin:
        sys.exit(1)
    print(pinyin)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(
            "usage: update-workflow.py init   <pinyin> <name> <role> <salary>\n"
            "       update-workflow.py event  <pinyin> <step> <action> [note]\n"
            "       update-workflow.py attach <pinyin> <lobster_json_file>\n"
            "       update-workflow.py lookup <pinyin> [contract_gate|account_gate]\n"
            "       update-workflow.py cleanup-stale-pending\n"
            "       update-workflow.py pinyin-from-token <resumeToken>\n"
        )
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "init":
        if len(sys.argv) < 6:
            sys.stderr.write("usage: update-workflow.py init <pinyin> <name> <role> <salary>\n")
            sys.exit(1)
        cmd_init(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "event":
        if len(sys.argv) < 5:
            sys.stderr.write("usage: update-workflow.py event <pinyin> <step> <action> [note]\n")
            sys.exit(1)
        note = sys.argv[5] if len(sys.argv) > 5 else ""
        cmd_event(sys.argv[2], sys.argv[3], sys.argv[4], note)
    elif cmd == "attach":
        if len(sys.argv) < 4:
            sys.stderr.write("usage: update-workflow.py attach <pinyin> <lobster_json_file>\n")
            sys.exit(1)
        cmd_attach(sys.argv[2], sys.argv[3])
    elif cmd == "lookup":
        if len(sys.argv) < 3:
            sys.stderr.write(
                "usage: update-workflow.py lookup <pinyin> [contract_gate|account_gate]\n"
            )
            sys.exit(1)
        step = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_lookup(sys.argv[2], step)
    elif cmd == "pinyin-from-token":
        if len(sys.argv) < 3:
            sys.stderr.write("usage: update-workflow.py pinyin-from-token <resumeToken>\n")
            sys.exit(1)
        cmd_pinyin_from_token(sys.argv[2])
    elif cmd == "cleanup-stale-pending":
        cmd_cleanup_stale_pending()
    else:
        sys.stderr.write(f"[update-workflow] 未知命令: {cmd}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
