# TOOLS.md — 绩效子 Agent 的工具与 Skill 清单

> 这个文件记录绩效业务专属的工具用法。Skill 定义工具「怎么用」，这里记录
> 「在本 workspace 怎么调、产出放哪、有什么调用要点」。

## 360 反馈聚合相关 Skill

360 反馈聚合是一条三层 Pipeline。每一层对应一个能力：

### aggregating-360-feedback —— 第一层 · 机械聚合

- **做什么**：从 `feedback-360/source_feedback/` 顶层任意名的 zip/rar（内含已填 DOCX）摄入，解析成 JSON，再机械聚合成按视角分组的 `aggregated-data.json`——逐维度算各视角平均分，并算出「视角平均分极差」标记疑似分歧维度。
- **什么时候用**：拿到一包 360 反馈 Word 表（或已解析的 JSON 目录），要做绩效面谈/校准会的输入材料时，这是第一步。
- **调用要点**：
  - 摄入（压缩包名随意；落盘目录由 DOCX「被评估人」决定）：
    `python3 skills/aggregating-360-feedback/scripts/ingest_archive.py`
    或显式：`.../ingest_archive.py feedback-360/source_feedback/<任意名>.zip`
    → 产出 `feedback-360/source_feedback/<slug>/`（docx + json）。
  - 校验：`python3 skills/aggregating-360-feedback/scripts/check_feedback.py feedback-360/source_feedback/<slug>`，全部合法（退出码 0）才进聚合。
  - 聚合：`python3 skills/aggregating-360-feedback/scripts/aggregate.py feedback-360/source_feedback/<slug>`
    → 写出 `feedback-360/source_feedback/<slug>/aggregated-data.json`（与原料同目录）。
  - 该 `aggregated-data.json` 是后两层的**唯一评分基准**。
  - 跑脚本需 `group:runtime` 权限。
  - 极差 ≥ 1.0 是机械信号（标 `suspected_split`），只触发关注，不是最终分歧结论。

### 综合分析 —— 第二层 · LLM 读评语区分共识/分歧

- **做什么**：读 `source_feedback/<slug>/` 下反馈评语 + 同目录 `aggregated-data.json`，区分共识/分歧，给归因和面谈建议。
- **产出路径**：`feedback-360/source_feedback/<slug>/aggregated-report.md`。
- **什么时候用**：机械聚合产出同目录 `aggregated-data.json` 之后。
- **调用要点**：语言理解由 Agent 完成；评分必须与 `aggregated-data.json` 一致，评语必须引用同目录反馈 JSON 原文。

### generating-360-dashboard —— 第三层 · HTML 雷达看板

- **做什么**：评分取自同目录 `aggregated-data.json`；共识/分歧判定与卡片语义**必须**取自同目录 `aggregated-report.md`（吸入 HTML），并可发布到 Canvas。
- **路径约定**：输入输出都在 `feedback-360/source_feedback/<slug>/`。
- **调用要点**：
  - 生成并发布：
    `bash skills/generating-360-dashboard/scripts/build_dashboard.sh feedback-360/source_feedback/<slug> --publish --force`
  - 缺 `aggregated-report.md` 会失败（语义不允许只用机械极差）。
  - canvas-id：`feedback-360-<slug>`；
    `http://127.0.0.1:18999/__openclaw__/canvas/documents/feedback-360-<slug>/index.html`

## 环境备注

- 本 profile：`$OPENCLAW_STATE_DIR`（仓库 `.openclaw-hr/`），访问前 `source` 该目录下 `env.sh`。
- 360 反馈：压缩包在 `source_feedback/` 顶层；该人全部资料（docx、单份 json、aggregated-data.json、aggregated-report.md、report.html）在 `source_feedback/<slug>/`。`raw/` 仅为历史样例。
