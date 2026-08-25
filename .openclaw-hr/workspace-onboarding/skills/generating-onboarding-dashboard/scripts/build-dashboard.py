#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入职进度看板生成器 —— generating-onboarding-dashboard Skill 的核心脚本。

读入职审批工作流落盘的 stub-state 真实状态 + Cron review 落盘的 review-state,
生成一份可视化 HTML 看板,供 HR 一眼看清每个新员工卡在哪一步。

数据全部来自真实落盘文件,本脚本不编造任何状态:
  - 准备节点状态 <- <workspace>/stub-state*/   (入职工作流跑出来的)
  - 流程扭转状态 <- <workspace>/stub-state/<pinyin>/workflow.json
  - review 节点状态 <- <workspace>/review-state/ (Cron 定时 review 落盘的)

封进 Skill 后路径推导:本脚本位于
  <workspace>/skills/generating-onboarding-dashboard/scripts/build-dashboard.py
向上三级即 workspace 根。也支持环境变量 ONBOARDING_WORKSPACE 覆盖(测试/移植用)。
不再硬编码员工名单——自动发现 workspace 根下所有 stub-state* 目录,
新员工跑完入职工作流就自动出现在看板上,无需改本脚本。

用法: build-dashboard.py            -> 看板写到 <workspace>/onboarding-dashboard.html
      build-dashboard.py <输出路径>  -> 看板写到指定路径
"""
import json
import os
import sys
import datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

# ── 路径推导:脚本在 <workspace>/skills/<skill>/scripts/ 下,向上三级是 workspace 根。
#    ONBOARDING_WORKSPACE 环境变量可覆盖,便于测试与移植。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.environ.get(
    "ONBOARDING_WORKSPACE",
    os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..")),
)
REVIEW_DIR = os.path.join(WS, "review-state")

# 5 个入职准备节点(对应入职审批工作流的 5 个 stub 系统)
PREP_NODES = [
    ("contract", "合同签署"),
    ("account", "IT 账号"),
    ("device", "行政设备"),
    ("buddy", "Buddy 匹配"),
    ("training", "入职培训"),
]

# 4 个 review 节点(对应入职流程的 7/30/60/90 天跟进节点)
REVIEW_NODES = [7, 30, 60, 90]
REVIEW_LABEL = {7: "第 7 天", 30: "第 30 天", 60: "第 60 天", 90: "第 90 天"}

# 状态归类:把 stub-state 里五花八门的中文 status 归到 3 个标准态。
# 「待审批」= 已进审批门、等真人批；「已审批/已通过」= 审批通过后。
# 「已排期」指培训节点已安排好日期(报到时该准备节点即完成),归为 done。
DONE_WORDS = (
    "已审批", "已通过", "已开通", "已配齐", "已匹配", "已完成", "已签署", "已排期",
)
PENDING_WORDS = ("待审批", "待办", "待制", "待分配", "待排期", "待开通", "未就绪")

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
}


def classify(status):
    """把原始 status 文案归类为 done / progress / pending 三态。"""
    if status in DONE_WORDS:
        return "done"
    if status in PENDING_WORDS or status.startswith("待"):
        return "pending"
    return "progress"  # 进行中 / 起草中 等


def read_node(state_dir, node_key):
    """读某个准备节点的 JSON,返回 (status, 整条记录)。文件缺失返回未就绪。"""
    path = os.path.join(state_dir, node_key + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        return rec.get("status", "缺失"), rec
    except Exception:
        return "未就绪", {}


def read_workflow(state_dir):
    """读 workflow.json；缺失返回空 dict。"""
    path = os.path.join(state_dir, "workflow.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_employee_dir(state_dir):
    """至少有 contract.json 或 workflow.json 才算有效候选人目录（跳过空壳）。"""
    return (
        os.path.isfile(os.path.join(state_dir, "contract.json"))
        or os.path.isfile(os.path.join(state_dir, "workflow.json"))
    )


def workflow_badge(wf):
    """从 workflow.json 拼卡片角标文案与 CSS 类。"""
    if not wf:
        return {"text": "无流程记录", "cls": "wf-unknown"}
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


def discover_employees():
    """自动发现 workspace 根下所有 stub-state 目录下的员工状态。
    支持两种目录结构:
      旧结构: stub-state-张磊/  每个目录直接是一个员工
      新结构: stub-state/zhanglei/  员工按拼音放在子目录里
    同名候选人优先保留新结构（stub-state/<pinyin>/）。
    员工姓名/岗位从 contract.json / workflow.json 读取——不再硬编码名单。
    """
    found = []  # list of dicts
    for entry in sorted(os.listdir(WS)):
        full = os.path.join(WS, entry)
        if not (entry.startswith("stub-state") and os.path.isdir(full)):
            continue

        nested = entry == "stub-state"
        subdirs = sorted(
            d for d in os.listdir(full)
            if os.path.isdir(os.path.join(full, d))
        )
        if subdirs:
            for sub in subdirs:
                sub_full = os.path.join(full, sub)
                if not is_employee_dir(sub_full):
                    continue
                wf = read_workflow(sub_full)
                _, contract = read_node(sub_full, "contract")
                name = (
                    contract.get("candidate")
                    or wf.get("candidate")
                    or sub
                )
                role = contract.get("role") or wf.get("role") or "—"
                found.append({
                    "name": name,
                    "role": role,
                    "state_dir": sub_full,
                    "pinyin": wf.get("pinyin") or sub,
                    "nested": nested,
                    "wf": wf,
                })
        else:
            if not is_employee_dir(full):
                continue
            wf = read_workflow(full)
            _, contract = read_node(full, "contract")
            name = (
                contract.get("candidate")
                or wf.get("candidate")
                or entry.replace("stub-state-", "")
                or entry
            )
            role = contract.get("role") or wf.get("role") or "—"
            found.append({
                "name": name,
                "role": role,
                "state_dir": full,
                "pinyin": wf.get("pinyin") or "",
                "nested": False,
                "wf": wf,
            })

    # 同名去重：优先 stub-state/<pinyin>/（nested=True）
    by_name = {}
    for emp in found:
        key = emp["name"]
        prev = by_name.get(key)
        if prev is None or (emp["nested"] and not prev["nested"]):
            by_name[key] = emp
    return [by_name[k] for k in sorted(by_name.keys())]


def load_reviews(name):
    """读 review-state 目录,返回该员工已 review 的天数集合。"""
    done = set()
    if not os.path.isdir(REVIEW_DIR):
        return done
    for fn in os.listdir(REVIEW_DIR):
        if fn.startswith("review-" + name + "-day") and fn.endswith(".json"):
            try:
                with open(os.path.join(REVIEW_DIR, fn), encoding="utf-8") as f:
                    rec = json.load(f)
                done.add(int(rec.get("day", 0)))
            except Exception:
                continue
    return done


def build_employee(emp):
    """汇总单个员工的 9 个节点状态 + workflow 角标 + 整体进度。"""
    prep = []
    done_count = 0
    for key, label in PREP_NODES:
        raw, _ = read_node(emp["state_dir"], key)
        cls = classify(raw)
        if cls == "done":
            done_count += 1
        prep.append({"label": label, "raw": raw, "cls": cls})

    reviewed = load_reviews(emp["name"])
    reviews = []
    rdone = 0
    for day in REVIEW_NODES:
        if day in reviewed:
            reviews.append({"label": REVIEW_LABEL[day], "cls": "done",
                            "text": "已 review"})
            rdone += 1
        else:
            reviews.append({"label": REVIEW_LABEL[day], "cls": "pending",
                            "text": "待触发"})

    total = len(PREP_NODES) + len(REVIEW_NODES)
    pct = round((done_count + rdone) / total * 100)
    badge = workflow_badge(emp.get("wf") or {})
    return {
        "emp": emp,
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
    emp = data["emp"]
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
          <span class="name">{emp['name']}</span>
          <span class="role">{emp['role']}</span>
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
    employees = discover_employees()
    if not employees:
        print("[dashboard] 未发现任何 stub-state* 目录——还没有员工跑过入职工作流。",
              file=sys.stderr)
        sys.exit(2)

    cards = [build_employee(e) for e in employees]
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
      <div class="sub">入职准备 5 节点 + 试用期跟进 4 节点 · 卡片角标读自 workflow.json</div>
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
    准备节点读自 stub-state*/（入职工作流）· 流程角标读自 workflow.json ·
    review 节点读自 review-state（Cron 定时 review）
  </div>
</body>
</html>"""

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WS, "onboarding-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[dashboard] 已生成 {out}")
    for c in cards:
        badge = c["badge"]["text"]
        print(f"  {c['emp']['name']}: [{badge}] 准备 {c['done_count']}/5 · "
              f"review {c['rdone']}/4 · 整体 {c['pct']}%")


if __name__ == "__main__":
    main()
