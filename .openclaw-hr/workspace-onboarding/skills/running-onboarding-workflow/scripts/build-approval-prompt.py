#!/usr/bin/env python3
"""
build-approval-prompt.py —— 入职审批门 prompt 构建器

由 hr-onboarding.lobster 的两个 approval: true 步骤调用：
    run: python3 $STUB/build-approval-prompt.py contract <pinyin>
    run: python3 $STUB/build-approval-prompt.py account  <pinyin>

负责两件事：
  1. 从 HCM 系统 API 读取各部门填写的最新数据（真相源）。
     API 不可用时回退到本地 stub-state/<pinyin>/ JSON 文件。
  2. 按门类型拼出中文 prompt + items，输出 Lobster 期望的 JSON。

业务保鲜范围：
  · contract 门：只读 HCM 合同节点
  · account 门：读 account + device + training + buddy（HCM 真实状态）。
    任一仍为 pending 时，prompt 明确写「请勿批准」，入职小慧不代替部门填写。

§13 升级：在 prompt 末尾追加各节点落盘时间 + 人话等待时长。
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

# HCM API 客户端（优先数据源）
try:
    import hcm_api
    _HCM_AVAILABLE = True
except ImportError:
    _HCM_AVAILABLE = False

SHANGHAI = ZoneInfo("Asia/Shanghai")

STATUS_LABELS = {
    "pending": "未开始",
    "in_progress": "进行中",
    "completed": "已完成",
    "paused": "暂停",
    "rejected": "否决",
}


def _read_state(path):
    """从本地 JSON 文件读取状态（回退方案）。"""
    if not os.path.exists(path):
        sys.stderr.write(
            f"[build-approval-prompt] 缺少状态文件：{path}\n"
            "——通常因为尚未从 HCM 快照，或 stub 被人手动删了。"
            "请重新执行 run-onboarding.sh start ... 让 prep 从 HCM 重写 stub-state。\n"
        )
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_node_from_api(pinyin, node_type):
    """从 HCM 读节点：顶层 status + data，不编造部门产出。"""
    if not _HCM_AVAILABLE:
        return None
    node = hcm_api.get_prep_node(pinyin, node_type)
    if not node:
        return None
    data = dict(node.get("data") or {})
    hcm_status = node.get("status") or "pending"
    info = hcm_api.get_candidate_info(pinyin) or {}
    rec = {
        "candidate": info.get("name") or data.get("candidate") or pinyin,
        "hcm_status": hcm_status,
        "status": STATUS_LABELS.get(hcm_status, hcm_status),
        "source": "hcm",
        "role": data.get("role") or info.get("role") or "",
        "salary": data.get("salary") or info.get("salary") or "",
        **{k: v for k, v in data.items()
           if k not in ("status", "system", "candidate", "hcm_status", "role", "salary")},
    }
    return rec


def _read_state_with_fallback(api_pinyin, node_type, local_path):
    """优先从 HCM API 读取，不可用时回退到本地 JSON 文件。
    两者都无数据时返回默认占位 dict（不 exit）。"""
    api_data = _read_node_from_api(api_pinyin, node_type)
    if api_data is not None and api_data:
        return api_data
    if os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "candidate": api_pinyin,
        "hcm_status": "pending",
        "status": "未开始",
        "source": "none",
    }


def _parse_iso(s):
    """解析落盘 ISO 时间：支持 +08:00（上海）与旧数据 Z（UTC）。失败返回 None。"""
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
    """把 ISO 时间转人话：'5 秒前' / '5 分钟前' / '2 小时前' / '3 天前'。"""
    t = _parse_iso(iso)
    if not t:
        return "时间未知"
    now = dt.datetime.now(SHANGHAI)
    if t.tzinfo is None:
        t = t.replace(tzinfo=SHANGHAI)
    delta = now - t
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "刚刚"   # stub 时间在未来（时钟漂移）
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def _append_age_clause(prompt, stub_or_prepared):
    """在 prompt 末尾追加落盘时间。优先展示 updated_at（查询刷新可见）。"""
    if isinstance(stub_or_prepared, dict):
        prepared = stub_or_prepared.get("prepared_at")
        updated = stub_or_prepared.get("updated_at") or prepared
    else:
        prepared = stub_or_prepared
        updated = stub_or_prepared
    if not updated:
        return prompt
    age = _humanize_age(updated)
    if prepared and prepared != updated:
        return (
            f"{prompt}\n\n"
            f"（材料首次准备于 {prepared}；本次落盘刷新于 {updated}，{age}）"
        )
    return f"{prompt}\n\n（材料准备于 {updated}，{age}）"


def _append_multi_age_clause(prompt, labeled_stubs):
    """多份 stub 各自追加时间（用 updated_at 反映查询刷新）。"""
    parts = []
    for label, stub in labeled_stubs:
        updated = stub.get("updated_at") or stub.get("prepared_at")
        if not updated:
            continue
        prepared = stub.get("prepared_at")
        if prepared and prepared != updated:
            parts.append(
                f"{label}首次 {prepared}，刷新于 {updated}（{_humanize_age(updated)}）"
            )
        else:
            parts.append(f"{label}准备于 {updated}，{_humanize_age(updated)}")
    if not parts:
        return prompt
    return f"{prompt}\n\n（{'；'.join(parts)}）"


def _hcm_line(rec):
    hcm = rec.get("hcm_status") or ""
    label = rec.get("status") or STATUS_LABELS.get(hcm, hcm or "未知")
    if hcm:
        return f"{label}（HCM {hcm}）"
    return label or "未知"


def _pending_warn(labeled_recs):
    pending = [
        label for label, rec in labeled_recs
        if (rec.get("hcm_status") or "pending") == "pending"
    ]
    if not pending:
        return ""
    return (
        "\n\n⚠️ 以下节点在 HCM 仍为 pending（未开始）："
        + "、".join(pending)
        + "。材料未齐，请勿批准。请先催对应部门在 HCM 填写。"
        "入职小慧不代替部门执行。"
    )


def build_contract_prompt(state_dir, pinyin):
    c = _read_state_with_fallback(
        pinyin, "contract",
        os.path.join(state_dir, pinyin, "contract.json"),
    )
    name = c.get("candidate") or pinyin
    status_line = _hcm_line(c)
    lines = [
        f'HR 主管，请审批 {name} 的劳动合同【当前状态：{status_line}】：',
        f'· HCM 合同节点：{status_line}',
        f'· 岗位：{c.get("role", "")} / 薪资：{c.get("salary", "")} / 试用期：{c.get("probation", "")}',
    ]
    contract = (c.get("contract") or "").strip()
    if contract:
        lines.append(f'· 合同：{contract}')
    files = (c.get("files") or "").strip()
    if files:
        lines.append(f'· 配套文件：{files}')
    warn = _pending_warn([("合同", c)])
    if warn:
        lines.append('合同材料尚未在 HCM 开始填写，请勿批准。')
    else:
        lines.append('是否批准进入签约？')
    prompt = "\n".join(lines) + warn
    prompt = _append_age_clause(prompt, c)

    item = dict(c)
    if not (item.get("files") or "").strip():
        item.pop("files", None)
    ordered = {"hcm_status": c.get("hcm_status") or "pending", "status": c.get("status") or ""}
    for k, v in item.items():
        if k in ordered:
            continue
        ordered[k] = v
    return {"prompt": prompt, "items": [ordered]}


def build_account_prompt(state_dir, pinyin):
    """第二道门：账号 + 设备 + 培训 + Buddy，展示 HCM 真实状态。"""
    base = os.path.join(state_dir, pinyin)
    a = _read_state_with_fallback(pinyin, "account", os.path.join(base, "account.json"))
    d = _read_state_with_fallback(pinyin, "device", os.path.join(base, "device.json"))
    t = _read_state_with_fallback(pinyin, "training", os.path.join(base, "training.json"))
    b = _read_state_with_fallback(pinyin, "buddy", os.path.join(base, "buddy.json"))

    name = a.get("candidate") or pinyin
    a_line, d_line, t_line, b_line = _hcm_line(a), _hcm_line(d), _hcm_line(t), _hcm_line(b)
    warn = _pending_warn([
        ("IT 账号", a), ("设备", d), ("培训", t),
    ])
    buddy_bits = []
    if b.get("buddy"):
        buddy_bits.append(str(b["buddy"]))
    if b.get("mentor"):
        buddy_bits.append(f"导师 {b['mentor']}")
    buddy_detail = " / ".join(buddy_bits) if buddy_bits else "（HCM 未填）"

    lines = [
        f'IT 安全负责人，请审批 {name} 的入职 IT/行政准备【账号：{a_line}】：',
        f'· 账号：工号 {a.get("workno") or "未填"} / 邮箱 {a.get("email") or "未填"}'
        f' / 企业微信 {a.get("wecom") or "未填"}（{a_line}）',
        f'· 设备：{d.get("laptop") or "未填"} / {d.get("badge") or "未填"} / {d.get("desk") or "未填"}'
        f'（{d_line}）',
        f'· 培训：{t.get("course") or "未填"} · {t.get("date") or "未填"}（{t_line}）',
        f'· Buddy：{buddy_detail}（{b_line}）',
    ]
    if warn:
        lines.append('账号/设备/培训在 HCM 尚未开始，请勿批准开通。')
    else:
        lines.append('是否批准开通账号，并确认设备/培训已由对应部门在 HCM 填写？')
    prompt = "\n".join(lines) + warn
    prompt = _append_multi_age_clause(prompt, [
        ("账号", a),
        ("设备", d),
        ("培训", t),
        ("Buddy", b),
    ])
    a_ord = {
        "hcm_status": a.get("hcm_status") or "pending",
        "status": a.get("status") or "",
        **{k: v for k, v in a.items() if k not in ("hcm_status", "status")},
    }
    return {"prompt": prompt, "items": [a_ord, d, t, b]}


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: build-approval-prompt.py <contract|account> <pinyin>\n")
        sys.exit(1)
    gate = sys.argv[1]
    pinyin = sys.argv[2]
    state_dir = os.environ.get("STATE")
    if not state_dir:
        sys.stderr.write("[build-approval-prompt] 缺少 $STATE 环境变量。\n")
        sys.exit(2)
    if gate == "contract":
        payload = build_contract_prompt(state_dir, pinyin)
    elif gate == "account":
        payload = build_account_prompt(state_dir, pinyin)
    else:
        sys.stderr.write(f"[build-approval-prompt] 未知 gate: {gate}\n")
        sys.exit(1)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
