#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入职进度看板生成器 —— generating-onboarding-dashboard Skill 的核心脚本。

数据来源：HCM 系统 API（只读）
  - 花名册与五部门准备节点：GET /api/candidates
  - review 节点：candidate.reviews 字段
  - 审批门角标：本机 stub-state/<pinyin>/workflow.json（HCM 无此字段）

不向 HCM 写入，不读本地 stub-state 作为准备节点真相源。

用法: build-dashboard.py            -> 看板写到 <workspace>/onboarding-dashboard.html
      build-dashboard.py <输出路径>  -> 看板写到指定路径
"""
import json
import os
import sys
import datetime
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

# ── 路径推导
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.environ.get(
    "ONBOARDING_WORKSPACE",
    os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..")),
)

# HCM API 地址
HCM_API_BASE = os.environ.get("HCM_API_URL", "http://localhost:8000")

# 5 个入职准备节点
PREP_NODES = [
    ("contract", "合同签署"),
    ("account", "IT 账号"),
    ("device", "行政设备"),
    ("buddy", "Buddy 匹配"),
    ("training", "入职培训"),
]

# 4 个 review 节点
REVIEW_NODES = [7, 30, 60, 90]
REVIEW_LABEL = {7: "第 7 天", 30: "第 30 天", 60: "第 60 天", 90: "第 90 天"}

# 状态归类
DONE_WORDS = (
    "已审批", "已通过", "已开通", "已配齐", "已匹配", "已完成", "已签署", "已排期",
    "completed",
)
PENDING_WORDS = ("待审批", "待办", "待制", "待分配", "待排期", "待开通", "未就绪", "pending")

STEP_LABELS = {
    "prep": "入职准备",
    "contract_gate": "合同审批门",
    "account_gate": "账号审批门",
    "buddy": "Buddy 匹配",
    "complete": "流程归档",
}
STATUS_LABELS = {
    "started": "进行中",
    "halted": "等待审批",
    "completed": "已完成",
    "cancelled": "已取消",
    "onboarding": "入职中",
}


def classify(status):
    """把原始 status 归类为 done / progress / pending 三态。"""
    if not status or status in ("未就绪", "缺失"):
        return "pending"
    if status in DONE_WORDS or status in ("in_progress",):
        # in_progress 表示部门正在处理，算进行中
        if status in DONE_WORDS:
            return "done"
        return "progress"
    if status in PENDING_WORDS or (isinstance(status, str) and status.startswith("待")):
        return "pending"
    return "progress"


def hcm_get(path):
    """GET HCM API，返回 parsed JSON 或 None。"""
    url = f"{HCM_API_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"[dashboard] HCM API 请求失败: {url} — {e}", file=sys.stderr)
        return None


def fetch_candidates():
    """从 HCM API 获取所有候选人。"""
    data = hcm_get("/api/candidates")
    if data is None:
        print("[dashboard] ❌ HCM API 不可用，无法生成看板。", file=sys.stderr)
        sys.exit(5)
    return data


def load_workflow(pinyin):
    """读本机 workflow.json 获取审批门状态（HCM 无此字段）。"""
    path = os.path.join(WS, "stub-state", pinyin, "workflow.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def workflow_badge(wf):
    """从 workflow.json 拼卡片角标文案与 CSS 类。"""
    if not wf:
        return {"text": "无审批记录", "cls": "wf-unknown"}
    status = wf.get("status") or "started"
    step = wf.get("current_step") or "—"
    status_cn = STATUS_LABELS.get(status, status)
    step_cn = STEP_LABELS.get(step, step)
    if status == "halted":
        text = f"{status_cn} · {step_cn}"
        cls = "wf-halted"
    elif status == "completed":
        text = status_cn
        cls = "wf-done"
    elif status == "cancelled":
        text = status_cn
        cls = "wf-cancel"
    else:
        text = f"{status_cn} · {step_cn}"
        cls = "wf-active"
    return {"text": text, "cls": cls, "status": status, "step": step}


def build_employee(candidate):
    """汇总单个员工的 9 个节点状态 + workflow 角标 + 整体进度。"""
    name = candidate.get("name", "")
    pinyin = candidate.get("pinyin", "")
    role = candidate.get("role", "—")

    nodes = candidate.get("nodes") or []
    node_map = {n["node_type"]: n for n in nodes}

    # 5 个准备节点（来自 HCM）
    prep = []
    done_count = 0
    for key, label in PREP_NODES:
        n = node_map.get(key, {})
        raw_status = n.get("status", "未就绪")
        cls = classify(raw_status)
        if cls == "done":
            done_count += 1
        # 用 data.status（部门填的中文状态）作为显示文本，比 node.status 更友好
        data = n.get("data") or {}
        display = data.get("status", raw_status)
        prep.append({"label": label, "raw": display, "cls": cls})

    # 4 个 review 节点（来自 HCM）
    reviews_data = candidate.get("reviews") or []
    review_map = {r["review_type"]: r for r in reviews_data}
    reviews = []
    rdone = 0
    for day in REVIEW_NODES:
        rec = review_map.get(f"day{day}", {})
        st = rec.get("status", "pending")
        if st == "completed":
            reviews.append({"label": REVIEW_LABEL[day], "cls": "done",
                            "text": "已 review"})
            rdone += 1
        else:
            reviews.append({"label": REVIEW_LABEL[day], "cls": "pending",
                            "text": "待触发"})

    total = len(PREP_NODES) + len(REVIEW_NODES)
    pct = round((done_count + rdone) / total * 100)

    # 审批门角标来自本机 workflow.json
    wf = load_workflow(pinyin)
    badge = workflow_badge(wf)

    return {
        "name": name,
        "role": role,
        "pinyin": pinyin,
        "hcm_status": candidate.get("status", ""),
        "prep": prep,
        "reviews": reviews,
        "done_count": done_count,
        "rdone": rdone,
        "pct": pct,
        "badge": badge,
    }


def render_node(label, cls, sub):
    return f"""        <div class="node {cls}">
          <div class="node-dot"></div>
          <div class="node-label">{label}</div>
          <div class="node-status">{sub}</div>
        </div>"""


def render_card(data):
    badge = data["badge"]
    prep_html = "\n".join(
        render_node(n["label"], n["cls"], n["raw"])
        for n in data["prep"])
    rev_html = "\n".join(
        render_node(n["label"], n["cls"], n["text"])
        for n in data["reviews"])
    pct = data["pct"]
    bar_cls = "bar-high" if pct >= 80 else ("bar-mid" if pct >= 50 else "bar-low")
    return f"""    <section class="card">
      <header class="card-head">
        <div class="who">
          <span class="name">{data['name']}</span>
          <span class="role">{data['role']}</span>
        </div>
        <span class="wf-badge {badge['cls']}">{badge['text']}</span>
      </header>
      <div class="progress-row">
        <div class="progress-label">整体入职进度</div>
        <div class="progress-track">
          <div class="progress-fill {bar_cls}" style="width:{pct}%"></div>
        </div>
        <div class="progress-pct">{pct}%</div>
      </div>
      <div class="stage">
        <div class="stage-title">入职准备 · 5 节点
          <span class="stage-count">{data['done_count']}/5 完成</span></div>
        <div class="timeline">
{prep_html}
        </div>
      </div>
      <div class="stage">
        <div class="stage-title">试用期跟进 · 4 个 review 节点
          <span class="stage-count">{data['rdone']}/4 已 review</span></div>
        <div class="timeline">
{rev_html}
        </div>
      </div>
    </section>"""


def main():
    candidates = fetch_candidates()
    if not candidates:
        print("[dashboard] HCM 花名册为空，无候选人。", file=sys.stderr)
        sys.exit(2)

    cards = [build_employee(c) for c in candidates]
    now = datetime.datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M")
    total_emp = len(cards)
    avg = round(sum(c["pct"] for c in cards) / total_emp)

    cards_html = "\n".join(render_card(c) for c in cards)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>星桥科技 · 新员工入职进度看板</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
    background:#f4f6fa; color:#1f2733; padding:38px 40px;
  }}
  .page-head {{
    max-width:1500px; margin:0 auto 28px; display:flex;
    align-items:flex-end; justify-content:space-between;
  }}
  .page-head h1 {{ font-size:30px; font-weight:700; color:#1a2233; }}
  .page-head .sub {{ font-size:15px; color:#7a869a; margin-top:8px; }}
  .page-head .meta {{ font-size:15px; color:#7a869a; text-align:right; }}
  .page-head .meta b {{ color:#2f6df6; font-size:24px; }}
  .grid {{
    max-width:1500px; margin:0 auto;
    display:grid; grid-template-columns:repeat(3,1fr); gap:26px;
  }}
  .card {{
    background:#fff; border-radius:16px; padding:28px;
    box-shadow:0 2px 16px rgba(31,39,51,.08);
  }}
  .card-head {{
    display:flex; justify-content:space-between; align-items:flex-start;
    gap:12px; padding-bottom:16px; border-bottom:1px solid #eef1f6;
  }}
  .who .name {{ font-size:23px; font-weight:700; }}
  .who .role {{
    font-size:13px; color:#5b6b85; background:#eef3ff;
    padding:3px 10px; border-radius:6px; margin-left:9px;
  }}
  .wf-badge {{
    flex-shrink:0; font-size:12px; font-weight:600; padding:5px 10px;
    border-radius:8px; white-space:nowrap; line-height:1.3;
  }}
  .wf-halted {{ background:#fff3e0; color:#c77700; }}
  .wf-done   {{ background:#e6f7ef; color:#15a06a; }}
  .wf-active {{ background:#eef3ff; color:#2f6df6; }}
  .wf-cancel {{ background:#f1f3f6; color:#7a869a; }}
  .wf-unknown {{ background:#f1f3f6; color:#98a2b3; }}
  .progress-row {{
    display:flex; align-items:center; gap:12px; margin:20px 0 6px;
  }}
  .progress-label {{ font-size:14px; color:#5b6b85; white-space:nowrap; }}
  .progress-track {{
    flex:1; height:13px; background:#eef1f6; border-radius:7px; overflow:hidden;
  }}
  .progress-fill {{ height:100%; border-radius:7px; }}
  .bar-high {{ background:linear-gradient(90deg,#22c081,#15a06a); }}
  .bar-mid  {{ background:linear-gradient(90deg,#f5b13d,#f59331); }}
  .bar-low  {{ background:linear-gradient(90deg,#f1707a,#e44a57); }}
  .progress-pct {{ font-size:19px; font-weight:700; color:#2f3a4d; }}
  .stage {{ margin-top:22px; }}
  .stage-title {{
    font-size:15px; font-weight:600; color:#2f3a4d; margin-bottom:16px;
    display:flex; justify-content:space-between; align-items:center;
  }}
  .stage-count {{ font-size:12px; font-weight:500; color:#9aa4b6; }}
  .timeline {{
    display:flex; gap:4px;
  }}
  .node {{
    flex:1; text-align:center; position:relative; padding-top:16px;
  }}
  .node::before {{
    content:""; position:absolute; top:6px; left:50%; right:-50%;
    height:2px; background:#e3e7ef;
  }}
  .node:last-child::before {{ display:none; }}
  .node-dot {{
    width:14px; height:14px; border-radius:50%; margin:0 auto;
    position:relative; z-index:1; border:2px solid #fff;
  }}
  .node-label {{ font-size:12.5px; color:#3a4659; margin-top:9px; font-weight:600; }}
  .node-status {{ font-size:11px; margin-top:4px; line-height:1.4; }}
  .node.done    .node-dot {{ background:#22c081; box-shadow:0 0 0 3px #d3f3e6; }}
  .node.done    .node-status {{ color:#15a06a; }}
  .node.progress .node-dot {{ background:#f5b13d; box-shadow:0 0 0 3px #fdeccf; }}
  .node.progress .node-status {{ color:#d8841a; }}
  .node.pending .node-dot {{ background:#c2cad6; box-shadow:0 0 0 3px #eef1f6; }}
  .node.pending .node-status {{ color:#98a2b3; }}
  .legend {{
    max-width:1500px; margin:30px auto 0; display:flex; gap:28px;
    font-size:14px; color:#5b6b85; justify-content:center; flex-wrap:wrap;
  }}
  .legend span {{ display:flex; align-items:center; gap:7px; }}
  .dot {{ width:13px; height:13px; border-radius:50%; }}
  .dot.done {{ background:#22c081; }}
  .dot.progress {{ background:#f5b13d; }}
  .dot.pending {{ background:#c2cad6; }}
  .foot {{
    max-width:1500px; margin:20px auto 0; font-size:12.5px;
    color:#aab2c0; text-align:center;
  }}
</style>
</head>
<body>
  <div class="page-head">
    <div>
      <h1>星桥科技 · 新员工入职进度看板</h1>
      <div class="sub">数据来源：HCM 系统 API · 审批门角标读自本机 workflow.json</div>
    </div>
    <div class="meta">
      在职新员工 <b>{total_emp}</b> 人 · 平均进度 <b>{avg}%</b><br>
      生成时间 {now}
    </div>
  </div>
  <div class="grid">
{cards_html}
  </div>
  <div class="legend">
    <span><i class="dot done"></i>已完成</span>
    <span><i class="dot progress"></i>进行中</span>
    <span><i class="dot pending"></i>待办 / 待审批 / 待触发</span>
  </div>
  <div class="foot">
    准备节点与 review 状态来自 HCM GET /api/candidates ·
    审批门角标来自本机 stub-state/&lt;pinyin&gt;/workflow.json
  </div>
</body>
</html>"""

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WS, "onboarding-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[dashboard] 已生成 {out}（数据来源：HCM API）")
    for c in cards:
        badge = c["badge"]["text"]
        print(f"  {c['name']}: [{badge}] 准备 {c['done_count']}/5 · "
              f"review {c['rdone']}/4 · 整体 {c['pct']}%")


if __name__ == "__main__":
    main()
