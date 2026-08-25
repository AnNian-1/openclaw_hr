#!/usr/local/miniconda3/envs/py312/bin/python3
# -*- coding: utf-8 -*-
"""
HTML 候选人画像生成器  ·  openclaw-ai-hr 阶段 C 招聘子 Agent

输入：C-2 产出的 ranking-后端开发.json（某候选人的 parsed 解析数据 + score 评分数据）
输出：单文件 HTML 候选人画像（图表 base64 内嵌，离线可打开）

画像构成：
  1. 候选人基本信息卡（姓名 / 目标岗位 / 期望薪资·城市 / 到岗时间 / 学历 / 经验年限）
  2. 综合评级横幅（综合匹配分 + A/B/C/D 评级 + 建议处置）
  3. 8 维度能力雷达图（matplotlib 极坐标，base64 内嵌）
  4. 工作经历时间线（HTML+CSS 竖向时间轴）
  5. 技能分布图（matplotlib 横向条形图，按熟练度着色，base64 内嵌）
  6. 与 JD 匹配度对比（综合分 vs 岗位基线进度条）
  7. 亮点 / 顾虑 / 硬伤三栏

数据真实性铁律：所有字段值取自 ranking JSON，脚本不编造任何内容。

用法：
  python3 generate_profile.py <ranking.json> <候选人姓名> <输出 HTML 路径>
"""
import sys
import json
import base64
import io
import re
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

# ---- 中文字体（macOS 自带，画像图表里的中文不能是方块）----
_CN_FONT = None
for _name in ["WenQuanYi Micro Hei", "WenQuanYi Micro Hei Mono", "Songti SC", "STHeiti", "Heiti TC", "PingFang SC", "PingFang HK", "Arial Unicode MS"]:
    try:
        font_manager.findfont(_name, fallback_to_default=False)
        _CN_FONT = _name
        break
    except Exception:
        continue
if _CN_FONT:
    plt.rcParams["font.sans-serif"] = [_CN_FONT]
plt.rcParams["axes.unicode_minus"] = False

# 评级配色（A 绿 / B 蓝 / C 橙 / D 灰红）
RATING_COLOR = {"S": "#8b5cf6", "A": "#16a34a", "B": "#2563eb", "C": "#ea580c", "D": "#9ca3af"}
RATING_LABEL = {"S": "卓越", "A": "强烈推荐", "B": "推荐", "C": "待定", "D": "不匹配"}


def fig_to_base64(fig):
    """matplotlib 图 -> base64 data URI（内嵌 HTML，不依赖外部文件）"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii")


def norm_rating(raw):
    """评级可能是 'B' 或 'B(推荐)' 或 'D(不匹配)'，取首字母"""
    m = re.match(r"\s*([SABCD])", str(raw))
    return m.group(1) if m else "C"


def make_radar(dim_scores):
    """8 维度能力雷达图。dim_scores: {维度名: 1-5 分}"""
    labels = list(dim_scores.keys())
    values = [dim_scores[k] for k in labels]
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_c = values + values[:1]
    angles_c = angles + angles[:1]

    fig = plt.figure(figsize=(5.2, 5.2))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], color="#9ca3af", fontsize=8)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=11, color="#374151")
    ax.plot(angles_c, values_c, color="#2563eb", linewidth=2)
    ax.fill(angles_c, values_c, color="#2563eb", alpha=0.20)
    # 每个顶点标分数
    for ang, val in zip(angles, values):
        ax.text(ang, val + 0.35, str(val), ha="center", va="center",
                fontsize=10, color="#1d4ed8", fontweight="bold")
    ax.spines["polar"].set_color("#e5e7eb")
    ax.grid(color="#e5e7eb")
    return fig_to_base64(fig)


def make_skill_cloud(skills):
    """技能词云（标签云）：技能名错落布局，字号按简历中的列出顺序递减。
       简历里候选人优先列出的技能 = 自我认知中的核心技能，这是真实排序信号，
       不编造熟练度等级。skills 是字符串列表，取技能名（去掉括号注释）。"""
    # 清洗：取技能名主体，过滤掉过长的描述性条目
    names = []
    for s in skills:
        name = re.split(r"[（(]", str(s))[0].strip()
        # 去掉"了解/熟悉"等前缀动词，保留技能本体
        name = re.sub(r"^(了解|熟悉|掌握|熟练|精通)\s*", "", name)
        if name and len(name) <= 16:
            names.append(name)
    names = names[:24]  # 词云最多 24 个标签，过多会拥挤
    n = len(names)
    if n == 0:
        names, n = ["（简历未列明技能）"], 1

    # 字号：越靠前越大（22 -> 11），调色板冷色系
    palette = ["#1e3a8a", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"]
    sizes = np.linspace(22, 11, n)

    n_rows = int(np.ceil(n / 4.5)) + 1
    fig, ax = plt.subplots(figsize=(6.6, max(2.0, 0.46 * n_rows)))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # 简单网格错落布局：按行排，每行交错起点，模拟标签云
    rng = np.random.RandomState(42)  # 固定种子，保证可复现
    x, y = 0.4, 9.5
    row_h = 9.2 / n_rows
    for i, name in enumerate(names):
        fs = sizes[i]
        color = palette[i % len(palette)]
        est_w = len(name) * fs * 0.020 + 0.45  # 估算标签宽度（绘图坐标）
        if x + est_w > 9.8:
            x = 0.4 + rng.uniform(0, 0.4)
            y -= row_h
        ax.text(x, y, name, fontsize=fs, color=color, va="top", ha="left",
                fontweight="bold" if i < 5 else "normal")
        x += est_w + 0.3
    return fig_to_base64(fig)


def build_timeline(work_exp):
    """工作经历时间线（HTML+CSS 竖向时间轴）"""
    rows = []
    for w in work_exp:
        company = w.get("company", "—")
        position = w.get("position", "—")
        period = "{} ~ {}".format(w.get("start_date", "?"), w.get("end_date", "?"))
        rows.append(
            '<div class="tl-item">'
            '<div class="tl-dot"></div>'
            '<div class="tl-card">'
            '<div class="tl-period">{}</div>'
            '<div class="tl-company">{}</div>'
            '<div class="tl-position">{}</div>'
            '</div></div>'.format(period, company, position)
        )
    return '<div class="timeline">' + "".join(rows) + "</div>"


def build_list(title, items, cls):
    if not items:
        items_html = '<li class="empty">无</li>'
    else:
        items_html = "".join("<li>{}</li>".format(x) for x in items)
    return ('<div class="lc {}"><div class="lc-title">{}</div>'
            '<ul>{}</ul></div>').format(cls, title, items_html)


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>候选人画像 · {name}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"PingFang SC","Microsoft YaHei",sans-serif; background:#f1f5f9;
          color:#1f2937; padding:32px 16px; }}
  .page {{ max-width:960px; margin:0 auto; background:#fff; border-radius:16px;
           box-shadow:0 8px 30px rgba(0,0,0,0.08); overflow:hidden; }}
  /* 顶部信息卡 */
  .header {{ background:linear-gradient(135deg,#1e3a8a,#2563eb); color:#fff;
             padding:28px 36px; display:flex; justify-content:space-between; align-items:center; }}
  .h-left h1 {{ font-size:26px; margin-bottom:6px; }}
  .h-left .target {{ font-size:15px; opacity:0.9; }}
  .h-meta {{ margin-top:14px; display:flex; gap:24px; flex-wrap:wrap; font-size:13px; }}
  .h-meta div span {{ opacity:0.7; }}
  .rating-badge {{ text-align:center; padding:16px 22px; border-radius:12px;
                   background:rgba(255,255,255,0.14); }}
  .rating-badge .score {{ font-size:42px; font-weight:700; line-height:1; }}
  .rating-badge .grade {{ font-size:15px; margin-top:6px; padding:2px 12px;
                          border-radius:20px; display:inline-block; font-weight:600; }}
  .rating-badge .action {{ font-size:12px; margin-top:8px; opacity:0.85; }}
  /* 区块 */
  .section {{ padding:24px 36px; border-bottom:1px solid #f1f5f9; }}
  .section-title {{ font-size:16px; font-weight:600; color:#1e3a8a; margin-bottom:16px;
                    padding-left:10px; border-left:4px solid #2563eb; }}
  .two-col {{ display:flex; gap:28px; align-items:flex-start; }}
  .two-col > div {{ flex:1; }}
  .chart img {{ width:100%; }}
  .chart-cap {{ text-align:center; font-size:12px; color:#9ca3af; margin-top:4px; }}
  /* 维度分表 */
  .dim-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .dim-table td {{ padding:7px 6px; border-bottom:1px solid #f1f5f9; }}
  .dim-table .dname {{ color:#374151; width:78px; }}
  .dim-bar-bg {{ background:#f1f5f9; border-radius:6px; height:9px; width:100%; }}
  .dim-bar {{ background:#2563eb; border-radius:6px; height:9px; }}
  .dim-score {{ width:30px; text-align:right; color:#1d4ed8; font-weight:600; }}
  /* 时间线 */
  .timeline {{ position:relative; padding-left:24px; }}
  .timeline:before {{ content:""; position:absolute; left:6px; top:4px; bottom:4px;
                      width:2px; background:#dbeafe; }}
  .tl-item {{ position:relative; margin-bottom:18px; }}
  .tl-dot {{ position:absolute; left:-22px; top:4px; width:12px; height:12px;
             border-radius:50%; background:#2563eb; border:3px solid #dbeafe; }}
  .tl-card {{ background:#f8fafc; border-radius:10px; padding:12px 16px; }}
  .tl-period {{ font-size:12px; color:#2563eb; font-weight:600; }}
  .tl-company {{ font-size:15px; font-weight:600; margin-top:3px; }}
  .tl-position {{ font-size:13px; color:#6b7280; margin-top:2px; }}
  /* JD 匹配度 */
  .match-row {{ margin-bottom:14px; }}
  .match-label {{ display:flex; justify-content:space-between; font-size:13px;
                  margin-bottom:5px; color:#374151; }}
  .match-bar-bg {{ background:#f1f5f9; border-radius:8px; height:14px; }}
  .match-bar {{ border-radius:8px; height:14px; }}
  /* 亮点/顾虑/硬伤 */
  .lists {{ display:flex; gap:18px; }}
  .lc {{ flex:1; border-radius:10px; padding:14px 16px; }}
  .lc-title {{ font-size:14px; font-weight:600; margin-bottom:8px; }}
  .lc ul {{ list-style:none; }}
  .lc li {{ font-size:12.5px; line-height:1.7; padding-left:14px; position:relative; color:#374151; }}
  .lc li:before {{ content:""; position:absolute; left:0; top:8px; width:5px; height:5px;
                   border-radius:50%; }}
  .lc li.empty {{ color:#9ca3af; }}
  .lc.good {{ background:#f0fdf4; }} .lc.good .lc-title {{ color:#16a34a; }}
  .lc.good li:before {{ background:#16a34a; }}
  .lc.warn {{ background:#fff7ed; }} .lc.warn .lc-title {{ color:#ea580c; }}
  .lc.warn li:before {{ background:#ea580c; }}
  .lc.risk {{ background:#fef2f2; }} .lc.risk .lc-title {{ color:#dc2626; }}
  .lc.risk li:before {{ background:#dc2626; }}
  /* 评分理由 */
  .reasoning {{ background:#f8fafc; border-radius:10px; padding:14px 18px;
               font-size:13px; line-height:1.8; color:#374151; }}
  .footer {{ padding:16px 36px; font-size:11px; color:#9ca3af; text-align:center;
             background:#f8fafc; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="h-left">
      <h1>{name}</h1>
      <div class="target">求职意向：{target}</div>
      <div class="h-meta">
        <div><span>期望薪资</span> {salary}</div>
        <div><span>期望城市</span> {city}</div>
        <div><span>到岗时间</span> {available}</div>
        <div><span>学历</span> {degree} · {school}</div>
        <div><span>工作年限</span> {years} 年 / {jobs} 段经历</div>
      </div>
    </div>
    <div class="rating-badge">
      <div class="score">{match_score}</div>
      <div class="grade" style="background:{rcolor};color:#fff;">{rating} 级 · {rlabel}</div>
      <div class="action">{action}</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">能力雷达 · 8 维度评估</div>
    <div class="two-col">
      <div class="chart">
        <img src="{radar}" alt="8 维度能力雷达图">
        <div class="chart-cap">8 维度评分（1-5 分，初筛阶段评分 · 面试待复核）</div>
      </div>
      <div>
        <table class="dim-table">{dim_rows}</table>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">与岗位 JD 匹配度</div>
    {match_bars}
  </div>

  <div class="section">
    <div class="section-title">工作经历时间线</div>
    {timeline}
  </div>

  <div class="section">
    <div class="section-title">技能词云</div>
    <div class="chart">
      <img src="{skill_chart}" alt="技能词云" style="max-width:680px;">
      <div class="chart-cap">共 {skill_count} 项技能，字号按简历中列出的先后排序（越靠前 = 候选人优先列出的核心技能）</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">亮点 · 顾虑 · 硬伤</div>
    <div class="lists">
      {good}
      {warn}
      {risk}
    </div>
  </div>

  <div class="section">
    <div class="section-title">综合评分理由</div>
    <div class="reasoning">{reasoning}</div>
  </div>

  <div class="footer">
    本画像由 HR 数字员工招聘子 Agent 自动生成 · 数据源：简历解析 + AI 评分（C-1/C-2）<br>
    评分仅供初筛参考，最终录用决定由人工做出 · 生成时间 {gen_time}
  </div>

</div>
</body>
</html>"""


def main():
    if len(sys.argv) != 4:
        print("用法: python3 generate_profile.py <ranking.json> <候选人姓名> <输出 HTML 路径>")
        sys.exit(1)

    ranking_path, target_name, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    data = json.load(open(ranking_path, encoding="utf-8"))

    # 从 details 里找目标候选人 + 从 ranking 里取 suggested_action
    detail = None
    for d in data.get("details", []):
        if d.get("parsed", {}).get("name") == target_name:
            detail = d
            break
    if detail is None:
        print("错误：在 {} 中找不到候选人「{}」".format(ranking_path, target_name))
        print("可选：", [d.get("parsed", {}).get("name") for d in data.get("details", [])])
        sys.exit(2)

    action = ""
    for r in data.get("ranking", []):
        if r.get("name") == target_name:
            action = r.get("suggested_action", "")
            break

    parsed = detail["parsed"]
    score = detail["score"]
    edu = parsed.get("education", {})
    rating = norm_rating(score.get("overall_rating", "C"))

    print("[1/4] 候选人「{}」数据载入 · 综合分 {} · 评级 {}".format(
        target_name, score.get("jd_match_score"), rating))

    # 图表
    radar = make_radar(score["dimension_scores"])
    print("[2/4] 8 维度雷达图已渲染（matplotlib 极坐标）")
    skill_chart = make_skill_cloud(parsed.get("skills", []))
    print("[3/4] 技能词云已渲染（{} 项技能）".format(len(parsed.get("skills", []))))

    # 8 维度表格行
    dim_rows = ""
    for dname, dval in score["dimension_scores"].items():
        pct = int(dval / 5 * 100)
        dim_rows += (
            '<tr><td class="dname">{}</td>'
            '<td><div class="dim-bar-bg"><div class="dim-bar" style="width:{}%;"></div></div></td>'
            '<td class="dim-score">{}</td></tr>'.format(dname, pct, dval)
        )

    # JD 匹配度进度条：综合分 vs 岗位基线 60
    rcolor = RATING_COLOR[rating]
    match_score = score.get("jd_match_score", 0)
    baseline = 60  # 岗位初筛通过基线
    match_bars = (
        '<div class="match-row"><div class="match-label">'
        '<span>本候选人综合匹配分</span><span>{ms} / 100</span></div>'
        '<div class="match-bar-bg"><div class="match-bar" '
        'style="width:{ms}%;background:{c};"></div></div></div>'
        '<div class="match-row"><div class="match-label">'
        '<span>岗位初筛通过基线</span><span>{bl} / 100</span></div>'
        '<div class="match-bar-bg"><div class="match-bar" '
        'style="width:{bl}%;background:#cbd5e1;"></div></div></div>'
    ).format(ms=match_score, c=rcolor, bl=baseline)

    timeline = build_timeline(parsed.get("work_experience", []))
    good = build_list("亮点", score.get("highlights", []), "good")
    warn = build_list("顾虑", score.get("concerns", []), "warn")
    risk = build_list("硬伤", score.get("hard_issues", []), "risk")

    html = HTML_TMPL.format(
        name=parsed.get("name", target_name),
        target=parsed.get("target_position", "—"),
        salary=parsed.get("expected_salary", "—"),
        city=parsed.get("expected_city", "—"),
        available=parsed.get("available_date", "—"),
        degree=edu.get("degree", "—"),
        school=edu.get("school", "—"),
        years=parsed.get("total_experience_years", "—"),
        jobs=parsed.get("job_count", "—"),
        match_score=match_score,
        rating=rating,
        rlabel=RATING_LABEL[rating],
        rcolor=rcolor,
        action=action or "—",
        radar=radar,
        dim_rows=dim_rows,
        match_bars=match_bars,
        timeline=timeline,
        skill_chart=skill_chart,
        skill_count=len(parsed.get("skills", [])),
        good=good, warn=warn, risk=risk,
        reasoning=score.get("score_reasoning", "—"),
        gen_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("[4/4] HTML 画像已生成 -> {}".format(out_path))


if __name__ == "__main__":
    main()
