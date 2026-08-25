---
name: generating-360-dashboard
description: Generate a single-file HTML dashboard from aggregated 360 feedback JSON scores plus sibling aggregated-report.md semantics, then optionally publish to OpenClaw Canvas. Use when aggregated-data.json needs a visual review board. Scores and ranges come only from aggregated-data.json; consensus/divergence verdicts and card narratives must come from aggregated-report.md and are embedded into the self-contained HTML. Never recomputes scores or outputs a performance grade.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# generating-360-dashboard

把 360 反馈聚合结果渲染成单文件 HTML 看板，并发布到 OpenClaw Canvas。

## 输入分工

| 来源 | 用途 |
|---|---|
| `aggregated-data.json` | 评分、极差、雷达图（数字只取不算） |
| `aggregated-report.md` | **语义必读**：共识/分歧判定 + 卡片文案（吸入 HTML，页面不外链） |

缺综合分析报告时脚本直接失败——看板语义不允许只用机械极差凑。

## 路径约定

```
feedback-360/source_feedback/<slug>/
  ├── aggregated-data.json     # 评分基准
  ├── aggregated-report.md     # 语义判定（必有）
  └── report.html              # 本 Skill 产出
```

## 工作流程

```bash
bash skills/generating-360-dashboard/scripts/build_dashboard.sh \
  feedback-360/source_feedback/<slug> --publish --force
```

canvas-id：`feedback-360-<slug>`；浏览器用 18999。

## 关键规则

- **数字只取不算**（JSON）。
- **语义只取报告**（`aggregated-report.md`），判定列与卡片不照搬机械 `suspected_split`。
- **看板自包含**：报告语义写入 HTML，不引导读者再打开 md。
- **绝不输出绩效评级**。
