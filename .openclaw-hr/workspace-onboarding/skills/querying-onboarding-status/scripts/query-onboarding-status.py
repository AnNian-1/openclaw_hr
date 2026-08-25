#!/usr/bin/env python3
"""
query-onboarding-status.py —— 入职审批状态查询

真源优先级：
  1. stub-state/<pinyin>/workflow.json（扭转状态机，含停留天数）
  2. pending-approvals/<pinyin>-<gate>.json（halt 时 stub 快照，做 stub_changed_after_halt）

按候选人全名查：
  · 当前状态 / 当前节点 / halt 停留几天
  · 完整事件轨迹
  · stub 在 halt 之后是否被改过 + 当前 prompt 投影

输出到 stdout：完整 JSON 给程序读
输出到 stderr：人话摘要给 HR 看
退出码：0 = 查到；3 = 有 stub 无 workflow（旧数据）；4 = 未启动
"""
import datetime as dt
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _parse_iso(s):
    """解析落盘 ISO 时间：支持 +08:00（上海）与旧数据 Z（UTC）。"""
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc
            )
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _humanize_age(iso):
    t = _parse_iso(iso)
    if not t:
        return "时间未知"
    now = dt.datetime.now(SHANGHAI)
    if t.tzinfo is None:
        t = t.replace(tzinfo=SHANGHAI)
    delta = now - t
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "刚刚"
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def _shallow_diff(pre, cur):
    """浅层字段 diff：只比第一层。忽略时间戳（query 刷新落盘会改它们）。"""
    skip = {"prepared_at", "updated_at"}
    diffs = []
    keys = sorted(set(pre.keys()) | set(cur.keys()))
    for k in keys:
        if k in skip:
            continue
        p = pre.get(k)
        c = cur.get(k)
        if p != c:
            diffs.append({"field": k, "pre_halt": p, "current": c})
    return diffs


def _default_running_scripts_dir():
    """相对本 skill 定位 running-onboarding-workflow/scripts（不依赖 $STUB）。"""
    skill_scripts_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(skill_scripts_dir)
    skills_root = os.path.dirname(skill_dir)
    return os.path.join(skills_root, "running-onboarding-workflow", "scripts")


def _resolve_stub_scripts_dir():
    """优先用带 refresh-gate-stubs.py 的目录；$STUB 无效时回退到本仓库 sibling。"""
    candidates = []
    env_stub = os.environ.get("STUB")
    if env_stub:
        candidates.append(env_stub)
    candidates.append(_default_running_scripts_dir())
    for d in candidates:
        if d and os.path.isfile(os.path.join(d, "refresh-gate-stubs.py")):
            return d
    sys.stderr.write(
        "[query-onboarding-status] 警告：找不到 refresh-gate-stubs.py，"
        "查询将无法重跑门对应 shell 刷新落盘。"
        f" 已试路径：{candidates}\n"
    )
    return candidates[0] if candidates else ""


def _resolve_pinyin(workspace, name, pinyin):
    """拼音解析：显式参数 > 内置表 > 扫 stub-state/*/workflow.json 的 candidate。"""
    if pinyin:
        return pinyin
    pin_map = {
        "张磊": "zhanglei", "陈思远": "chensiyuan", "王芳菲": "wangfangfei",
        "李娜": "lina", "刘洋": "liuyang", "李四": "lisi", "王五": "wangwu",
        "周敏": "zhoumin", "陈静": "chenjing", "毛毛豆": "maomaodou",
    }
    if name in pin_map:
        return pin_map[name]
    stub_root = os.path.join(workspace, "stub-state")
    if not os.path.isdir(stub_root):
        return None
    matches = []
    for entry in sorted(os.listdir(stub_root)):
        base = os.path.join(stub_root, entry)
        if not os.path.isdir(base):
            continue
        wf = _load_json(os.path.join(base, "workflow.json"))
        if wf.get("candidate") == name:
            matches.append(entry)
            continue
        for stub_name in ("contract.json", "account.json"):
            stub = _load_json(os.path.join(base, stub_name))
            if stub.get("candidate") == name:
                matches.append(entry)
                break
    # 去重并保持顺序
    dedup = []
    for m in matches:
        if m not in dedup:
            dedup.append(m)
    if len(dedup) == 1:
        sys.stderr.write(
            f"[query-onboarding-status] 拼音未手传，已从 stub-state/{dedup[0]}/ 匹配到「{name}」\n"
        )
        return dedup[0]
    if len(dedup) > 1:
        sys.stderr.write(
            f"[query-onboarding-status] 「{name}」匹配到多个目录 {dedup}，请手传拼音\n"
        )
        return None
    return None


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _refresh_gate_stubs(stub_scripts_dir, gate, state_dir, pinyin):
    """按门重跑对应 shell，刷新 stub 后再拼 prompt。"""
    script = os.path.join(stub_scripts_dir, "refresh-gate-stubs.py")
    if not os.path.isfile(script):
        sys.stderr.write(
            f"[query-onboarding-status] 跳过刷新：无 {script}\n"
        )
        return False
    try:
        proc = subprocess.run(
            ["python3", script, gate, pinyin],
            env={
                **os.environ,
                "STATE": state_dir,
                "STUB_STATE_DIR": os.path.join(state_dir, pinyin),
            },
            timeout=60,
        )
        if proc.returncode != 0:
            sys.stderr.write(
                f"[query-onboarding-status] refresh-gate-stubs 退出码 {proc.returncode}\n"
            )
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        sys.stderr.write(f"[query-onboarding-status] refresh-gate-stubs 失败：{e}\n")
        return False


def _render_current_prompt(stub_scripts_dir, gate, state_dir, pinyin):
    """先刷新对应门落盘，再调 build-approval-prompt，保证 HR 看到最新物料。"""
    _refresh_gate_stubs(stub_scripts_dir, gate, state_dir, pinyin)
    try:
        proc = subprocess.run(
            ["python3", os.path.join(stub_scripts_dir, "build-approval-prompt.py"), gate, pinyin],
            env={**os.environ, "STATE": state_dir},
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            payload = json.loads(proc.stdout.strip())
            return payload.get("prompt", "")
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def _query_gate(workspace, stub_scripts_dir, gate, pinyin):
    pending_path = os.path.join(workspace, "pending-approvals", f"{pinyin}-{gate}.json")
    base = os.path.join(workspace, "stub-state", pinyin)

    if not os.path.exists(pending_path):
        return None

    with open(pending_path, encoding="utf-8") as f:
        rec = json.load(f)

    pre = rec.get("pre_halt_snapshot", {})

    # account 门新格式：{account, device, training}；旧格式：单层 account 字段
    # 注意：先做 diff（相对 halt 快照），再 refresh+拼 prompt，避免刷新时间戳干扰变更判断
    if gate == "account" and isinstance(pre, dict) and "account" in pre:
        cur = {}
        for key in ("account", "device", "training"):
            path = os.path.join(base, f"{key}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    cur[key] = json.load(f)
            else:
                cur[key] = {}
        diffs = []
        for key in ("account", "device", "training"):
            for d in _shallow_diff(pre.get(key) or {}, cur.get(key) or {}):
                diffs.append({
                    "field": f"{key}.{d['field']}",
                    "pre_halt": d["pre_halt"],
                    "current": d["current"],
                })
    else:
        state_path = os.path.join(base, f"{gate}.json")
        cur = {}
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                cur = json.load(f)
        diffs = _shallow_diff(pre, cur)

    prompt_now = _render_current_prompt(stub_scripts_dir, gate,
                                         os.path.join(workspace, "stub-state"),
                                         pinyin)

    return {
        "halted_at": rec.get("halted_at"),
        "stub_prepared_at_pre_halt": rec.get("stub_prepared_at"),
        "stub_updated_at_pre_halt": rec.get("stub_updated_at_pre_halt"),
        "stub_pre_halt": pre,
        "stub_current": cur,
        "stub_changed_after_halt": len(diffs) > 0,
        "diff_fields": diffs,
        "current_prompt": prompt_now,
    }


def _load_workflow(workspace, pinyin):
    path = os.path.join(workspace, "stub-state", pinyin, "workflow.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _halt_days(halted_at):
    t = _parse_iso(halted_at)
    if not t:
        return None
    now = dt.datetime.now(SHANGHAI)
    if t.tzinfo is None:
        t = t.replace(tzinfo=SHANGHAI)
    seconds = max(0, int((now - t).total_seconds()))
    return seconds // 86400


def _ensure_tokens(workspace, stub_scripts_dir, pinyin, wf):
    """卡在两道审批门且 workflow.json 缺 token 时，从 ~/.lobster/state 兜底。

    仅 status=halted 且 current_step ∈ {contract_gate, account_gate} 才查；
    其它节点直接返回。找到后回写 workflow.json，下次查询不再扫 lobster。
    """
    if not wf or wf.get("status") != "halted":
        return wf, None
    if wf.get("current_step") not in ("contract_gate", "account_gate"):
        return wf, None
    if wf.get("approval_id") and wf.get("resume_token"):
        return wf, "workflow.json"

    uw_path = os.path.join(stub_scripts_dir, "update-workflow.py")
    if not os.path.exists(uw_path):
        return wf, None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("update_workflow", uw_path)
        mod = importlib.util.module_from_spec(spec)
        # 让 ensure_approval_tokens 能拼出 stub-state/<pinyin>/
        os.environ.setdefault("STATE", os.path.join(workspace, "stub-state"))
        spec.loader.exec_module(mod)
        data, filled, src = mod.ensure_approval_tokens(pinyin, wf, persist=True)
        if filled:
            return data, src
        return data, src  # src 可能是 None（没找到）或 "workflow.json"
    except Exception as e:
        sys.stderr.write(f"[query-onboarding-status] lobster 兜底查找失败：{e}\n")
        return wf, None


def _summarize_workflow(name, pinyin, wf, token_source=None):
    status = wf.get("status", "unknown")
    step = wf.get("current_step", "?")
    lines = [f"== {name}（{pinyin}）入职审批状态 =="]
    lines.append(f" · 来源：stub-state/{pinyin}/workflow.json")
    lines.append(f" · 状态：{status} · 当前节点：{step}")
    if status == "halted":
        halted_at = wf.get("halted_at")
        days = _halt_days(halted_at)
        age = _humanize_age(halted_at)
        if days is not None and days >= 1:
            lines.append(f" · 已在 {step} 停留 {days} 天（halt 于 {halted_at}，{age}）")
        else:
            lines.append(f" · 已在 {step} 停留（halt 于 {halted_at}，{age}）")
        if wf.get("approval_id"):
            src = f"（来源：{token_source}）" if token_source else ""
            lines.append(f" · approval_id：{wf['approval_id']}{src}")
        if wf.get("resume_token"):
            tok = wf["resume_token"]
            lines.append(f" · resume_token：{tok[:32]}…（完整值见 JSON）")
            lines.append(f"   恢复命令：run-onboarding.sh resume <token> yes|no")
        elif step in ("contract_gate", "account_gate"):
            lines.append(" · 警告：卡在审批门但找不到 approval_id/resume_token")
            lines.append("   （workflow.json 无记录，~/.lobster/state 也无有效快照）")
    elif status == "completed":
        lines.append(f" · 完成于：{wf.get('completed_at')}")
    elif status == "cancelled":
        lines.append(" · 流程已取消（审批拒绝）")
    elif status == "started":
        lines.append(f" · 启动于：{wf.get('started_at')} · 进行中")

    events = wf.get("events") or []
    if events:
        lines.append("")
        lines.append(" · 扭转轨迹（最近 8 条）：")
        for e in events[-8:]:
            note = e.get("note") or ""
            note_s = f" · {note}" if note else ""
            lines.append(f"     [{e.get('at')}] {e.get('step')}/{e.get('action')}{note_s}")

    lines.append("")
    lines.append("→ 现状决策指引：")
    if status == "halted":
        lines.append("  流程卡在审批门·先查 stub_changed_after_halt，再决定 resume yes/no。")
    elif status == "completed":
        lines.append("  流程已结束，等待候选人报到当天签约。无需 resume。")
    elif status == "cancelled":
        lines.append("  流程已取消·如需重开，请 run-onboarding.sh start 重新启动。")
    else:
        lines.append("  流程进行中·尚未 halt，耐心等待下一个审批门。")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: query-onboarding-status.py <候选人全名> [pinyin]\n"
                         "       pinyin 可省·按 reference/pinyin.py 字典推导\n")
        sys.exit(1)
    name = sys.argv[1]
    pinyin = sys.argv[2] if len(sys.argv) > 2 else None

    workspace = os.environ.get("WORKSPACE")
    if not workspace:
        sys.stderr.write("[query-onboarding-status] 缺少 $WORKSPACE 环境变量。\n")
        sys.exit(2)

    pinyin = _resolve_pinyin(workspace, name, pinyin)
    if not pinyin:
        sys.stderr.write(
            f"[query-onboarding-status] 无法解析 '{name}' 的拼音目录。"
            "请手传拼音作为第 2 个参数，或确认 stub-state/<pinyin>/workflow.json 存在。\n"
        )
        sys.exit(4)

    stub_scripts_dir = _resolve_stub_scripts_dir()

    wf = _load_workflow(workspace, pinyin)

    found_pending = []
    halts = {}
    pending_dir = os.path.join(workspace, "pending-approvals")
    if os.path.isdir(pending_dir):
        for gate in ("contract", "account"):
            info = _query_gate(workspace, stub_scripts_dir, gate, pinyin)
            if info is not None:
                found_pending.append(gate)
                halts[gate] = info

    if wf is None and not found_pending:
        stub_dir = os.path.join(workspace, "stub-state", pinyin)
        if os.path.isdir(stub_dir):
            sys.stderr.write(
                f"[query-onboarding-status] '{name}'（{pinyin}）有 stub-state/{pinyin}/，"
                "但没有 workflow.json，也没有 pending-approvals。\n"
                "——可能是旧数据（workflow.json 落地前跑的）或流程异常中断。\n"
                "→ 建议：重跑 run-onboarding.sh start 生成完整扭转记录。\n"
            )
            sys.exit(3)
        sys.stderr.write(
            f"[query-onboarding-status] '{name}'（{pinyin}）未启动入职流程。\n"
            f"——stub-state/{pinyin}/ 与 pending-approvals/{pinyin}-* 都不存在。\n"
        )
        sys.exit(4)

    if wf is not None:
        wf, token_source = _ensure_tokens(workspace, stub_scripts_dir, pinyin, wf)
        summary = _summarize_workflow(name, pinyin, wf, token_source=token_source)
        if found_pending:
            summary += "\n\n · pending-approvals 附加：\n"
            for gate in found_pending:
                h = halts[gate]
                changed = h["stub_changed_after_halt"]
                age = _humanize_age(h["halted_at"])
                if changed:
                    summary += f"   - {gate}：{age} halt·stub 被改 {len(h['diff_fields'])} 项\n"
                else:
                    summary += f"   - {gate}：{age} halt·stub 未变\n"
        sys.stderr.write(summary + "\n")
        # 强制原样交回块（与 run-onboarding.sh 同一套标记）
        # 先按当前审批门再刷一次落盘，确保即便 pending 路径未触发也能更新
        state_root = os.path.join(workspace, "stub-state")
        os.environ["STATE"] = state_root
        os.environ["STUB_STATE_DIR"] = os.path.join(state_root, pinyin)
        os.environ["STUB"] = stub_scripts_dir
        gate_now = {"contract_gate": "contract", "account_gate": "account"}.get(
            (wf or {}).get("current_step") or ""
        )
        if (wf or {}).get("status") == "halted" and gate_now:
            _refresh_gate_stubs(stub_scripts_dir, gate_now, state_root, pinyin)
        emit = os.path.join(stub_scripts_dir, "emit-approval-verbatim.py")
        if os.path.exists(emit):
            try:
                subprocess.run(
                    ["python3", emit, pinyin],
                    env=os.environ.copy(),
                    timeout=90,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                sys.stderr.write(f"[query-onboarding-status] emit verbatim 失败：{e}\n")
        else:
            sys.stderr.write(
                f"[query-onboarding-status] 找不到 emit：{emit}\n"
            )
        payload = {
            "candidate_pinyin": pinyin,
            "query_input": name,
            "workflow": wf,
            "token_source": token_source,
            "halt_days": _halt_days(wf.get("halted_at")) if wf.get("status") == "halted" else None,
            "found_pending": found_pending,
            "halts": halts,
            "summary": summary,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 无 workflow.json、仅有 pending（旧数据兼容）
    lines = [f"== {name}（{pinyin}）入职审批状态 =="]
    lines.append(" · 来源：pending-approvals/（无 workflow.json，旧数据兼容）")
    for gate in found_pending:
        h = halts[gate]
        changed = h["stub_changed_after_halt"]
        halted_age = _humanize_age(h["halted_at"])
        if changed:
            lines.append(f" · {gate}：{halted_age} halt·stub 被改 {len(h['diff_fields'])} 项")
            for d in h["diff_fields"]:
                lines.append(f"     - {d['field']}: {d['pre_halt']!r} → {d['current']!r}")
        else:
            lines.append(f" · {gate}：{halted_age} halt·stub 未变")
    lines.append("")
    lines.append("→ 现状决策指引：")
    if all(not h["stub_changed_after_halt"] for h in halts.values()):
        lines.append("  所有 stub 都未变，resumeToken 有效·可放心 resume <token> yes。")
    else:
        lines.append("  有 stub 被改·如要走'最新 stub'重新审，请拒绝后让候选人 recruiter 重跑 start；")
        lines.append("  如认为旧 stub 足够·直接 resume <token> yes 也合理。")
    summary = "\n".join(lines)
    sys.stderr.write(summary + "\n")

    payload = {
        "candidate_pinyin": pinyin,
        "query_input": name,
        "workflow": None,
        "found_pending": found_pending,
        "halts": halts,
        "summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
