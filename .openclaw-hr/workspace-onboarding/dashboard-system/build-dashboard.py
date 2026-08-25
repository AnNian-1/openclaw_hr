#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入职进度看板生成器
读 D-1 入职工作流的 stub-state 真实状态 + D-2 Cron review 落盘的 review-state,
生成一份可视化 HTML 看板,供 HR 一眼看清每个新员工卡在哪一步。

数据全部来自真实文件,本脚本不编造任何状态:
  - 准备节点状态 <- ../stub-state*/  (D-1 入职工作流跑出来的)
  - review 节点状态 <- ../review-state/  (D-2 Cron 定时触发落盘的)

用法: build-dashboard.py
"""
import json
import os
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(BASE)
REVIEW_DIR = os.path.join(WS, "review-state")

# 5 个入职准备节点(对应 D-1 入职工作流的 5 个 stub 系统)
PREP_NODES = [
    ("contract", "合同签署"),
    ("account", "IT 账号"),
    ("device", "行政设备"),
    ("buddy", "Buddy 匹配"),
    ("training", "入职培训"),
]

# 4 个 review 节点(对应 09-入职流程.md 第四节的跟进节点)
REVIEW_NODES = [7, 30, 60, 90]
REVIEW_LABEL = {7: "第 7 天", 30: "第 30 天", 60: "第 60 天", 90: "第 90 天"}

# 自动发现候选人：遍历 stub-state/<pinyin>/ 子目录，每个子目录 = 1 个候选人。
# candidate / role / prepared_at 从该目录里的 contract.json 等 gate 文件读出，
# 不再硬编码员工名单——新员工跑完 run-onboarding.sh start 后自动出现在看板上。
STUB_STATE_ROOT = os.path.join(WS, "stub-state")


def discover_employees():
    """遍历 stub-state/*/ 自动发现候选人，按目录 mtime 倒序（最新入职在前）。"""
    emps = []
    if not os.path.isdir(STUB_STATE_ROOT):
        return emps
    cands = []
    for entry in os.listdir(STUB_STATE_ROOT):
        sub = os.path.join(STUB_STATE_ROOT, entry)
        if os.path.isdir(sub):
            cands.append((entry, sub, os.path.getmtime(sub)))
    cands.sort(key=lambda x: x[2], reverse=True)
    for pinyin, sub, _ in cands:
        candidate_name = pinyin
        role = "员工"
        join = ""
        for probe in ("contract.json", "buddy.json", "account.json"):
            p = os.path.join(sub, probe)
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        d = json.load(f)
                    candidate_name = d.get("candidate") or pinyin
                    role = d.get("role") or role
                    if not join:
                        pa = d.get("prepared_at", "")
                        join = pa[:10] if pa else ""
                    break
                except Exception:
                    pass
        emps.append({
            "name": candidate_name,
            "pinyin": pinyin,
            "role": role,
            "join": join,
            "state_dir": os.path.join("stub-state", pinyin),
        })
    return emps

# 状态归类:把 stub-state 里五花八门的中文 status 归到 3 个标准态。
# "已排期"指培训节点已安排好日期(报到时该准备节点即完成),归为 done。
DONE_WORDS = ("已审批", "已开通", "已配齐", "已匹配", "已完成", "已签署", "已排期")
PENDING_WORDS = ("待审批", "待办", "待制", "待分配", "待排期", "待开通")


def classify(status):
    """把原始 status 文案归类为 done / progress / pending 三态。"""
    if status in DONE_WORDS:
        return "done"
    if status in PENDING_WORDS or status.startswith("待"):
        return "pending"
    return "progress"  # 进行中 / 起草中 等


def read_status(state_dir, node_key):
    path = os.path.join(WS, state_dir, node_key + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("status", "缺失")
    except Exception:
        return "未就绪"


def load_reviews(name):
    """读 review-state 目录,返回该员工已 review 的天数集合。"""
    done = set()
    if not os.path.isdir(REVIEW_DIR):
        return done
    for fn in os.listdir(REVIEW_DIR):
        if fn.startswith("review-" + name + "-day") and fn.endswith(".json"):
            with open(os.path.join(REVIEW_DIR, fn), encoding="utf-8") as f:
                rec = json.load(f)
            done.add(int(rec.get("day", 0)))
    return done


STATE_CN = {"done": "已完成", "progress": "进行中", "pending": "待办"}
STATE_CLASS = {"done": "done", "progress": "progress", "pending": "pending"}


def build_employee(emp):
    """汇总单个员工的 9 个节点状态 + 整体进度。"""
    prep = []
    done_count = 0
    for key, label in PREP_NODES:
        raw = read_status(emp["state_dir"], key)
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

    # 整体进度 = 9 个节点里完成的占比
    total = len(PREP_NODES) + len(REVIEW_NODES)
    pct = round((done_count + rdone) / total * 100)
    return {"emp": emp, "prep": prep, "reviews": reviews,
            "done_count": done_count, "rdone": rdone, "pct": pct}


def render_node(label, cls, sub):
    return f"""        <div class="node {cls}">
          <div class="node-dot"></div>
          <div class="node-label">{label}</div>
          <div class="node-status">{sub}</div>
        </div>"""


def render_card(data):
    emp = data["emp"]
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
        <div class="join">入职日 {emp['join']}</div>
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
        print(f"[dashboard] 警告：{STUB_STATE_ROOT}/ 下未发现候选人目录（应为 stub-state/<pinyin>/）。")
        print("[dashboard] 请先跑 run-onboarding.sh start 让 stub 写入候选人目录。")
        return
    cards = [build_employee(e) for e in employees]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
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
    padding-bottom:16px; border-bottom:1px solid #eef1f6;
  }}
  .who .name {{ font-size:23px; font-weight:700; }}
  .who .role {{
    font-size:13px; color:#5b6b85; background:#eef3ff;
    padding:3px 10px; border-radius:6px; margin-left:9px;
  }}
  .join {{ font-size:13px; color:#9aa4b6; }}
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
    font-size:14px; color:#5b6b85; justify-content:center;
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
      <div class="sub">入职准备 5 节点 + 试用期跟进 4 节点 · 数据来自入职工作流与 Cron 定时 review</div>
    </div>
    <div class="meta">
      在入职新员工 <b>{total_emp}</b> 人 · 平均进度 <b>{avg}%</b><br>
      生成时间 {now}
    </div>
  </div>
  <div class="grid">
{cards_html}
  </div>
  <div class="legend">
    <span><i class="dot done"></i>已完成</span>
    <span><i class="dot progress"></i>进行中</span>
    <span><i class="dot pending"></i>待办 / 待触发</span>
  </div>
  <div class="foot">
    准备节点状态读自 workspace-onboarding/stub-state*（入职工作流产出）·
    review 节点状态读自 workspace-onboarding/review-state（Cron 定时 review 落盘）
  </div>
</body>
</html>"""

    out = os.path.join(BASE, "onboarding-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[dashboard] 已生成 {out}")
    for c in cards:
        print(f"  {c['emp']['name']}: 准备 {c['done_count']}/5 · "
              f"review {c['rdone']}/4 · 整体 {c['pct']}%")


if __name__ == "__main__":
    main()
