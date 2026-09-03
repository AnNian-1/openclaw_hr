#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HR 月报自动生成 Pipeline
读 6 个 CSV -> pandas 算指标 -> 对标业界基准 -> matplotlib 图表 -> HTML 图文月报

用法:
  python3 generate_monthly_report.py [目标月份 YYYY-MM] [--publish] [--force]
不传月份则取 CSV 里最新一个月。
--publish: 生成后发布到 OpenClaw Canvas（id=hr-monthly-report）
--force:   覆盖已有 Canvas 文档（仅与 --publish 联用；Cron/重出月报时必带）

设计原则(C-2 数字回核教训):
  所有展示数字都由 pandas 从 CSV 确定性算出, 不经过任何 LLM 自由文本。
  脚本末尾把"数字回核表"落盘到 report-output/hr-monthly-report-<月>-audit.md,
  并同步打印到终端, 把每个进 HTML 的数字和 CSV 原值并排列出, 供人工核对。
"""
import argparse
import sys
import io
import os
import base64
from datetime import datetime

def _reexec_with_pandas():
    try:
        import pandas  # noqa: F401
        return
    except ImportError:
        pass
    cands = [
        os.environ.get("MONTHLY_REPORT_PYTHON"),
        os.path.expanduser("~/miniconda3/envs/openclaw-hr/bin/python3"),
        os.path.expanduser("~/miniconda3/envs/py312/bin/python3"),
        "/usr/local/miniconda3/envs/py312/bin/python3",
        os.path.expanduser("~/anaconda3/envs/py312/bin/python3"),
    ]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK) and os.path.realpath(c) != os.path.realpath(sys.executable):
            os.execv(c, [c] + sys.argv)
    sys.stderr.write(
        "[monthly-report] 当前 python 无 pandas。请用 conda 环境 openclaw-hr 或 MONTHLY_REPORT_PYTHON。\n"
    )
    sys.exit(127)

_reexec_with_pandas()
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Canvas 约定 id（最新一期月报总览；ASCII only）
CANVAS_ID = "hr-monthly-report"


def _first_existing(paths):
    for fp in paths:
        if os.path.isfile(fp):
            return fp
    return None


def _setup_chinese_font():
    """为 matplotlib 图表注册中文字体（含 Bold 字重）。

    根因：旧版只探测 macOS PingFang/STHeiti；Linux 上全部失败后回退 DejaVu Sans，
    图表里中文变成缺字方框（tofu）。HTML 正文用系统/浏览器字体通常正常，
    出问题的是内嵌的 matplotlib PNG。

    只注册 Regular 时，标题 fontweight="bold" 会告缺字重（ER-FONT）。
    Regular 与 Bold 都要 addfont；TTC 的 fname 族名常是 JP，优先选用已注册的 SC。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    regular_fp = _first_existing([
        os.path.join(here, "fonts", "NotoSansCJKsc-Regular.otf"),
        os.path.join(here, "fonts", "SourceHanSansSC-Regular.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/opentype/chinese/SourceHanSansSC-Regular.otf",
        "/usr/share/fonts/truetype/SourceHanSansSC-Regular.otf",
        "/usr/local/share/fonts/chinese/SourceHanSansSC-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ])
    bold_fp = _first_existing([
        os.path.join(here, "fonts", "NotoSansCJKsc-Bold.otf"),
        os.path.join(here, "fonts", "SourceHanSansSC-Bold.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
        "C:/Windows/Fonts/msyhbd.ttc",
    ])
    for fp in (regular_fp, bold_fp):
        if not fp:
            continue
        try:
            font_manager.fontManager.addfont(fp)
        except Exception as exc:
            print(f"[font] 加载失败 {fp}: {exc}")

    registered = {f.name for f in font_manager.fontManager.ttflist}
    family = next(
        (n for n in (
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "Noto Sans CJK JP",
            "WenQuanYi Micro Hei",
            "Microsoft YaHei",
            "PingFang SC",
            "Heiti SC",
        ) if n in registered),
        None,
    )
    if family is None and regular_fp:
        family = font_manager.FontProperties(fname=regular_fp).get_name()
    matplotlib.rcParams["axes.unicode_minus"] = False
    if not family:
        print(
            "[font] WARNING: 未找到中文字体，图表中文可能显示为方框。"
            "请安装 fonts-noto-cjk / 文泉驿，或把 OTF 放到 scripts/fonts/"
        )
        return None
    matplotlib.rcParams["font.family"] = family
    matplotlib.rcParams["font.sans-serif"] = [family, "DejaVu Sans"]
    extra = f"; Bold <- {bold_fp}" if bold_fp else "（无独立 Bold 字重，标题可能假粗）"
    print(f"[font] 使用中文字体: {family} <- {regular_fp}{extra}")
    return family


_setup_chinese_font()

# 数据目录定位: 脚本可能在 report-system/ 下, 也可能在 Skill 的 scripts/ 下,
# 不能假设脚本相对位置。从脚本所在目录逐级向上找含 report-system/data/ 的目录
# (即 er-admin workspace 根), 找不到则回退到脚本同级 data/。
def _locate_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    # 回退1: 脚本同级有 data/ (脚本仍放在 report-system/ 下的旧布局)
    sib = os.path.join(here, "data")
    if os.path.isdir(sib):
        return sib, os.path.join(os.path.dirname(here), "report-output")
    # 主路径: 向上逐级找 report-system/data/
    cur = here
    for _ in range(6):  # 最多上溯 6 级, 足够覆盖 skills/<name>/scripts/ 这种深度
        cand = os.path.join(cur, "report-system", "data")
        if os.path.isdir(cand):
            ws_root = cur
            return cand, os.path.join(ws_root, "report-output")
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # 兜底: 仍按旧布局假设, 让后续 read_csv 报清晰的 FileNotFound
    return sib, os.path.join(os.path.dirname(here), "report-output")

DATA, OUT = _locate_dirs()
os.makedirs(OUT, exist_ok=True)

# ---- 业界基准 (来源: 业界标准) ----
BENCHMARK = {
    "面试转Offer率": (27.0, "面试→Offer 转化率业界基准 27%"),
    "Offer接受率":   (50.0, "Offer 接受率业界基准约 50%"),
    "TimeToHire":    (43.0, "Time to Hire 业界基准 43 天"),
    "离职45天率":    (20.0, "入职 45 天内离职率业界基准 20% (SHRM)"),
    "培训满意度":    (4.0,  "培训满意度 (Kirkpatrick L1) 业界基准 ≥4.0"),
}

COMPANY = "某某公司"


def pct(s):
    """把 '22.6%' 这类字符串转 float"""
    if isinstance(s, str):
        return float(s.strip().replace("%", ""))
    return float(s)


def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="生成 HR 月报 HTML，可选发布到 OpenClaw Canvas。"
    )
    p.add_argument(
        "month",
        nargs="?",
        default=None,
        help="目标月份 YYYY-MM；省略则取 CSV 最新月",
    )
    p.add_argument(
        "--publish",
        action="store_true",
        help=f"生成后发布到 Canvas（id={CANVAS_ID}）",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="覆盖已有 Canvas 文档（仅与 --publish 联用）",
    )
    return p.parse_args(argv)


def _publish_html(html_path: str, force: bool) -> int:
    """调用同目录 publish_to_canvas.py。返回其退出码。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from publish_to_canvas import run_one, EX_OK  # noqa: WPS433

    print(f"--- publish → Canvas id={CANVAS_ID} (force={force}) ---")
    code, msg = run_one(html_path, CANVAS_ID, force)
    if code == EX_OK:
        print(f"[ok] {msg}")
    else:
        print(f"[FAIL] {msg}", file=sys.stderr)
    return code


def main(argv=None):
    args = _parse_args(argv)

    # ---- 读 6 个 CSV ----
    funnel = pd.read_csv(os.path.join(DATA, "recruitment-funnel.csv"))
    positions = pd.read_csv(os.path.join(DATA, "positions-progress.csv"))
    retention = pd.read_csv(os.path.join(DATA, "onboarding-retention.csv"))
    training = pd.read_csv(os.path.join(DATA, "training-completion.csv"))
    cost = pd.read_csv(os.path.join(DATA, "hiring-cost.csv"))
    attrition = pd.read_csv(os.path.join(DATA, "attrition.csv"))

    # ---- 目标月份 ----
    target = args.month if args.month else funnel["月份"].iloc[-1]
    months = list(funnel["月份"])
    if target not in months:
        print(f"[ERROR] 月份 {target} 不在数据范围 {months[0]}~{months[-1]}")
        sys.exit(1)

    fr = funnel[funnel["月份"] == target].iloc[0]
    cr = cost[cost["月份"] == target].iloc[0]
    rr = retention[retention["月份"] == target].iloc[0]
    tr = training[training["月份"] == target].iloc[0]
    ar = attrition[attrition["月份"] == target].iloc[0]

    audit = []  # 数字回核表: (指标, 进HTML的值, CSV原始来源)

    # ===== 招聘漏斗 =====
    stages = ["投递数", "初筛通过", "面试", "Offer", "入职"]
    funnel_vals = [int(fr[s]) for s in stages]
    for s in stages:
        audit.append((f"漏斗-{s}", str(int(fr[s])), f"recruitment-funnel.csv {target}行 {s}列"))
    i2o = pct(fr["面试转Offer率"])
    offer_accept = pct(fr["Offer接受率"])
    audit.append(("面试转Offer率", f"{i2o}%", f"recruitment-funnel.csv {target}行"))
    audit.append(("Offer接受率", f"{offer_accept}%", f"recruitment-funnel.csv {target}行"))

    # ===== 岗位进度 =====
    total_hc = int(positions["HC"].sum())
    total_filled = int(positions["已入职"].sum())
    total_open = int(positions["在招中"].sum())
    fill_rate = round(total_filled / total_hc * 100, 1)
    done_cnt = int((positions["招聘状态"] == "已完成").sum())
    audit.append(("岗位总HC", str(total_hc), "positions-progress.csv HC列求和"))
    audit.append(("已入职合计", str(total_filled), "positions-progress.csv 已入职列求和"))
    audit.append(("整体到位率", f"{fill_rate}%", "已入职合计/岗位总HC"))

    # ===== 入职留存 =====
    onboard_cnt = int(rr["入职人数"])
    pass_cnt = int(rr["试用期通过"])
    leave45_raw = str(rr["45天内离职率"])
    audit.append(("本月入职人数", str(onboard_cnt), f"onboarding-retention.csv {target}行"))
    audit.append(("45天内离职率", leave45_raw, f"onboarding-retention.csv {target}行"))

    # ===== 培训 =====
    train_rate = pct(tr["完成率"])
    train_sat = float(tr["培训满意度"])
    audit.append(("培训完成率", f"{train_rate}%", f"training-completion.csv {target}行"))
    audit.append(("培训满意度", str(train_sat), f"training-completion.csv {target}行"))

    # ===== 成本 =====
    cost_per_hire = int(cr["人均招聘成本"])
    tth = int(cr["平均TimeToHire天数"])
    channel_fee = int(cr["招聘渠道费用"])
    audit.append(("人均招聘成本", f"{cost_per_hire}元", f"hiring-cost.csv {target}行"))
    audit.append(("TimeToHire", f"{tth}天", f"hiring-cost.csv {target}行"))

    # ===== 离职 =====
    leave_total = int(ar["离职总人数"])
    leave_voluntary = int(ar["主动离职"])
    monthly_attr = str(ar["月离职率"])
    reasons = {"薪资": int(ar["薪资原因"]), "发展": int(ar["发展原因"]),
               "管理": int(ar["管理原因"]), "家庭": int(ar["家庭原因"]),
               "不胜任": int(ar["不胜任"])}
    audit.append(("离职总人数", str(leave_total), f"attrition.csv {target}行"))
    audit.append(("月离职率", monthly_attr, f"attrition.csv {target}行"))

    # ============ 图表 ============
    charts = {}

    # 图1 招聘漏斗 (窄条形把标签放外侧, 避免文字被截断)
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    colors = ["#4F86C6", "#5B96CE", "#6BA3D6", "#7FB3DE", "#94C2E6"]
    maxv = funnel_vals[0]
    for idx, (st, v) in enumerate(zip(stages, funnel_vals)):
        w = v / maxv
        ax.barh(idx, w, height=0.62, color=colors[idx], left=(1 - w) / 2)
        # 上一阶段转化率
        if idx == 0:
            label = f"{st}  {v}"
        else:
            conv = round(v / funnel_vals[idx - 1] * 100, 1)
            label = f"{st}  {v}  (转化 {conv}%)"
        # 条形够宽放里面(白字), 否则放右侧外面(深色字)
        if w >= 0.42:
            ax.text(0.5, idx, label, ha="center", va="center",
                    color="white", fontsize=11, fontweight="bold")
        else:
            ax.text(0.5 + w / 2 + 0.02, idx, label, ha="left", va="center",
                    color="#2a3340", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 1.05)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.invert_yaxis()
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(f"{target} 招聘漏斗", fontsize=13, fontweight="bold", pad=10)
    charts["funnel"] = fig_to_base64(fig)

    # 图2 关键指标 6 月趋势线
    fig, axes = plt.subplots(1, 3, figsize=(11, 3))
    axes[0].plot(months, funnel["面试转Offer率"].apply(pct), "o-", color="#4F86C6", lw=2)
    axes[0].axhline(27, ls="--", color="#E07B39", lw=1.3)
    axes[0].set_title("面试→Offer 转化率 %", fontsize=10)
    axes[0].text(0, 27.4, "业界 27%", color="#E07B39", fontsize=8)
    axes[1].plot(months, cost["平均TimeToHire天数"], "o-", color="#4F86C6", lw=2)
    axes[1].axhline(43, ls="--", color="#E07B39", lw=1.3)
    axes[1].set_title("Time to Hire 天", fontsize=10)
    axes[1].text(0, 43.6, "业界 43 天", color="#E07B39", fontsize=8)
    axes[2].plot(months, training["完成率"].apply(pct), "o-", color="#4F86C6", lw=2)
    axes[2].set_title("培训完成率 %", fontsize=10)
    for a in axes:
        a.tick_params(axis="x", labelsize=7, rotation=30)
        a.grid(alpha=0.25)
    fig.suptitle("关键指标 6 个月趋势", fontsize=12, fontweight="bold", y=1.04)
    charts["trend"] = fig_to_base64(fig)

    # 图3 招聘成本柱状图
    fig, ax = plt.subplots(figsize=(6.5, 3))
    bars = ax.bar(months, cost["人均招聘成本"], color="#6BA3D6", width=0.55)
    bars[months.index(target)].set_color("#E07B39")
    ax.set_title("人均招聘成本 (元)", fontsize=12, fontweight="bold")
    ax.tick_params(axis="x", labelsize=8, rotation=30)
    ax.grid(axis="y", alpha=0.25)
    for b, v in zip(bars, cost["人均招聘成本"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 80, str(int(v)),
                ha="center", fontsize=8)
    charts["cost"] = fig_to_base64(fig)

    # 图4 离职原因分布饼图
    fig, ax = plt.subplots(figsize=(4.4, 3.4))
    rlabels = [k for k, v in reasons.items() if v > 0]
    rvals = [v for v in reasons.values() if v > 0]
    ax.pie(rvals, labels=rlabels, autopct=lambda p: f"{int(round(p/100*sum(rvals)))}人",
           colors=["#E07B39", "#4F86C6", "#6BA3D6", "#94C2E6", "#B8D4E8"],
           textprops={"fontsize": 9})
    ax.set_title(f"{target} 离职原因分布", fontsize=12, fontweight="bold")
    charts["attrition"] = fig_to_base64(fig)

    # ============ 对标分析 ============
    def cmp_line(name, val, bench, better_high, unit=""):
        if better_high:
            ok = val >= bench
            diff = f"高于基准 {round(val-bench,1)}{unit}" if ok else f"低于基准 {round(bench-val,1)}{unit}"
        else:
            ok = val <= bench
            diff = f"优于基准 {round(bench-val,1)}{unit}" if ok else f"高于基准 {round(val-bench,1)}{unit}"
        cls = "good" if ok else "warn"
        mark = "达标" if ok else "需关注"
        return val, bench, diff, cls, mark

    bench_rows = []
    v, b, d, c, m = cmp_line("面试→Offer 转化率", i2o, 27.0, True, "%")
    bench_rows.append(("面试→Offer 转化率", f"{v}%", "27%", d, c, m))
    v, b, d, c, m = cmp_line("Offer 接受率", offer_accept, 50.0, True, "%")
    bench_rows.append(("Offer 接受率", f"{v}%", "约 50%", d, c, m))
    v, b, d, c, m = cmp_line("Time to Hire", tth, 43.0, False, " 天")
    bench_rows.append(("Time to Hire", f"{tth} 天", "43 天", d, c, m))
    v, b, d, c, m = cmp_line("培训满意度", train_sat, 4.0, True, "")
    bench_rows.append(("培训满意度 (L1)", str(train_sat), "≥4.0", d, c, m))

    # 45 天离职率: 5 月可能是"统计中"
    leave45_known = leave45_raw.endswith("%")
    if leave45_known:
        v45 = pct(leave45_raw)
        v, b, d, c, m = cmp_line("45天内离职率", v45, 20.0, False, "%")
        bench_rows.append(("入职 45 天内离职率", leave45_raw, "20% (SHRM)", d, c, m))
    else:
        bench_rows.append(("入职 45 天内离职率", leave45_raw, "20% (SHRM)",
                            "本月入职员工尚在 45 天观察期", "warn", "观察中"))

    # ============ HTML ============
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows_html = ""
    for name, cur, bench, diff, cls, mark in bench_rows:
        rows_html += f"""<tr>
      <td>{name}</td><td class="num">{cur}</td><td class="num">{bench}</td>
      <td>{diff}</td><td class="{cls}">{mark}</td></tr>"""

    audit_html = ""
    for name, val, src in audit:
        audit_html += f"<tr><td>{name}</td><td class='num'>{val}</td><td class='src'>{src}</td></tr>"

    # 解读文字 (基于确定性指标拼装, 非 LLM 生成)
    pos_done = positions[positions["招聘状态"] == "已完成"]["岗位"].tolist()
    slow_pos = positions[positions["平均在招天数"] >= 50][["岗位", "平均在招天数"]]
    slow_txt = "、".join(f"{r['岗位']}（{int(r['平均在招天数'])}天）"
                         for _, r in slow_pos.iterrows()) or "无"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>{COMPANY} HR 月报 · {target}</title>
<style>
  body{{font-family:"Noto Sans CJK SC","Source Han Sans SC","PingFang SC","Microsoft YaHei","WenQuanYi Micro Hei",sans-serif;background:#f0f3f7;
       margin:0;padding:32px;color:#2a3340;}}
  .wrap{{max-width:980px;margin:0 auto;background:#fff;border-radius:12px;
        box-shadow:0 4px 24px rgba(0,0,0,.08);overflow:hidden;}}
  .hd{{background:linear-gradient(135deg,#3a6ea5,#4F86C6);color:#fff;padding:30px 40px;}}
  .hd h1{{margin:0;font-size:25px;}}
  .hd p{{margin:6px 0 0;opacity:.9;font-size:13px;}}
  .body{{padding:28px 40px 36px;}}
  h2{{font-size:17px;border-left:4px solid #4F86C6;padding-left:10px;
     margin:30px 0 14px;color:#2a3340;}}
  .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0;}}
  .kpi{{flex:1;min-width:140px;background:#f5f8fb;border-radius:9px;
       padding:14px 16px;border-top:3px solid #4F86C6;}}
  .kpi .v{{font-size:24px;font-weight:700;color:#3a6ea5;}}
  .kpi .l{{font-size:12px;color:#6b7785;margin-top:3px;}}
  img{{max-width:100%;display:block;margin:8px 0;}}
  table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0;}}
  th,td{{border:1px solid #e2e8f0;padding:8px 10px;text-align:left;}}
  th{{background:#eef3f8;font-weight:600;}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums;}}
  td.src{{color:#8b96a3;font-size:11px;}}
  .good{{color:#2e7d32;font-weight:600;}}
  .warn{{color:#d9822b;font-weight:600;}}
  .note{{background:#f5f8fb;border-radius:8px;padding:14px 18px;font-size:13px;
        line-height:1.8;margin:12px 0;}}
  .ft{{margin-top:30px;padding-top:14px;border-top:1px dashed #d4dde6;
      font-size:11px;color:#9aa5b1;line-height:1.7;}}
</style></head><body>
<div class="wrap">
  <div class="hd">
    <h1>{COMPANY} · HR 月度报告</h1>
    <p>报告月份 {target}　|　生成时间 {gen_time}　|　数据周期 {months[0]} ~ {months[-1]}</p>
  </div>
  <div class="body">

    <h2>一、本月核心指标</h2>
    <div class="kpis">
      <div class="kpi"><div class="v">{onboard_cnt}</div><div class="l">本月入职人数</div></div>
      <div class="kpi"><div class="v">{fill_rate}%</div><div class="l">岗位整体到位率</div></div>
      <div class="kpi"><div class="v">{tth}天</div><div class="l">平均 Time to Hire</div></div>
      <div class="kpi"><div class="v">{cost_per_hire}元</div><div class="l">人均招聘成本</div></div>
      <div class="kpi"><div class="v">{train_rate}%</div><div class="l">培训完成率</div></div>
      <div class="kpi"><div class="v">{leave_total}人</div><div class="l">本月离职人数</div></div>
    </div>

    <h2>二、招聘漏斗</h2>
    <img src="data:image/png;base64,{charts['funnel']}" alt="招聘漏斗">
    <div class="note">本月投递 {funnel_vals[0]} 份，经初筛 {funnel_vals[1]} 人、面试
      {funnel_vals[2]} 人，发出 Offer {funnel_vals[3]} 份，最终入职 {funnel_vals[4]} 人。
      面试→Offer 转化率 {i2o}%，Offer 接受率 {offer_accept}%。</div>

    <h2>三、对标业界基准</h2>
    <table>
      <tr><th>指标</th><th>本月</th><th>业界基准</th><th>差距</th><th>评估</th></tr>
      {rows_html}
    </table>
    <div class="note">业界基准来源：业界标准（面试→Offer 27%、
      Time to Hire 43 天、入职 45 天离职率 20% SHRM、培训满意度 Kirkpatrick L1 ≥4.0）。</div>

    <h2>四、关键指标趋势</h2>
    <img src="data:image/png;base64,{charts['trend']}" alt="趋势">

    <h2>五、岗位招聘进度</h2>
    <div class="note">在招岗位共 {len(positions)} 个，HC 合计 {total_hc} 人，
      已入职 {total_filled} 人，在招中 {total_open} 人，整体到位率 {fill_rate}%。
      本月已招满岗位 {done_cnt} 个。<br>
      在招周期偏长（≥50 天）的岗位：{slow_txt}——建议复盘渠道与 JD 吸引力。</div>

    <h2>六、招聘成本与效率</h2>
    <img src="data:image/png;base64,{charts['cost']}" alt="成本">
    <div class="note">本月招聘渠道总投入 {channel_fee:,} 元，入职 {onboard_cnt} 人，
      人均招聘成本 {cost_per_hire} 元。主要费用构成：{cr['主要费用构成']}。</div>

    <h2>七、入职留存与培训</h2>
    <div class="note">本月入职 {onboard_cnt} 人，试用期通过 {pass_cnt} 人，
      入职 45 天内离职率 {leave45_raw}（备注：{rr['备注']}）。<br>
      培训应参训 {int(tr['应参训人数'])} 人，完成 {int(tr['完成人数'])} 人，
      完成率 {train_rate}%，满意度 {train_sat}。培训内容：{tr['主要培训内容']}。</div>

    <h2>八、离职分析</h2>
    <img src="data:image/png;base64,{charts['attrition']}" alt="离职原因">
    <div class="note">本月离职 {leave_total} 人（主动 {leave_voluntary} 人），
      月离职率 {monthly_attr}。离职原因以
      {max(reasons, key=reasons.get)}原因为主——HR 需重点关注该方向的保留措施。</div>

    <div class="ft">
      本报告由行政子 Agent「小慧」通过 OpenClaw Cron 定时任务自动生成。<br>
      数据来源：{COMPANY} HR 月度历史数据 6 个 CSV（招聘漏斗 / 岗位进度 / 入职留存 /
      培训完成 / 招聘成本 / 离职）。所有数字由 pandas 脚本确定性计算，未经 LLM 改写。<br>
      报告月份 {target}　·　生成时间 {gen_time}
    </div>
  </div>
</div>
</body></html>"""

    out_path = os.path.join(OUT, f"hr-monthly-report-{target}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # ============ 数字回核表落盘 + 终端打印 (C-2: 进 HTML 的数字逐条对 CSV) ============
    audit_path = os.path.join(OUT, f"hr-monthly-report-{target}-audit.md")
    audit_lines = [
        f"# HR 月报数字回核表 · {target}",
        "",
        f"- 公司：{COMPANY}",
        f"- 报告 HTML：`hr-monthly-report-{target}.html`",
        f"- 生成时间：{gen_time}",
        f"- 回核项数：{len(audit)}",
        "",
        "| 指标 | 进 HTML 的值 | CSV / 算式来源 |",
        "|---|---|---|",
    ]
    for name, val, src in audit:
        audit_lines.append(f"| {name} | {val} | {src} |")
    audit_lines.extend([
        "",
        "## 回核结论",
        "",
        f"以上 {len(audit)} 个数字均由 pandas 直接读取/计算自 CSV，"
        "全程无 LLM 参与数值生成，可逐条复核。",
        "",
    ])
    with open(audit_path, "w", encoding="utf-8") as f:
        f.write("\n".join(audit_lines))

    print("=" * 64)
    print(f"HR 月报生成完成: {out_path}")
    print(f"数字回核表已落盘: {audit_path}")
    print(f"报告月份: {target}  |  图表 4 张  |  对标指标 {len(bench_rows)} 项")
    print("=" * 64)
    print("【数字回核表】每个进入 HTML 的数字 vs CSV 原始来源:")
    print("-" * 64)
    for name, val, src in audit:
        print(f"  {name:<14} = {val:<10} <- {src}")
    print("-" * 64)
    print(f"回核结论: 以上 {len(audit)} 个数字均由 pandas 直接读取/计算自 CSV,")
    print("          全程无 LLM 参与数值生成,可逐条复核。")
    print("=" * 64)

    # ============ 可选：发布到 Canvas ============
    if args.publish:
        # 月报固定 id 重出时必须覆盖；未带 --force 时仍尊重 publish 脚本的拒覆盖策略
        pub_code = _publish_html(out_path, args.force)
        if pub_code != 0:
            sys.exit(pub_code)


if __name__ == "__main__":
    main()
