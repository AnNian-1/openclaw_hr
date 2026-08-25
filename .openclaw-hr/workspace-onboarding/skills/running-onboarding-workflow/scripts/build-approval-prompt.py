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
  · contract 门：只读合同节点
  · account 门：读 account + device + training 三个节点（IT/行政/培训并行准备的产物），
    审批人一次看齐「账号能否开通 + 设备是否配齐 + 培训是否排期」

§13 升级：在 prompt 末尾追加各 stub 准备时间 + 人话等待时长。
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


def _read_state(path):
    """从本地 JSON 文件读取状态（回退方案）。"""
    if not os.path.exists(path):
        sys.stderr.write(
            f"[build-approval-prompt] 缺少状态文件：{path}\n"
            "——通常因为 4 路并行准备没跑完、或被人手动删了。"
            "请重新执行 run-onboarding.sh start ... 让 prep 步骤重写 stub-state。\n"
        )
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_node_from_api(pinyin, node_type):
    """从 HCM API 读取节点数据（优先数据源）。返回 dict 或 None。"""
    if not _HCM_AVAILABLE:
        return None
    data = hcm_api.get_prep_node_data(pinyin, node_type)
    return data if data else None


def _read_state_with_fallback(api_pinyin, node_type, local_path):
    """优先从 HCM API 读取，不可用时回退到本地 JSON 文件。
    两者都无数据时返回默认占位 dict（不 exit）。"""
    api_data = _read_node_from_api(api_pinyin, node_type)
    if api_data is not None and api_data:
        return api_data
    if os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as f:
            return json.load(f)
    # 无数据时返回默认占位（不 exit，让调用方处理“未就绪”）
    return {}


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


def build_contract_prompt(state_dir, pinyin):
    c = _read_state_with_fallback(
        pinyin, "contract",
        os.path.join(state_dir, pinyin, "contract.json"),
    )
    status = (c.get("status") or "").strip() or "待审批"
    # 状态必须进第一行：Agent 常只保留首句再自造表格，放后面会被丢掉
    lines = [
        f'HR 主管，请审批 {c["candidate"]} 的劳动合同【当前状态：{status}】：',
        f'· 状态：{status}',
        f'· 岗位：{c.get("role", "")} / 薪资：{c.get("salary", "")} / 试用期：{c.get("probation", "")}',
        f'· 合同：{c.get("contract", "")}',
    ]
    # 配套文件：数据里有且非空才展示；没有就整行省略
    files = (c.get("files") or "").strip()
    if files:
        lines.append(f'· 配套文件：{files}')
    lines.append('是否批准进入签约？')
    prompt = "\n".join(lines)
    prompt = _append_age_clause(prompt, c)

    # items：空 files 删掉；把 status 提到最前，降低 Agent 漏画概率
    item = dict(c)
    if not (item.get("files") or "").strip():
        item.pop("files", None)
    ordered = {"status": status}
    for k, v in item.items():
        if k == "status":
            continue
        ordered[k] = v
    return {"prompt": prompt, "items": [ordered]}


def build_account_prompt(state_dir, pinyin):
    """第二道门：账号 + 设备 + 培训 + Buddy 四合一审批。"""
    base = os.path.join(state_dir, pinyin)
    a = _read_state_with_fallback(pinyin, "account", os.path.join(base, "account.json"))
    d = _read_state_with_fallback(pinyin, "device", os.path.join(base, "device.json"))
    t = _read_state_with_fallback(pinyin, "training", os.path.join(base, "training.json"))
    b = _read_state_with_fallback(pinyin, "buddy", os.path.join(base, "buddy.json"))

    a_status = (a.get("status") or "").strip() or "待审批"
    d_status = (d.get("status") or "").strip()
    t_status = (t.get("status") or "").strip()
    b_status = (b.get("status") or "").strip()
    # Buddy 未就绪时显式标记，防止无声跳过
    buddy_line = f'· Buddy：{b.get("buddy", "")} / 带教导师：{b.get("mentor", "")}'
    if b_status:
        buddy_line += f'（{b_status}）'
    else:
        buddy_line += '（未就绪 — 用人部门尚未匹配 Buddy）'

    lines = [
        f'IT 安全负责人，请审批 {a["candidate"]} 的入职 IT/行政准备【账号状态：{a_status}】：',
        f'· 账号：工号 {a.get("workno", "")} / 邮箱 {a.get("email", "")}'
        f' / 企业微信 {a.get("wecom", "")}（{a_status}）',
        f'· 设备：{d.get("laptop", "")} / {d.get("badge", "")} / {d.get("desk", "")}'
        + (f'（{d_status}）' if d_status else ''),
        f'· 培训：{t.get("course", "")} · {t.get("date", "")}'
        + (f'（{t_status}）' if t_status else ''),
        buddy_line,
        '是否批准开通账号，并确认设备/培训/Buddy 已就绪？',
    ]
    prompt = "\n".join(lines)
    prompt = _append_multi_age_clause(prompt, [
        ("账号", a),
        ("设备", d),
        ("培训", t),
        ("Buddy", b),
    ])
    # status 提到 items 最前
    a_ord = {"status": a_status, **{k: v for k, v in a.items() if k != "status"}}
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
