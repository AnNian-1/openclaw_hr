---
name: aggregating-360-feedback
description: Ingest a zip/rar of filled 360 feedback Word forms, parse them into JSON, then mechanically aggregate by reviewer perspective (manager/peer/report/self) with per-dimension averages and divergence flags. Use whenever 360 feedback arrives as an archive of DOCX forms (or an already-parsed JSON directory) and needs a reproducible, auditable score rollup. Deterministic scripts only — never produces a performance rating.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      # .rar 额外需要系统 unrar；python 依赖：python-docx、pypinyin；rar 另需 rarfile
---

# aggregating-360-feedback

把多份 360 度绩效反馈表机械聚合成一份按视角分组的数据集——逐维度算各视角平均分，并标出哪些维度各视角说法打架。

## 何时用这个 Skill

收到一组 360 反馈表（上级 / 平级 / 下属 / 自评），需要把它们汇总成「四视角 × 五维度」的对照数据时用。这是 360 反馈聚合 Pipeline 的**第一层**：

- 第一层（本 Skill）：机械聚合——按视角分组、逐维度算平均分、算极差、标疑似分歧。**确定性计算，脚本做。**
- 第二层：LLM 综合分析——读反馈评语，把疑似分歧坐实为共识点 / 分歧点，给分歧归因和面谈建议。
- 第三层：HTML 看板——由 `generating-360-dashboard` Skill 做。

本 Skill 的产出 `aggregated-data.json` 是后面两层的**唯一数据基准**——第二层综合分析、第三层看板都从它取数，不再重新算。

## 数据源头与落盘

**主源头是压缩包**，文件名**不固定**；原料与聚合产物都落在同一人目录下：

```
feedback-360/source_feedback/
  ├── <任意名>.zip|.rar            # 顶层投放压缩包（名字随意）
  └── <slug>/                      # 如 zhanglei/，由 DOCX「被评估人」自动转拼音
        ├── *.docx                 # 解压出的反馈表
        ├── manager.json …         # 解析出的单份反馈
        ├── aggregated-data.json   # 机械聚合产出
        ├── aggregated-report.md   # 第二层综合分析产出
        └── report.html            # 第三层看板（generating-360-dashboard）
```

```
source_feedback/<任意名>.zip
        │  ingest_archive.py
        ▼
source_feedback/<slug>/            ← 该人全部资料同目录
        │  check → aggregate
        ▼
source_feedback/<slug>/aggregated-data.json
source_feedback/<slug>/aggregated-report.md
        │  generating-360-dashboard
        ▼
source_feedback/<slug>/report.html
```

### 聚合产物落盘（按人、同目录）

一次只聚合一位被评估人，产物写在该人 `source_feedback/<slug>/` 下：

| 文件 | 路径示例 | 谁写 |
|---|---|---|
| 评分聚合 | `source_feedback/zhanglei/aggregated-data.json` | `aggregate.py` |
| 综合分析 | `source_feedback/zhanglei/aggregated-report.md` | 第二层 Agent |
| HTML 看板 | `source_feedback/zhanglei/report.html` | `generating-360-dashboard` |

## 为什么聚合层用脚本，不用 LLM

算平均分、算极差是确定性计算，LLM 算反而会出错。所以：

- **能用确定性脚本算的（解压、DOCX→JSON、评分聚合、极差），一律脚本算。**
- **必须靠语言理解的（评语对照、分歧归因、面谈建议），才交给 LLM**。

## 工作流程

### 第 0 步 · 摄入压缩包（DOCX → JSON）

```bash
python3 skills/aggregating-360-feedback/scripts/ingest_archive.py
# 或
python3 skills/aggregating-360-feedback/scripts/ingest_archive.py \
  feedback-360/source_feedback/<任意名>.zip
```

### 第 1 步 · 数据校验

```bash
python3 skills/aggregating-360-feedback/scripts/check_feedback.py \
  feedback-360/source_feedback/zhanglei
```

（会自动跳过同目录的 `aggregated-data.json`。）

### 第 2 步 · 机械聚合

```bash
python3 skills/aggregating-360-feedback/scripts/aggregate.py \
  feedback-360/source_feedback/zhanglei
```

**缺省产出**：`source_feedback/zhanglei/aggregated-data.json`。

### 第 3 步（衔接）· 综合分析报告

写到同目录：`source_feedback/zhanglei/aggregated-report.md`。

## 关键规则

- **源头走压缩包摄入**；原料与聚合产物都在 `source_feedback/<slug>/`。
- **聚合前必须先过校验**。
- **产物路径**：`<slug>/aggregated-data.json` + `<slug>/aggregated-report.md`。
- **`aggregated-data.json` 是唯一评分基准**；下游看板从该路径取数。
- **本 Skill 不输出 S/A/B/C/D 绩效评级**（合规红线，见 SOUL.md）。
