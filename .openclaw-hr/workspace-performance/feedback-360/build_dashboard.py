#!/usr/bin/env python3
"""360 反馈可视化看板：从 aggregated-data.json 取数，渲染四视角雷达对比图，
输出单文件自包含 HTML（report.html）。所有数字直取聚合数据，不重新计算。"""

import json
import os
import base64
import io
import hashlib
import math

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "aggregated-data.json")
OUT_PATH = os.path.join(BASE, "report.html")

# ---- 1. 读聚合数据（唯一数据基准，记录 md5 防漂移）----
with open(DATA_PATH, "rb") as f:
    raw_bytes = f.read()
DATA_MD5 = hashlib.md5(raw_bytes).hexdigest()
data = json.loads(raw_bytes)

DIM_KEYS = ["goal_achievement", "professional_skill", "collaboration", "responsibility", "growth"]
DIM_CN = {
    "goal_achievement": "目标达成", "professional_skill": "专业能力",
    "collaboration": "协作沟通", "responsibility": "责任心", "growth": "学习成长",
}
PERSP_ORDER = ["manager", "peer", "report", "self"]
PERSP_CN = {"manager": "上级", "peer": "平级", "report": "下属", "self": "自评"}
PERSP_COLOR = {"manager": "#2563eb", "peer": "#059669", "report": "#d97706", "self": "#9333ea"}

# 各视角各维度平均分（直取，不计算）
persp_avg = {}
for p in PERSP_ORDER:
    persp_avg[p] = [data["perspectives"][p]["dimensions"][d]["average"] for d in DIM_KEYS]

# ---- 2. matplotlib 渲染雷达对比图 ----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CJK_FONT = None
for fname in ["Songti SC", "STHeiti", "Heiti SC", "STSong"]:
    try:
        fpath = font_manager.findfont(fname, fallback_to_default=False)
        CJK_FONT = font_manager.FontProperties(fname=fpath)
        plt.rcParams["font.sans-serif"] = [fname]
        plt.rcParams["font.family"] = "sans-serif"
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

labels = [DIM_CN[d] for d in DIM_KEYS]
N = len(labels)
angles = [n / float(N) * 2 * math.pi for n in range(N)]
angles += angles[:1]

fig = plt.figure(figsize=(7.8, 8.2), dpi=130)
ax = plt.subplot(111, polar=True)
ax.set_position([0.12, 0.12, 0.76, 0.70])  # 顶部留白给标题、底部留白给图例
ax.set_theta_offset(math.pi / 2)
ax.set_theta_direction(-1)
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, fontsize=13, fontproperties=CJK_FONT)
ax.tick_params(axis="x", pad=10)
ax.set_ylim(0, 5)
ax.set_yticks([1, 2, 3, 4, 5])
ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=9, color="#888")
ax.grid(color="#d0d0d0", linewidth=0.8)

for p in PERSP_ORDER:
    vals = persp_avg[p] + persp_avg[p][:1]
    ax.plot(angles, vals, linewidth=2.2, label=PERSP_CN[p], color=PERSP_COLOR[p])
    ax.fill(angles, vals, alpha=0.08, color=PERSP_COLOR[p])

leg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=4,
                fontsize=12, frameon=False, handletextpad=0.4, columnspacing=1.6,
                prop=CJK_FONT)
for txt in leg.get_texts():
    txt.set_fontproperties(CJK_FONT)
    txt.set_fontsize(13)
fig.suptitle("四视角 × 五维度 评分雷达对比", fontsize=16, y=0.96, fontproperties=CJK_FONT)

buf = io.BytesIO()
plt.savefig(buf, format="png")
plt.close(fig)
radar_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

# ---- 3. 维度分类（共识/分歧）----
# 极差是机械信号（视角平均分 range），但最终共识/分歧判定以综合分析报告为准：
# 责任心极差 1.00 正好踩阈值，但报告综合评语后判定为共识（上级 4 分是留成长空间，
# 评语核心叙事一致）。看板判定与 aggregated-report.md 的章节归属对齐——
# 报告第三章共识点 3 项，第四章分歧点 2 项。
REPORT_VERDICT = {
    "goal_achievement": "consensus",
    "professional_skill": "consensus",
    "collaboration": "split",
    "responsibility": "consensus",
    "growth": "split",
}
dim_rows = []
for d in DIM_KEYS:
    avgs = [data["perspectives"][p]["dimensions"][d]["average"] for p in PERSP_ORDER]
    rng = round(max(avgs) - min(avgs), 2)
    dim_rows.append({
        "key": d, "cn": DIM_CN[d], "avgs": avgs, "range": rng,
        "is_split": REPORT_VERDICT[d] == "split",
    })

consensus = [r for r in dim_rows if not r["is_split"]]
splits = [r for r in dim_rows if r["is_split"]]

# 平级内部明细（协作沟通维度）
peer_collab = data["perspectives"]["peer"]["dimensions"]["collaboration"]["scores"]
peer_reviewers = [r["alias"] for r in data["perspectives"]["peer"]["reviewers"]]

# ---- 4. 拼 HTML ----
def score_cell(v):
    color = "#059669" if v >= 4.5 else ("#2563eb" if v >= 3.5 else ("#d97706" if v >= 2.5 else "#dc2626"))
    return f'<td style="color:{color};font-weight:600">{v:.2f}</td>'

dim_table_rows = ""
for r in dim_rows:
    tag = ('<span class="tag split">分歧</span>' if r["is_split"]
           else '<span class="tag consensus">共识</span>')
    cells = "".join(score_cell(v) for v in r["avgs"])
    dim_table_rows += f"<tr><td class='dim'>{r['cn']}</td>{cells}<td>{r['range']:.2f}</td><td>{tag}</td></tr>\n"

peer_rows = ""
for alias, sc in zip(peer_reviewers, peer_collab):
    peer_rows += f"<tr><td>{alias}</td>{score_cell(float(sc))}</tr>\n"

# 共识点/分歧点文字（来自综合分析报告的核心结论）
CONSENSUS_NOTES = {
    "goal_achievement": "全视角 4 分高度一致。支付网关重构成果（P99 延迟降 43%）被所有视角认可，是本次 360 最稳固的共识。",
    "professional_skill": "得分最高、赞誉最集中的维度，7 人无一人低于 4 分。组内公认的技术标杆，专业能力无争议。",
    "responsibility": "所有视角评分 ≥ 4，核心叙事一致——靠谱、顶得上、兜底。下属视角尤其高（双 5 分）。",
}
SPLIT_NOTES = {
    "collaboration": {
        "title": "协作沟通 — 对内暖、对外硬",
        "body": "极差 1.50。本质不是「不会协作」，而是协作能力高度情境分化：向下带教满分级、同组平级顺畅、跨组协作明显摩擦。平级平均 3.00 掩盖了关键结构——同组 4 分、风控 2 分、前端 3 分。",
    },
    "growth": {
        "title": "学习成长 — 成长定义不一致",
        "body": "极差 2.00（最大）。自评 5 分 vs 上级 3 分。分歧源于对「成长」的定义不同：上级要的是角色成长（带人、做沉淀、影响团队），员工1认定的是技术深度成长。这是面谈必须对齐的认知 gap。",
    },
}

consensus_cards = ""
for r in consensus:
    note = CONSENSUS_NOTES.get(r["key"], "")
    consensus_cards += f"""
    <div class="card consensus-card">
      <div class="card-h"><span class="dot c"></span>{r['cn']}<span class="range">极差 {r['range']:.2f}</span></div>
      <p>{note}</p>
    </div>"""

split_cards = ""
for r in splits:
    n = SPLIT_NOTES[r["key"]]
    avgs_str = " / ".join(f"{PERSP_CN[p]} {v:.2f}" for p, v in zip(PERSP_ORDER, r["avgs"]))
    split_cards += f"""
    <div class="card split-card">
      <div class="card-h"><span class="dot s"></span>{n['title']}<span class="range">极差 {r['range']:.2f}</span></div>
      <p class="avgs">{avgs_str}</p>
      <p>{n['body']}</p>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>员工1 2026 上半年 360 反馈聚合看板</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"PingFang SC","Songti SC",sans-serif; background:#f4f5f7; color:#1f2937; line-height:1.7; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:32px 28px 56px; }}
  .banner {{ background:#fff7ed; border:1px solid #fdba74; border-radius:8px; padding:14px 18px; margin-bottom:24px; font-size:14px; color:#9a3412; }}
  .banner b {{ color:#c2410c; }}
  h1 {{ font-size:24px; margin-bottom:6px; }}
  .sub {{ color:#6b7280; font-size:14px; margin-bottom:24px; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:10px 24px; background:#fff; border-radius:8px; padding:16px 20px; margin-bottom:24px; font-size:14px; }}
  .meta span b {{ color:#374151; }}
  section {{ background:#fff; border-radius:8px; padding:22px 24px; margin-bottom:22px; }}
  h2 {{ font-size:17px; margin-bottom:14px; padding-left:10px; border-left:4px solid #2563eb; }}
  .radar {{ text-align:center; }}
  .radar img {{ max-width:560px; width:100%; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ padding:9px 8px; text-align:center; border-bottom:1px solid #eef0f2; }}
  th {{ background:#f8fafc; color:#475569; font-weight:600; }}
  td.dim {{ text-align:left; font-weight:600; }}
  .tag {{ font-size:12px; padding:2px 9px; border-radius:10px; color:#fff; }}
  .tag.consensus {{ background:#059669; }}
  .tag.split {{ background:#d97706; }}
  .cards {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  .card {{ border-radius:8px; padding:14px 16px; font-size:13.5px; }}
  .consensus-card {{ background:#ecfdf5; border:1px solid #a7f3d0; }}
  .split-card {{ background:#fffbeb; border:1px solid #fde68a; }}
  .card-h {{ font-weight:700; font-size:14.5px; margin-bottom:6px; display:flex; align-items:center; gap:6px; }}
  .dot {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
  .dot.c {{ background:#059669; }}
  .dot.s {{ background:#d97706; }}
  .range {{ margin-left:auto; font-size:12px; font-weight:500; color:#6b7280; }}
  .avgs {{ color:#6b7280; font-size:12.5px; margin-bottom:4px; }}
  .conclude {{ font-size:14px; }}
  .conclude .col {{ margin-bottom:12px; }}
  .conclude h3 {{ font-size:14.5px; margin-bottom:4px; color:#374151; }}
  .conclude ul {{ padding-left:20px; }}
  .review-stamp {{ display:inline-block; background:#1e293b; color:#fff; font-size:13px; padding:6px 14px; border-radius:6px; margin-top:8px; }}
  footer {{ font-size:12px; color:#9ca3af; margin-top:20px; text-align:center; }}
  .peer-detail {{ margin-top:16px; }}
  .peer-detail h3 {{ font-size:14px; color:#92400e; margin-bottom:8px; }}
  .note {{ font-size:12.5px; color:#6b7280; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">

  <div class="banner">
    <b>合规声明：</b>本看板为 360 反馈聚合分析，<b>供绩效面谈与校准会 review</b>。AI 仅执行反馈聚合与综合分析，
    <b>不进行绩效评级</b>。最终绩效评级（S/A/B/C/D）由直接主管初评、隔级主管复核、校准会确认三级人工流程确定
    （依据《个人信息保护法》第 24 条 · 公司绩效管理制度第五条）。
  </div>

  <h1>员工1 · 2026 上半年 360 反馈聚合看板</h1>
  <div class="sub">支付平台研发组 后端开发工程师 · 半年度考核（1-6 月）</div>

  <div class="meta">
    <span><b>评估对象</b>　员工1</span>
    <span><b>反馈来源</b>　{data['total_feedback_count']} 份（上级 1 + 平级 3 + 下属 2 + 自评 1）</span>
    <span><b>考核周期</b>　{data['period']}</span>
    <span><b>数据性质</b>　模拟数据</span>
  </div>

  <section class="radar">
    <h2>一、四视角评分雷达对比</h2>
    <img src="data:image/png;base64,{radar_b64}" alt="四视角雷达对比图">
    <p class="note">雷达图越外圈分越高。四条线越贴合 = 各视角越一致；某个维度上线条越发散 = 视角分歧越大。</p>
  </section>

  <section>
    <h2>二、五维度评分对照表</h2>
    <table>
      <thead><tr><th>维度</th><th>上级</th><th>平级</th><th>下属</th><th>自评</th><th>极差</th><th>判定</th></tr></thead>
      <tbody>
      {dim_table_rows}
      </tbody>
    </table>
    <p class="note">极差是机械信号（四视角平均分的最大差）。最终共识/分歧判定以综合分析报告为准——责任心极差虽达 1.00，但各视角核心评语一致（上级 4 分是留成长空间），综合分析后归为共识。机械信号触发关注，结论交给语义分析。</p>

    <div class="peer-detail">
      <h3>平级内部明细 · 协作沟通维度（平均分 3.00 掩盖了内部结构）</h3>
      <table>
        <thead><tr><th>平级评估人</th><th>协作沟通评分</th></tr></thead>
        <tbody>
        {peer_rows}
        </tbody>
      </table>
      <p class="note">同组 4 分、风控 2 分、前端 3 分——协作分歧的本质是「对内 vs 对外」分化，单看平级平均分 3.00 发现不了。</p>
    </div>
  </section>

  <section>
    <h2>三、共识点（{len(consensus)} 项 · 各视角说法一致）</h2>
    <div class="cards">
    {consensus_cards}
    </div>
  </section>

  <section>
    <h2>四、分歧点（{len(splits)} 项 · 各视角说法不一致）</h2>
    <div class="cards">
    {split_cards}
    </div>
    <p class="note">分歧点是 360 反馈最有诊断价值的产出。聚合分析只负责把分歧摆出来、给出原因假设，不下结论——结论由主管在面谈中与本人对齐。</p>
  </section>

  <section class="conclude">
    <h2>五、综合结论（供面谈 review）</h2>
    <div class="col">
      <h3>三个核心长板（来自 7 份反馈交集）</h3>
      <ul>
        <li>技术硬实力无可争议——专业能力 7 人无一低于 4 分，网关重构 P99 延迟降 43% 有硬数据支撑。</li>
        <li>靠谱稳健的交付者——目标达成四视角一致 4 分，大促、线上告警关键节点「顶得上」。</li>
        <li>用心的带教者——两个下属反馈充满具体事例（逐行 code review、主动兜底、每周固定沟通）。</li>
      </ul>
    </div>
    <div class="col">
      <h3>两个成长瓶颈（需在面谈中对齐）</h3>
      <ul>
        <li>跨组协作是当前最大软肋——不是「会不会协作」，而是跨组场景下「捍卫技术方案」与「理解协作方诉求」的平衡未找到。</li>
        <li>成长认知与主管期待存在 gap——本人认为在「做深技术」上成长大，主管认为在「做宽影响力」上偏被动。</li>
      </ul>
    </div>
    <div class="col">
      <h3>建议面谈聚焦</h3>
      <ul>
        <li>跨组摩擦的根源探索——回顾具体评审场景，找「既保稳定性又满足风控诉求」的第三条路。</li>
        <li>成长期待对齐——把主管的抽象期待转化为 1-2 个可观察的下半年行为目标。</li>
        <li>聚焦一个关键行为改变，而非列一堆改进项。</li>
      </ul>
    </div>
    <div class="review-stamp">本看板为面谈输入材料 · 最终绩效定级由人工三级流程确定 · AI 不出评级</div>
  </section>

  <footer>
    数据来源：feedback-360/aggregated-data.json（md5 {DATA_MD5[:12]}） ·
    综合分析：feedback-360/aggregated-report.md ·
    所有评分直取聚合数据，看板不重新计算
  </footer>

</div>
</body>
</html>
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ 看板生成：{OUT_PATH}")
print(f"   数据基准 md5：{DATA_MD5}")
print(f"   共识维度：{', '.join(r['cn'] for r in consensus)}")
print(f"   分歧维度：{', '.join(r['cn'] for r in splits)}")
print(f"   雷达图 base64 长度：{len(radar_b64)} 字符（PNG 内嵌，单文件自包含）")
print(f"   HTML 文件大小：{os.path.getsize(OUT_PATH)} 字节")
