# 360 反馈聚合细则

> aggregating-360-feedback Skill 的聚合细则。SKILL.md 在需要时引用本文件。
> 评估维度对齐公司绩效管理制度第四条。

## 目录

- 1. 输入：反馈表 JSON 结构
- 2. 五个评估维度
- 3. 四类视角
- 4. 输出：aggregated-data.json 结构
- 5. 离散度与疑似分歧判定
- 6. 数据校验项
- 7. 合规边界

## 1. 输入：反馈表 JSON 结构

**上游源头**：`feedback-360/source_feedback/` 顶层任意文件名的 `.zip`/`.rar`。经 `ingest_archive.py` 得到 `source_feedback/<subject_slug>/*.json`（下文称 `json_dir`）。一次聚合一个人。

**聚合产物（与原料同目录）**：

| 文件 | 路径示例 | 说明 |
|---|---|---|
| `aggregated-data.json` | `source_feedback/yuangong1/aggregated-data.json` | `aggregate.py` 缺省产出 |
| `aggregated-report.md` | `source_feedback/yuangong1/aggregated-report.md` | 第二层综合分析约定产出 |

校验 / 聚合加载目录时须跳过上述聚合产物，只读单份反馈 JSON。

历史目录 `feedback-360/raw/` 仅为课程早期样例，主路径不再依赖。

`json_dir` 下每份反馈是一个 JSON 文件（`_` 开头与 `aggregated-*` 跳过）。每份结构：

```json
{
  "feedback_id": "唯一 ID",
  "subject": "评估对象姓名",
  "subject_role": "评估对象岗位",
  "period": "考核周期，如 2026-H1",
  "reviewer_relation": "manager / peer / report / self",
  "reviewer_alias": "领导1 / 同事1 / 下属1 / 自评（禁止真人名）",
  "submitted_at": "提交日期",
  "scores": {
    "goal_achievement": 1-5,
    "professional_skill": 1-5,
    "collaboration": 1-5,
    "responsibility": 1-5,
    "growth": 1-5
  },
  "comments": { "维度 key": "该维度文字评语" },
  "strengths": "总体亮点",
  "improvements": "改进建议"
}
```

## 2. 五个评估维度

源自绩效制度第四条「业绩结果 70% + 行为价值观 30%」，细化为 5 个可逐项打分的子项：

| key | 中文 | 归属 |
|---|---|---|
| `goal_achievement` | 目标达成 | 业绩结果 |
| `professional_skill` | 专业能力 | 业绩结果 |
| `collaboration` | 协作沟通 | 行为价值观 |
| `responsibility` | 责任心 | 行为价值观 |
| `growth` | 学习成长 | 行为价值观 |

评分 5 分制：5=远超预期 / 4=超出预期 / 3=符合预期 / 2=部分未达 / 1=明显未达。

## 3. 四类视角

360 反馈的「360」指评估视角覆盖一名员工的全部工作关系：

| `reviewer_relation` | 视角 | 看到什么 |
|---|---|---|
| `manager` | 上级 | 结果、目标对齐、向上沟通 |
| `peer` | 平级 | 组内/跨组协作 |
| `report` | 下属 | 带教、辅导 |
| `self` | 自评 | 自我认知 |

## 4. 输出：aggregated-data.json 结构

```json
{
  "subject": "...", "subject_role": "...", "period": "...",
  "total_feedback_count": 7,
  "perspectives": {
    "manager": {
      "label": "上级（直接主管）",
      "count": 1,
      "reviewers": [{ "alias": "...", "file": "manager.json" }],
      "dimensions": {
        "collaboration": { "scores": [3], "count": 1,
                           "average": 3.0, "min": 3, "max": 3 }
      }
    }
  },
  "overall": {
    "collaboration": { "average": 3.57, "min": 2, "max": 5, "range": 3 }
  },
  "divergence": {
    "collaboration": { "perspective_range": 1.5, "suspected_split": true }
  },
  "split_threshold": 1.0
}
```

- `perspectives` —— 按视角分组的逐维度统计，是报告和看板的主数据源。
- `overall` —— 所有反馈在每维度的总平均 + range。注意 `overall.range` 是「单份反馈之间」的极差，与 `divergence.perspective_range`（「视角平均分之间」的极差）是两个不同的数。
- `divergence` —— 逐维度的视角分歧机械判定。

## 5. 离散度与疑似分歧判定

`divergence` 段对每个维度算 `perspective_range` = 四个视角平均分里的最大值减最小值。`perspective_range >= 1.0` 时 `suspected_split = true`。

**为什么分析单位是「视角平均分」而不是「单份反馈」**：360 反馈要看的是「下属群体 vs 上级」这种系统性视角差异，不是「某一个评估人打分特别低」的个体噪声。所以极差算的是视角平均分之间的差，不是所有反馈的极值差。

**为什么阈值是 1.0**：1.0 分（5 分制的 20%）是一个保守的「值得关注」门槛——小于 1.0 的差异多属正常打分尺度波动，达到或超过 1.0 才足以构成「不同视角看到的不是同一个样子」的信号。这个阈值只触发关注，不下结论。

**`suspected_split` 不是「分歧」的最终判定**。它是机械信号，告诉第二层 LLM 综合分析「这个维度的评语要重点读」。最终是共识还是分歧，由 LLM 读完评语后定——有的维度极差达标但评语核心叙事一致（如上级打低分只是留成长空间），综合分析后仍归为共识。

## 6. 数据校验项

`check_feedback.py` 在聚合前校验：

1. 每个 JSON 文件可解析。
2. 必需字段齐全：`reviewer_relation` / `scores` / `comments`。
3. `reviewer_relation` 取值是 `manager / peer / report / self` 之一。
4. `reviewer_alias` 为 `领导N` / `同事N` / `下属N` / `自评`（校验前按文件名改写）。
5. `scores` 含 5 个维度，每个维度评分为 1-5 的整数。
6. 至少 1 份 `manager` + 1 份 `self`——360 反馈缺了上级或自评视角就不成立。

## 7. 合规边界

本 Skill 聚合的是绩效数据，受合规红线约束：

- 产出 `aggregated-data.json` 是**评分聚合数据**，不是绩效评级。
- 绝不输出 S/A/B/C/D 等绩效等级。绩效定级由「直接主管初评 → 隔级主管复核 → 校准会确认」三级人工流程确定（依据《个人信息保护法》第 24 条自动化决策条款、公司绩效管理制度第五条）。
- **评价人只出角色代号**（领导N / 同事N / 下属N / 自评），`reviewers[].alias` 不得保留真人名。
- 聚合产出定位是「供绩效面谈与校准会 review 的输入材料」。
