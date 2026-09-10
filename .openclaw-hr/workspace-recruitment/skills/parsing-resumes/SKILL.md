---
name: parsing-resumes
description: Extract structured candidate data from a resume that has been converted to Markdown. Use this skill whenever a resume Markdown file needs to become a schema-aligned candidate JSON for downstream scoring, profiling, or talent-pool indexing. Handles resumes converted from PDF, DOCX, or written natively in Markdown. Excludes legally forbidden fields (age, gender, marital status) and validates the result against the candidate profile schema.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# parsing-resumes

把一份已转成 Markdown 的简历，抽取成对齐候选人画像 schema 的结构化 JSON。

## 何时用这个 Skill

收到一份简历 Markdown，需要把它变成结构化候选人数据时用。简历可能来自：
- office-to-md 从 PDF 转出的（标题层级丢失，缩进纯文本）
- office-to-md 从 DOCX 转出的（保留表格、标题结构）
- 原本就是 Markdown 写的

下游的评分、画像、人才库检索都依赖这一步的产出，所以这一步的产出必须对齐 schema、可校验。

## 工作流程

简历解析分三步，按顺序做：

### 第 1 步 · 抽取

读简历 Markdown，按 `references/field-extraction.md` 的规则抽取字段，产出一个 JSON 文件，存到 `parsed/<简历名>.json`。

抽取的硬规则（必须照做，不靠判断）：
- **只抄原文有的，原文没有的字段留空（`null` 或 `""`）——绝不编造一个看起来合理的值。** LLM 有补全倾向，这条必须守死。
- **绝不抽取合规红线字段**：年龄、出生日期、性别、婚育、户籍、民族、健康。这些字段简历里有也跳过，既不抄中文键也不译英文键（依据见 `references/field-extraction.md` §8）。
- **软推断字段必须显式标注**。`industry`（行业）是从公司名推断的，不是简历原文写的——`work_experience` 里每段只要产出了 `industry`，就必须同时带 `"industry_inferred": true`。漏标注会被校验脚本拦下。
- **派生字段一律按客观数据计算，不取自述值**。`total_experience_years` 按 `work_experience` 各段起止时间累加得出；简历里"工作年限"栏的自述值只作参照，不作准——自述值可能笔误或有意写长。`job_count` = 工作经历段数。

字段组、每个字段的抽取细则见 → `references/field-extraction.md`

### 第 2 步 · 校验

抽取产出的 JSON 必须用校验脚本过一遍，跑通才算合格：

```bash
bash scripts/recruitment-run.sh node skills/parsing-resumes/scripts/validate_profile.js parsed/<简历名>.json
```

脚本校验：JSON 可解析、必需字段组齐全、**合规红线字段零出现**、派生字段与工作经历自洽、每段经历字段完整。退出码 0 = 通过，1 = 不通过（会列出全部问题）。

### 第 3 步 · 修正重跑

校验若报错（退出码 1），按报出的问题逐条修正 JSON，重跑第 2 步，直到校验通过。这是「抽取 → 校验 → 修 → 重跑」的闭环——不要跳过校验直接交付。

## 关键规则

- 一份简历对应一个 `parsed/<简历名>.json`，文件名与简历同名。
- 校验不通过的 JSON 不算解析完成。
- 这个 Skill 只做"简历 → 结构化数据"。真实性核对（字段逐字回溯原文）是另一个 Skill `auditing-extraction` 的事。
