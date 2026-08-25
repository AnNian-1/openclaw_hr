# generating-training-materials 评测场景

## 这份文件是干什么的

`evals/eval-cases.md` 不是给 HR 看的物料，而是本 Skill 的**验收说明书**，两种用法：

| 用法 | 谁用 | 何时 |
|---|---|---|
| **A · 作者评测** | 写 Skill / 做双 Claude 迭代的人 | 改 SKILL.md 前后，对照 `expected_behavior` 看 Agent 是否达标 |
| **B · Agent 自我校验** | 跑本 Skill 的 Agent | **8 份物料全部落盘之后**（SKILL.md 步骤 8），必须对照本文件做交付前自检 |

> Agent 跑完流水线却不读本文件、不做步骤 8，等于「只生产不验收」——这正是本 Skill 要堵住的缺口。

### Agent 怎么用（交付前必做）

1. 读本文件全部场景的 `expected_behavior`。
2. 先跑结构自检脚本（可机器化部分）：

```bash
python3 skills/generating-training-materials/scripts/self_check.py \
  --outdir <本次物料目录>
```

3. 再按下方场景做**判断项**抽查（脚本兜不住的部分），例如：
   - 讲师/学员手册是否以 `03-ppt-outline.md` 为单一内容源（而非各自重读 `source-docs/`）
   - 讲师手册是否为讲解要点版（**无逐字稿**）
   - 步骤顺序是否 A→D→I→E、有无跳阶段
4. 任一项不满足：修补对应物料或重跑对应步骤，再重新自检；**自检未通过不得声称「全套物料已交付」**。

---

## 评测场景

> 评测对象：经 ADDIE 五阶段 Pipeline 生成一套内在自洽的培训物料（8 份 Markdown）。
> 验证的不是「某个脚本输出对不对」，而是「Agent 能否照 SKILL.md 把阶段走完、承接不断链，并在交付前按本文件自检」。

### 场景 1 · 完整 ADDIE 五阶段走一遍（主场景）

- 输入：`source-docs/` 下若干培训素材文档
- query：给某主题做一套完整培训物料
- expected_behavior：
  - Agent 识别这是 ADDIE 物料生成任务，触发本 Skill
  - 严格按 A → D → I → E 顺序，不跳阶段、不打乱
  - 每个阶段的产出落盘成文件（`01-needs-analysis.md` ... `08-evaluation-form.md`）
  - 后一阶段调用前，先读前一阶段产出的指定文件（阶段承接）
  - 8 份物料全部产出，主题彼此一致
  - **交付前执行步骤 8 自检**（`self_check.py` + 本文件判断项）

### 场景 2 · 阶段承接不断链（验证 Pipeline 强约束）

- 输入：同场景 1
- query：观察 `03-ppt-outline.md` 与 `04-instructor-manual.md` / `05-participant-handbook.md` 的关系
- expected_behavior：
  - 讲师手册、学员手册都基于 `03-ppt-outline.md`（单一内容源），不各自重读 source-docs
  - PPT 大纲与课程设计的模块结构一一对应
  - 讲师手册是逐页**讲解要点**（非逐字稿）；不应出现长篇可照念话术
  - 测试题对应需求分析里定下的培训目标 T1-T5，每个目标都有题覆盖
  - `self_check.py` 对 T1-T5 / 对应矩阵 / 题目标注结构项通过

### 场景 3 · 换主题复用（验证 Skill 的可复用性）

- 输入：把 source-docs 换成另一主题的素材（或写入子目录如 `training-materials/<主题>/`）
- query：给新主题做培训物料
- expected_behavior：
  - 后几个阶段的 prompt 不用改——它们吃前阶段产出文件，主题顺着 Pipeline 自动往下传
  - 只需改 A 阶段对受众/目标的描述
  - 对新产出目录同样跑步骤 8 自检

### 场景 4（边界）· 缺素材文档

- 输入：`source-docs/` 为空或缺失
- query：做一套培训物料
- expected_behavior：
  - Agent 识别出 A 阶段（需求分析）没有素材输入，停下来要素材
  - 不在没有素材的情况下硬编一套需求分析（ADDIE 的地基不能凭空造）
  - 此场景**不应**产出 8 份文件，也**不必**强行跑 `self_check.py` 到通过

## 基线测试（没有 Skill 时）

没有这个 Skill 时，「做一套培训物料」常退化成一句模糊 prompt：只出 PPT、跳过需求分析、或阶段承接靠临场发挥。本文件的 `expected_behavior` 就是用来判定 Skill 是否把这些坑堵上的标准。
