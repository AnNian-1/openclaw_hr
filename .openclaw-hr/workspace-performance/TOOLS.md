# TOOLS.md — 绩效子 Agent 的工具与 Skill 清单

> Skill 定义「怎么用」。这里写本 workspace 的真实签名、路径和禁止入口。

工作目录：`workspace-performance/`。下列命令相对此目录。

## 脚本签名（以脚本 docstring / usage 为准）

```text
python3 skills/aggregating-360-feedback/scripts/ingest_archive.py
python3 skills/aggregating-360-feedback/scripts/ingest_archive.py <archive.zip|rar> [out_dir]

python3 skills/aggregating-360-feedback/scripts/check_feedback.py <json_dir>
# 退出码 0 合法 / 1 数据问题 / 2 用法错误。必须带 <json_dir>。

python3 skills/aggregating-360-feedback/scripts/aggregate.py <json_dir> [out_json_path]
# 缺省写出 <json_dir>/aggregated-data.json
# 会再跑 check 同一套校验；缺自评 / 脏数据 exit 1，不写聚合文件

python3 skills/generating-360-dashboard/scripts/build_dashboard.py \
  <person_dir|aggregated_json> [out_html] [verdict_json]
# 第三参 verdict_json 会被忽略：语义只读同目录 aggregated-report.md

bash skills/generating-360-dashboard/scripts/build_dashboard.sh \
  <person_dir|aggregated_json> [out_html] [--publish] [--force]
# canvas-id = feedback-360-<slug>；slug 必须 ASCII
```

**禁止**当现行入口（课程裸脚本，签名与现行不一致）：

- `feedback-360/check_feedback.py` — 无参数、绑死不存在的 `raw/`，不查自评
- `feedback-360/models/aggregate.py` — 绑死 `raw/`，缺自评仍会写出 JSON
- `feedback-360/build_dashboard.py` — 绑死根目录 JSON，写死课程 7 份判定

`feedback-360/raw/` 仅为历史样例目录（本仓可不存在）。现行原料与产物都在 `feedback-360/source_feedback/<slug>/`。

## 360 反馈聚合相关 Skill

### aggregating-360-feedback —— 第一层 · 机械聚合

- **做什么**：从 `feedback-360/source_feedback/` 顶层任意名的 zip/rar（内含已填 DOCX）摄入，解析成 JSON，再机械聚合成按视角分组的 `aggregated-data.json`。
- **什么时候用**：拿到一包 360 反馈 Word 表（或已解析的 JSON 目录），要做面谈输入材料时，这是第一步。
- **调用要点**：
  - 摄入：`ingest_archive.py` 无参则只扫 `source_feedback/` **顶层**唯一压缩包；多包必须显式传路径。
    → `feedback-360/source_feedback/<slug>/`（docx + json）。
  - 校验：`check_feedback.py feedback-360/source_feedback/<slug>`，退出码 0 才进聚合。
  - 聚合：`aggregate.py feedback-360/source_feedback/<slug>`
    → `feedback-360/source_feedback/<slug>/aggregated-data.json`。
  - 该 JSON 是后两层的**唯一评分基准**。
  - `reviewer_alias` 只保留 领导N、同事N、下属N、自评。
  - 跑脚本需 `group:runtime`（含 `exec`）。
  - 极差 ≥ 1.0 标 `suspected_split`，只触发关注，不是最终分歧结论。

### 综合分析 —— 第二层 · LLM 读评语

- **做什么**：读 `source_feedback/<slug>/` 评语 + 同目录 `aggregated-data.json`，区分共识/分歧，给归因和面谈建议。
- **产出**：`feedback-360/source_feedback/<slug>/aggregated-report.md`。
- **调用要点**：评分必须与 JSON 一致；评价人只用角色代号；首尾声明 + 全文无 S/A/B/C/D。

### generating-360-dashboard —— 第三层 · HTML 雷达看板

- **做什么**：评分取自 `aggregated-data.json`；共识/分歧与卡片**必须**取自同目录 `aggregated-report.md`。
- **推荐入口**：
  `bash skills/generating-360-dashboard/scripts/build_dashboard.sh feedback-360/source_feedback/<slug> --publish --force`
- 缺 `aggregated-report.md` 会失败。
- canvas-id：`feedback-360-<slug>`；
  `http://127.0.0.1:18999/__openclaw__/canvas/documents/feedback-360-<slug>/index.html`
- 夹具看板不是校准会结果。不要对用户发明 S/A/B/C。

## 环境备注

- 本 profile：`$OPENCLAW_STATE_DIR`（仓库 `.openclaw-hr/`），访问前 `source` 该目录下 `env.sh`。
- 一人一次：换人换 `<slug>`，不要把课程 7 份张磊数字套到现行 `yuangong1`（现行夹具是 4 份）。
