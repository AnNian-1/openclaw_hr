#!/usr/bin/env python3
"""build_dashboard.py — 360 反馈可视化看板生成器

用途：generating-360-dashboard Skill 的核心脚本。
      - 评分 / 极差：直读同目录 aggregated-data.json（不重算）
      - 共识/分歧判定与卡片语义：必须来自同目录 aggregated-report.md
      渲染雷达图 + 对照表 + 卡片，输出同目录单文件 HTML（report.html）。

路径约定：
  feedback-360/source_feedback/<slug>/
    ├── aggregated-data.json   # 评分唯一基准
    ├── aggregated-report.md   # 语义判定与卡片文案（必读）
    └── report.html            # 缺省产出（语义已吸入，页面自包含）

CLI：
  python3 build_dashboard.py <person_dir|aggregated_json> [out_html] [verdict_json]
  退出码 0 = 成功；1 = 数据问题；2 = 用法错误
"""

import json
import os
import re
import sys
import base64
import io
import hashlib
import math

DIM_KEYS = ["goal_achievement", "professional_skill",
            "collaboration", "responsibility", "growth"]
DIM_CN = {
    "goal_achievement": "目标达成", "professional_skill": "专业能力",
    "collaboration": "协作沟通", "responsibility": "责任心", "growth": "学习成长",
}
DIM_CN_TO_KEY = {v: k for k, v in DIM_CN.items()}
PERSP_ORDER = ["manager", "peer", "report", "self"]
PERSP_CN = {"manager": "上级", "peer": "平级", "report": "下属", "self": "自评"}
PERSP_COLOR = {"manager": "#2563eb", "peer": "#059669",
               "report": "#d97706", "self": "#9333ea"}


def die(msg, code=1):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def resolve_paths(cli_target, out_html=None):
    """返回 (data_path, report_path, out_path, person_dir)。"""
    target = os.path.abspath(cli_target)
    if os.path.isdir(target):
        person_dir = target
        data_path = os.path.join(person_dir, "aggregated-data.json")
    elif os.path.isfile(target):
        data_path = target
        person_dir = os.path.dirname(data_path)
    else:
        die(f"路径不存在: {cli_target}", 2)

    if not os.path.isfile(data_path):
        die(f"聚合数据不存在: {data_path}", 2)

    report_path = os.path.join(person_dir, "aggregated-report.md")
    out_path = (os.path.abspath(out_html) if out_html
                else os.path.join(person_dir, "report.html"))
    return data_path, report_path, out_path, person_dir


def _clean_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _label_to_verdict(label: str):
    """共识 / 边界共识 → consensus；分歧 → split。"""
    if not label:
        return None
    if "分歧" in label and "共识" not in label:
        return "split"
    if "共识" in label:
        return "consensus"
    if "分歧" in label:
        return "split"
    return None


def parse_aggregated_report(report_path):
    """从 aggregated-report.md 解析判定与卡片语义文案。

    兼容现有李四版式（总览表判定列 + ### N. 维度 —— … + **判定**/**分歧归因分析**），
    以及更早的 ✅/⚠️ 分节写法。
    返回 (verdict, consensus_notes, split_notes)。
    """
    if not os.path.isfile(report_path):
        die(
            f"综合分析报告不存在: {report_path}\n"
            f"看板语义（共识/分歧判定与卡片）必须来自同目录 aggregated-report.md。",
            1,
        )

    with open(report_path, "r", encoding="utf-8") as f:
        text = f.read()
    verdict = {}
    consensus_notes = {}
    split_notes = {}

    # 1) 总览表：维度行，取最后一个含共识/分歧的单元格
    for line in text.splitlines():
        m = re.match(
            r"^\|\s*(目标达成|专业能力|协作沟通|责任心|学习成长)\s*\|(.+)\|\s*$",
            line,
        )
        if not m:
            continue
        cn, rest = m.group(1), m.group(2)
        key = DIM_CN_TO_KEY[cn]
        decided = None
        for cell in [c.strip() for c in rest.split("|")]:
            v = _label_to_verdict(cell)
            if v:
                decided = v
        if decided:
            verdict[key] = decided

    # 2) 分节：### 1. 目标达成 —— … / ### ✅ 共识 · 目标达成 / ### ⚠️ 分歧点 …
    header_re = re.compile(
        r"^###\s+(?:\d+\.\s*)?(?:✅|⚠️|🔶)?\s*"
        r"(?:共识点\s*\d+[：:]|分歧点\s*\d+[：:]|"
        r"共识\s*[·•.\-—]\s*|分歧\s*[·•.\-—]\s*)?"
        r"(目标达成|专业能力|协作沟通|责任心|学习成长)"
        r"(?:\s*[—\-–]+\s*(.+))?$",
        re.M,
    )
    matches = list(header_re.finditer(text))
    for i, m in enumerate(matches):
        cn = m.group(1)
        key = DIM_CN_TO_KEY[cn]
        trail = m.group(2) or ""
        header = m.group(0)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        decided = _label_to_verdict(header + " " + trail)
        if decided and key not in verdict:
            verdict[key] = decided
        elif decided:
            # 分节标题可覆盖总览（更贴近章节归属）
            verdict[key] = decided

        # 语义摘要：共识优先「判定」；分歧优先「分歧归因分析」并多取几段
        note = ""
        prefer = (
            ("分歧归因分析", "归因分析", "判定", "结论")
            if (verdict.get(key) == "split" or "分歧" in header)
            else ("判定", "结论", "统一叙事", "归因分析")
        )
        for label in prefer:
            if label in ("分歧归因分析", "归因分析"):
                nm = re.search(
                    rf"\*\*{label}[：:]?\*\*[：:]*\s*(.+?)"
                    rf"(?=\n\*\*建议|\n\*\*需要探讨|\n###|\n##|\Z)",
                    block,
                    re.S,
                )
            else:
                nm = re.search(
                    rf"\*\*{label}[：:]?\*\*[：:]*\s*(.+?)"
                    rf"(?=\n\n|\n\*\*|\n###|\n##|\Z)",
                    block,
                    re.S,
                )
            if nm:
                note = _clean_md(nm.group(1))
                if len(note) >= 8:
                    break
        if not note:
            # 首个足够长的非表格段落
            for para in re.split(r"\n\s*\n", block):
                para = _clean_md(re.sub(r"^\|.+", "", para, flags=re.M))
                if len(para) >= 20 and not para.startswith(("#", "各视角", "建议")):
                    note = para[:420]
                    break

        if not note:
            continue
        if verdict.get(key) == "split":
            title_bit = trail.split("，")[0].strip() if trail else ""
            title_bit = re.sub(r"[⚠️✅🔶]", "", title_bit).strip(" —-")
            title = f"{cn} — {title_bit[:24]}" if title_bit else cn
            if len(title) > 36:
                title = title[:35] + "…"
            split_notes[key] = {"title": title, "body": note[:420]}
        else:
            consensus_notes[key] = note[:420]

    if len(verdict) < 5:
        die(
            f"未能从综合分析报告解析出完整五维度判定: {report_path}\n"
            f"已解析: {verdict}",
            1,
        )
    if not consensus_notes and not split_notes:
        die(
            f"综合分析报告缺少可展示的语义摘要（判定/归因）: {report_path}",
            1,
        )
    return verdict, consensus_notes, split_notes


def main():
    if len(sys.argv) < 2:
        print(
            "用法: python3 build_dashboard.py "
            "<person_dir|aggregated_json> [out_html] [verdict_json]",
            file=sys.stderr,
        )
        sys.exit(2)

    out_arg = sys.argv[2] if len(sys.argv) > 2 else None
    verdict_arg = sys.argv[3] if len(sys.argv) > 3 else None
    data_path, report_path, out_path, person_dir = resolve_paths(
        sys.argv[1], out_arg
    )
    # ---- 1. 读聚合数据（唯一数据基准，记录 md5 防漂移）----
    with open(data_path, "rb") as f:
        raw_bytes = f.read()
    data_md5 = hashlib.md5(raw_bytes).hexdigest()
    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        die(f"聚合数据 JSON 无法解析：{e}")

    # 数据完整性检查——看板依赖 perspectives 段
    if "perspectives" not in data:
        die("聚合数据缺 perspectives 段，不是合法的 aggregated-data.json")
    for p in PERSP_ORDER:
        if p not in data["perspectives"]:
            die(f"聚合数据缺 {p} 视角，无法生成四视角看板")

    # 各视角各维度平均分（直取，不计算）
    persp_avg = {}
    for p in PERSP_ORDER:
        persp_avg[p] = [data["perspectives"][p]["dimensions"][d]["average"]
                        for d in DIM_KEYS]

    # ---- 2. matplotlib 渲染雷达对比图 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    # matplotlib 渲染中文：标题/轴标签/图例是三条独立渲染路径，rcParams 不
    # 保证全覆盖。可靠做法是构造一个 FontProperties 对象，对每处文字显式传入。
    cjk_font = None
    # Linux 常见：Source Han Sans SC / Noto Sans CJK / 文泉驿；macOS：黑体/宋体/苹方
    for fname in [
        "Source Han Sans SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Songti SC",
        "STHeiti",
        "Heiti SC",
        "STSong",
        "PingFang SC",
        "Arial Unicode MS",
        "Microsoft YaHei",
        "Microsoft YaHei UI",
        "SimHei",
    ]:
        try:
            fpath = font_manager.findfont(fname, fallback_to_default=False)
            # findfont 找不到时会回落到 DejaVu，这里再过滤一次
            if not fpath or "DejaVu" in fpath:
                continue
            cjk_font = font_manager.FontProperties(fname=fpath)
            plt.rcParams["font.sans-serif"] = [fname]
            plt.rcParams["font.family"] = "sans-serif"
            break
        except Exception:
            continue
    # 直接按文件路径兜底（本机手动安装的字体）
    if cjk_font is None:
        for fpath in [
            "/usr/local/share/fonts/chinese/SourceHanSansSC-Regular.otf",
            "/usr/share/fonts/opentype/chinese/SourceHanSansSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            os.path.expanduser("~/.fonts/MicrosoftYaHei.ttc"),
            "/mnt/c/Windows/Fonts/msyh.ttc",
        ]:
            if os.path.isfile(fpath):
                try:
                    font_manager.fontManager.addfont(fpath)
                except Exception:
                    pass
                cjk_font = font_manager.FontProperties(fname=fpath)
                break
    plt.rcParams["axes.unicode_minus"] = False
    if cjk_font is None:
        print("⚠️ 未找到中文字体，雷达图中文可能显示为方块", file=sys.stderr)
    else:
        print(f"   中文字体：{cjk_font.get_name()} ({cjk_font.get_file()})")

    labels = [DIM_CN[d] for d in DIM_KEYS]
    N = len(labels)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]

    fig = plt.figure(figsize=(7.8, 8.2), dpi=130)
    ax = plt.subplot(111, polar=True)
    # 极坐标图不能用 tight_layout（维度标签会伸出坐标轴范围，算不准导致
    # 标题与标签重叠）。改用手动 set_position 留白 + fig.suptitle。
    ax.set_position([0.12, 0.12, 0.76, 0.70])
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=13, fontproperties=cjk_font)
    ax.tick_params(axis="x", pad=10)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=9, color="#888")
    ax.grid(color="#d0d0d0", linewidth=0.8)

    for p in PERSP_ORDER:
        vals = persp_avg[p] + persp_avg[p][:1]
        ax.plot(angles, vals, linewidth=2.2, label=PERSP_CN[p],
                color=PERSP_COLOR[p])
        ax.fill(angles, vals, alpha=0.08, color=PERSP_COLOR[p])

    leg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=4,
                    fontsize=12, frameon=False, handletextpad=0.4,
                    columnspacing=1.6, prop=cjk_font)
    for txt in leg.get_texts():
        txt.set_fontproperties(cjk_font)
        txt.set_fontsize(13)
    fig.suptitle("四视角 × 五维度 评分雷达对比", fontsize=16, y=0.96,
                 fontproperties=cjk_font)

    buf = io.BytesIO()
    plt.savefig(buf, format="png")  # 不加 bbox_inches=tight，否则裁掉手动留白
    plt.close(fig)
    radar_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    # ---- 3. 维度分类（共识/分歧）----
    # 评分/极差仍来自 JSON；语义判定与卡片文案必须来自 aggregated-report.md。
    report_verdict, consensus_notes, split_notes = parse_aggregated_report(
        report_path
    )
    REPORT_VERDICT = dict(report_verdict)
    verdict_source = "aggregated-report.md"
    divergence = data.get("divergence", {})

    if verdict_arg:
        if not os.path.isfile(verdict_arg):
            die(f"verdict_json 不存在: {verdict_arg}", 2)
        with open(verdict_arg, "r", encoding="utf-8") as f:
            REPORT_VERDICT.update(json.load(f))
        verdict_source = f"verdict_json:{os.path.basename(verdict_arg)}"

    dim_rows = []
    for d in DIM_KEYS:
        avgs = [data["perspectives"][p]["dimensions"][d]["average"]
                for p in PERSP_ORDER]
        if d in divergence:
            rng = divergence[d]["perspective_range"]
        else:
            # 兼容旧版无 divergence 段的聚合数据：现场算极差兜底
            rng = round(max(avgs) - min(avgs), 2)
        is_split = REPORT_VERDICT.get(d, "consensus") == "split"
        dim_rows.append({"key": d, "cn": DIM_CN[d], "avgs": avgs,
                         "range": rng, "is_split": is_split})

    consensus = [r for r in dim_rows if not r["is_split"]]
    splits = [r for r in dim_rows if r["is_split"]]

    # 平级内部明细（协作沟通维度）
    peer_collab = data["perspectives"]["peer"]["dimensions"]["collaboration"]["scores"]
    peer_reviewers = [r["alias"]
                      for r in data["perspectives"]["peer"]["reviewers"]]

    # ---- 4. 拼 HTML ----
    def score_cell(v):
        color = ("#059669" if v >= 4.5 else
                 ("#2563eb" if v >= 3.5 else
                  ("#d97706" if v >= 2.5 else "#dc2626")))
        return f'<td style="color:{color};font-weight:600">{v:.2f}</td>'

    dim_table_rows = ""
    for r in dim_rows:
        tag = ('<span class="tag split">分歧</span>' if r["is_split"]
               else '<span class="tag consensus">共识</span>')
        cells = "".join(score_cell(v) for v in r["avgs"])
        dim_table_rows += (f"<tr><td class='dim'>{r['cn']}</td>{cells}"
                           f"<td>{r['range']:.2f}</td><td>{tag}</td></tr>\n")

    peer_rows = ""
    for alias, sc in zip(peer_reviewers, peer_collab):
        peer_rows += f"<tr><td>{alias}</td>{score_cell(float(sc))}</tr>\n"

    consensus_cards = ""
    for r in consensus:
        note = consensus_notes.get(
            r["key"],
            "综合分析判定为共识（各视角核心叙事一致）。",
        )
        consensus_cards += f"""
    <div class="card consensus-card">
      <div class="card-h"><span class="dot c"></span>{r['cn']}<span class="range">极差 {r['range']:.2f}</span></div>
      <p>{note}</p>
    </div>"""

    split_cards = ""
    for r in splits:
        n = split_notes.get(
            r["key"],
            {
                "title": r["cn"],
                "body": "综合分析判定为分歧，详见本页分数对照。",
            },
        )
        avgs_str = " / ".join(f"{PERSP_CN[p]} {v:.2f}"
                              for p, v in zip(PERSP_ORDER, r["avgs"]))
        split_cards += f"""
    <div class="card split-card">
      <div class="card-h"><span class="dot s"></span>{n['title']}<span class="range">极差 {r['range']:.2f}</span></div>
      <p class="avgs">{avgs_str}</p>
      <p>{n['body']}</p>
    </div>"""

    subject = data.get("subject", "")
    subject_role = data.get("subject_role", "")
    period = data.get("period", "")
    total = data.get("total_feedback_count", 0)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject} 360 反馈聚合看板</title>
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

  <h1>{subject} · {period} 360 反馈聚合看板</h1>
  <div class="sub">{subject_role} · 半年度考核</div>

  <div class="meta">
    <span><b>评估对象</b>　{subject}</span>
    <span><b>反馈来源</b>　{total} 份（上级 1 + 平级 3 + 下属 2 + 自评 1）</span>
    <span><b>考核周期</b>　{period}</span>
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
    <p class="note">「极差」直取聚合 JSON。对照表「判定」与下方共识/分歧卡片语义来自同目录综合分析报告，不照搬机械极差信号。</p>

    <div class="peer-detail">
      <h3>平级内部明细 · 协作沟通维度（平均分掩盖了内部结构）</h3>
      <table>
        <thead><tr><th>平级评估人</th><th>协作沟通评分</th></tr></thead>
        <tbody>
        {peer_rows}
        </tbody>
      </table>
      <p class="note">同组与跨组评分分化——协作分歧的本质是「对内 vs 对外」，单看平级平均分发现不了。</p>
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

  <section>
    <h2>五、本看板的用途（供面谈 review）</h2>
    <p>本看板把 {total} 份 360 反馈聚合成一张可视化视图，供绩效面谈与校准会作为<b>输入材料</b>使用。
    它帮主管把功课做足——读透多源反馈、找全分歧点、把雷达对比摆清楚；但「绩效定级」这个对个人权益有重大影响的决定，
    留给「直接主管初评 → 隔级主管复核 → 校准会确认」三级人工流程。</p>
    <div class="review-stamp">本看板为面谈输入材料 · 最终绩效定级由人工三级流程确定 · AI 不出评级</div>
  </section>

  <footer>
    评估对象目录：{os.path.basename(person_dir)} ·
    数据来源：aggregated-data.json（md5 {data_md5[:12]}） ·
    判定来源：{verdict_source} ·
    看板不重新计算分数
  </footer>

</div>
</body>
</html>
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 看板生成：{out_path}")
    print(f"   人员目录：{person_dir}")
    print(f"   数据基准：{data_path}（md5 {data_md5}）")
    print(f"   综合报告：{report_path}")
    print(f"   判定来源：{verdict_source}")
    print(f"   评估对象：{subject}（{total} 份反馈）")
    print(f"   共识维度：{', '.join(r['cn'] for r in consensus)}")
    print(f"   分歧维度：{', '.join(r['cn'] for r in splits)}")
    print(f"   雷达图 base64 长度：{len(radar_b64)} 字符（PNG 内嵌，单文件自包含）")
    print(f"   HTML 文件大小：{os.path.getsize(out_path)} 字节")
    sys.exit(0)


if __name__ == "__main__":
    main()
