---
name: generating-training-materials
description: Generate a complete, internally consistent set of training materials from source documents via the ADDIE five-stage pipeline (eight Markdown deliverables), then run a mandatory self-check against evals/eval-cases.md and scripts/self_check.py before claiming delivery. Use whenever a business unit needs a full internal training package — needs analysis, course design, PPT outline, instructor manual (talking points, not verbatim scripts), participant handbook, assessment, delivery guide, and evaluation form — with stage hand-off and post-run validation.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# generating-training-materials

把一摞培训素材文档，经 ADDIE 五阶段流水线，生成一套内在自洽的培训物料——8 份文件；**交付前必须按评测场景做自我校验**。

## 何时用这个 Skill

业务部门要办一场内训，需要一整套培训物料时用。一套真正能用的培训物料不止一份 PPT，包含 8 类文件：需求分析、课程设计、PPT 大纲、讲师手册、学员手册、课后测试题、交付指南、评估反馈表。

讲师手册保留，但**只写讲解要点 + 互动 + 控场提示，禁止逐字稿**（长篇可照念话术费时难审）。

不用这个 Skill 的情况：只改某一份已有物料（直接改文件即可，不必重跑整条流水线）。用户只要学员手册+测试题时：`bash scripts/training-run.sh generate --theme <主题> --only 05,06`（缺 PPT 大纲等上游则停，不擅自生成另外 6 份）。

## 评测说明书在哪

本 Skill 目录结构：

```
generating-training-materials/
├── SKILL.md                 ← 工作流（本文）
├── references/stage-prompts.md
├── scripts/self_check.py    ← 交付前结构自检（机器可跑）
└── evals/eval-cases.md      ← 评测 / 自我校验说明书（必读）
```

**`evals/eval-cases.md` 用法（两用）**：

1. **作者评测**：改 Skill 前后，用里面的 `query` + `expected_behavior` 验收 Agent。
2. **Agent 自我校验（强制）**：流水线跑完后进入下方「步骤 8」，对照该文件的 `expected_behavior` 逐条核；结构项先跑 `self_check.py`。

不读 `eval-cases.md`、不做步骤 8，不得声称「全套物料已交付」。细则 → `evals/eval-cases.md` 文首「这份文件是干什么的」。

## 这条流水线的本质：ADDIE 五阶段，前阶段产出严格定义后阶段输入

ADDIE 是培训设计领域沿用数十年的标准方法论，五个字母是五个阶段：

| 阶段 | 含义 | 本流水线产出 |
|------|------|------------|
| **A** Analysis | 需求分析——教给谁、解决什么痛点、达成什么目标 | `01-needs-analysis.md` |
| **D** Design | 课程设计——课程结构、模块、时长、教学方式 | `02-course-design.md` |
| **D** Development | 物料开发——逐份生成可用物料 | `03`~`06` 四份 |
| **I** Implementation | 实施——交付指南，讲师怎么落地这套物料 | `07-delivery-guide.md` |
| **E** Evaluation | 评估——评估反馈表 | `08-evaluation-form.md` |

**编排在脚本里，不在一次 Agent 会话里。** 8 次长文若交给 OpenClaw 连续 `write`，会撞 CLI 默认 630s 超时且没有结束句（X-PROC-05 / T-D-002）。

对话层只许：

```bash
bash scripts/training-run.sh generate --theme <主题>
```

脚本按 ADDIE 对每个阶段做 **一次 HTTP LLM 调用** 并落盘；已有足够长的 `01`…`0k` 默认跳过（断点续跑）；结束时 **一定** 打印 `RESULT: success|failure` 以及 `FILES` / `MISSING`。声称交付时只认这一行 + `self_check.py`。禁止自己用 `write` 编 `training/courses/` 假路径。

流水线仍靠三条铁规则（由脚本执行，不是靠模型自觉）：

1. **每个阶段的产出落盘成文件**——`training-materials/<主题>/` 下指定文件名。
2. **后一阶段开工前读前一阶段产出**——脚本把文件打进下一阶段 prompt。
3. **全部落盘后自我校验**——脚本末尾跑 `self_check.py`。

## 工作流程

**Agent：只跑 `training-run.sh generate`，把脚本的 `RESULT` 原样交回。** 下面步骤 1–8 是脚本内部顺序（对照 `stage-prompts.md`），不要在对话里逐步 `write` 八份长文。

全量重写加 `--force`。缺素材则脚本非 0 退出，按 `RESULT: failure` 汇报。

### 步骤 0 · 准备

确认 `source-docs/` 下有培训素材。空则停。产出目录：`training-materials/<主题>/`。

脚本会 `ls` 后跳过已有合格文件。禁止 Agent 自己逐步写 01–08。

### 步骤 1 · A+D 阶段——需求分析 + 课程设计

读 `source-docs/` 全部素材，用 `stage-prompts.md` 的【模板 1】，产出 `01-needs-analysis.md` 和 `02-course-design.md`。
完成判据：两份文件落盘；`01` 含培训目标 T1-T5；`02` 末尾有"模块与培训目标对应矩阵"。

### 步骤 2 · D 阶段物料 1——PPT 大纲

读 `01-needs-analysis.md` 和 `02-course-design.md`，用【模板 2】，产出 `03-ppt-outline.md`。
完成判据：每页含页码、标题、要点（具体 bullet 不是占位符）、所属模块、时长；与课程设计的模块一一对应。

### 步骤 3 · D 阶段物料 2——讲师手册

读 `03-ppt-outline.md`，用【模板 3】，产出 `04-instructor-manual.md`。
完成判据：对 PPT 逐页对应；每页有讲解时长、**讲解要点**（3～6 条 bullet）、互动引导、讲师提示。**不要写逐字稿**——逐页长篇可照念话术费时难审，现行流程已删除该要求。

### 步骤 4 · D 阶段物料 3——学员手册

读 `03-ppt-outline.md`，用【模板 4】，产出 `05-participant-handbook.md`。
完成判据：按模块组织；每模块末尾有速查框；结尾有第一周行动清单。

> 步骤 3、4 都读 `03-ppt-outline.md`，**不各自重读 source-docs**——让 PPT 大纲当"单一内容源"，三份物料口径才一致。

### 步骤 5 · D+E 阶段物料 4——课后测试题

读 `01-needs-analysis.md`（取培训目标 T1-T5）和 `05-participant-handbook.md`（取考点），用【模板 5】，产出 `06-assessment.md`。
完成判据：题目难度分梯度；每题标【对应培训目标】且 T1-T5 全覆盖；每题附答案详解。

### 步骤 6 · I 阶段——交付指南

用【模板 6】，产出 `07-delivery-guide.md`（物料清单、实施流程、新讲师上手路径、当天 checklist、常见问题处理）。

### 步骤 7 · E 阶段——评估反馈表

用【模板 7】，产出 `08-evaluation-form.md`（李克特 5 级量表评分项 + 开放问答，附柯氏四级评估模型说明）。

完整 7 段 prompt 模板见 → `references/stage-prompts.md`

### 步骤 8 · 交付前自我校验（不可省）

**生成 ≠ 交付。** 8 份文件落盘后必须做本步，对照 → `evals/eval-cases.md`。

**8a · 结构自检（机器）**——原样跑：

```bash
python3 skills/generating-training-materials/scripts/self_check.py \
  --outdir <本次 8 份物料所在目录>
```

退出码 0 = 结构项通过；非 0 = 按 stderr 所列问题修补后重跑，**不得跳过**。

**8b · 场景判断项（对照 eval-cases）**——至少核场景 1、2：

- 是否按 A→D→I→E 顺序、无跳阶段
- 04/05 是否以 `03-ppt-outline.md` 为单一内容源（未各自重读 source-docs 另起炉灶）
- 04 讲师手册是否为讲解要点版（无逐字稿）
- 03 与 02 模块结构是否对应；06 是否覆盖 T1-T5

**8c · 汇报**：向用户说明自检结果（`self_check` 退出码 + 判断项结论）。自检未通过时明确列出缺口，不要假装已交付完成。

## 关键规则

- 7 个生成步骤严格按顺序，每步产出落盘后再进下一步；**第 8 步自检不可省**。
- 后一步开工前必须先读前一步指定的产出文件——这是 Pipeline 阶段承接的硬约束。
- 讲师手册**禁止逐字稿**，只要讲解要点 + 互动 + 控场提示。
- 所有物料内容基于 `source-docs/` 真实素材，不编造制度、数字、名称。
- 换主题复用：只改步骤 1【模板 1】里对素材和受众的描述，后面生成步骤不用动；换目录后步骤 8 仍要对新目录跑一遍。
- 物料是 AI 辅助生成的草稿，对外交付前必须经讲师审核，每份应带"AI 辅助生成、讲师审核后交付"标注。
- **验收标准写在 `evals/eval-cases.md`**——改行为或加场景时先改评测文件，再改本 SKILL / 模板（评测驱动）。
