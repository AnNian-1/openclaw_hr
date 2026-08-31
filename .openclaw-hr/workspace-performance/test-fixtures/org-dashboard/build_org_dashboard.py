#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把测试夹具 JSON 渲成四模块组织看板 HTML。不调用 LLM，不产出真实评级结论。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "org-dashboard.html"
DIMS = [
    ("goal_achievement", "目标达成"),
    ("professional_skill", "专业技能"),
    ("collaboration", "协作沟通"),
    ("responsibility", "责任心"),
    ("growth", "学习成长"),
]


def heat(v: float) -> str:
    t = max(1.0, min(5.0, float(v)))
    # 1 red → 5 green
    r = int(220 - (t - 1) * 40)
    g = int(80 + (t - 1) * 35)
    b = 90
    return f"rgb({r},{g},{b})"


def main() -> int:
    ratings = json.loads((HERE / "ratings-2026-H1.json").read_text(encoding="utf-8"))
    trend = json.loads((HERE / "trend-history.json").read_text(encoding="utf-8"))
    org = json.loads((HERE / "org-map.json").read_text(encoding="utf-8"))
    dist = ratings["rating_distribution"]
    grades = ["S", "A", "B", "C", "D"]
    max_c = max(dist[g]["count"] for g in grades) or 1

    bars_a = []
    for g in grades:
        c = dist[g]["count"]
        pct = dist[g]["pct"]
        people = "、".join(dist[g]["employees"])
        w = int(c / max_c * 100)
        bars_a.append(
            f'<div class="row"><span class="g">{g}</span>'
            f'<div class="bar"><i style="width:{w}%"></i></div>'
            f'<span class="n">{c}人 {pct}%</span>'
            f'<span class="p">{people}</span></div>'
        )
    team_rows = []
    for team, counts in ratings["by_team"].items():
        cells = "".join(f"<td>{counts[g]}</td>" for g in grades)
        team_rows.append(f"<tr><th>{team}</th>{cells}</tr>")

    team_b = []
    for team, info in org["teams"].items():
        dims = info["dimensions"]
        inner = []
        for key, label in DIMS:
            v = dims[key]
            inner.append(
                f'<div class="dim"><span>{label}</span>'
                f'<b style="background:{heat(v)}">{v:.2f}</b></div>'
            )
        members = "、".join(info["members"])
        team_b.append(
            f'<article><h3>{team}</h3><p class="m">{members}</p>{"".join(inner)}</article>'
        )

    periods = trend["periods"]
    lines = []
    for key, label in DIMS:
        vals = trend["department_trend"][key]
        pts = ", ".join(f"{p}={v}" for p, v in zip(periods, vals))
        lines.append(f"<li><strong>{label}</strong> {pts}</li>")
    events = "".join(
        f"<li>{e['period']} · {e['label']}</li>" for e in trend.get("events") or []
    )

    heat_head = "".join(f"<th>{label}</th>" for _, label in DIMS)
    heat_rows = []
    last_team = None
    for person in org["heatmap_people"]:
        sep = "sep" if last_team and person["team"] != last_team else ""
        last_team = person["team"]
        cells = []
        for key, _ in DIMS:
            v = person[key]
            cells.append(f'<td style="background:{heat(v)}">{v:.2f}</td>')
        src = "360" if person.get("from_360") else "夹具"
        heat_rows.append(
            f'<tr class="{sep}"><th>{person["name"]}<small>{person["team"]} · {src}</small></th>'
            + "".join(cells)
            + "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>组织绩效看板（测试夹具）· {ratings["period"]}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
.banner{{background:#7a1f1f;color:#fff;padding:12px 16px;border-radius:8px;margin-bottom:20px}}
h1{{font-size:22px}} h2{{margin-top:32px;border-bottom:1px solid #334;padding-bottom:6px}}
.row{{display:flex;align-items:center;gap:8px;margin:6px 0}}
.g{{width:24px;font-weight:700}} .bar{{flex:1;background:#223;height:18px;border-radius:4px}}
.bar i{{display:block;height:100%;background:#5b8def;border-radius:4px}}
.n{{width:90px;font-size:13px}} .p{{flex:1;font-size:12px;color:#9ab}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #334;padding:6px 8px;text-align:center}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
article{{background:#1a222c;padding:12px;border-radius:8px}}
.dim{{display:flex;justify-content:space-between;margin:4px 0}}
.dim b{{padding:2px 8px;border-radius:4px;color:#fff;min-width:48px;text-align:center}}
.m{{color:#9ab;font-size:13px}}
small{{display:block;font-weight:400;color:#8aa}}
tr.sep th{{border-top:3px solid #5b8def}}
</style>
</head>
<body>
<div class="banner">测试夹具 · 非校准会真实结果 · 禁止用于调薪/晋升决策 · {ratings["disclaimer"]}</div>
<h1>组织绩效看板 {ratings["period"]}</h1>
<p>模块 A 评级与编造员工为夹具；模块 B/D 中张磊、李四、陈伟、王芳分数取自现有 360 聚合或方案摘录。</p>

<h2>模块 A · 等级分布</h2>
{''.join(bars_a)}
<table><thead><tr><th>团队</th><th>S</th><th>A</th><th>B</th><th>C</th><th>D</th></tr></thead>
<tbody>{''.join(team_rows)}</tbody></table>

<h2>模块 B · 团队维度对比</h2>
<div class="grid">{''.join(team_b)}</div>

<h2>模块 C · 同比环比趋势（含编造历史点）</h2>
<ul>{''.join(lines)}</ul>
<p>事件标注</p>
<ul>{events}</ul>

<h2>模块 D · 360 维度热力图</h2>
<table><thead><tr><th>员工</th>{heat_head}</tr></thead>
<tbody>{''.join(heat_rows)}</tbody></table>
</body></html>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")
    for g in grades:
        if dist[g]["count"] < 1:
            print(f"missing grade {g}", file=sys.stderr)
            return 1
    if len(trend["periods"]) < 3:
        print("need 3 periods", file=sys.stderr)
        return 1
    if len(org["heatmap_people"]) < 4:
        print("need 4 heatmap people", file=sys.stderr)
        return 1
    print("org-dashboard fixture checks: A/B/C/D ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
