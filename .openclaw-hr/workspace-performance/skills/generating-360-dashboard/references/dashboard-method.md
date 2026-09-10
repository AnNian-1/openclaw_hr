# 360 看板生成细则

> generating-360-dashboard Skill 的看板生成细则。

## 1. 输入

| 文件 | 用途 |
|---|---|
| `aggregated-data.json` | 评分、极差、雷达（必有） |
| `aggregated-report.md` | 共识/分歧判定与卡片语义（必有；缺则失败） |

产出：同目录 `report.html`（语义已吸入，自包含）。

## 2. 判定口径

- **极差列**：直取 JSON `divergence.perspective_range`
- **判定列 / 卡片**：解析报告总览表与分节（含「边界共识」→ 共识、「真实分歧」→ 分歧）
- **不**照搬 JSON `suspected_split`
- 第三参 `verdict_json` 若传入则**忽略**（兼容旧签名，判定仍只读报告）

## 3. 卡片文案

- 共识：优先报告「**判定**」段
- 分歧：优先「**分歧归因分析**」段（吸入 HTML，不外链 md）
- 评价人只出 领导N / 同事N / 下属N / 自评

## 4. Canvas

canvas-id：`feedback-360-<slug>`；见 `canvas-publishing.md`。
