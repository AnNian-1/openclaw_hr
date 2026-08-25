---
name: auditing-extraction
description: Audit a parsed candidate JSON for truthfulness by tracing every extracted field back to the original resume. Use this skill right after parsing-resumes produces a candidate JSON, before that data goes to scoring or profiling. Hard-extracted fields (name, salary, school, dates, company) must be traceable character-by-character to the resume text; soft-inferred fields (industry) must carry an explicit `_inferred` flag. Catches fabricated, mistyped, or unflagged fields that schema validation alone cannot detect, and reports a field-level traceability rate.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# auditing-extraction

把 `parsing-resumes` 抽取出的候选人 JSON，逐字段回溯到简历原文，核对它真不真。

## 何时用这个 Skill

`parsing-resumes` 产出一份候选人 JSON 之后、这份数据进入评分或画像之前，用这个 Skill 做一道真实性核对。

它和 `parsing-resumes` 内置的 `validate_profile.js` 是两件不同的事——`validate_profile.js` 核对 schema 和合规**结构**（字段组齐不齐、有没有混进红线字段），回答「形状对不对」；这个 Skill 核对抽取值**逐字段回溯简历原文**，回答「内容真不真」。两道闸都要过：先 `validate_profile.js`，再这个 Skill。

为什么需要它：LLM 抽取结构化数据时有「补全」倾向，原文没有的字段可能被它填一个看似合理的值。简历解析产出是招聘子 Agent 整条链的地基，地基有假数据会一路传下去——评分基于假数据给分、画像展示假经历。所以解析之后必须有一道事后核对闸。

## 工作流程

真实性核对分两步，按顺序做：

### 第 1 步 · 核对

对一份待核对的候选人 JSON，跑核对脚本——它需要 parsed JSON 和对应的简历原文 Markdown 两个输入：

```bash
node skills/auditing-extraction/scripts/audit_extraction.js parsed/<简历名>.json inbox/<简历名>.md
```

脚本按字段类型分三套标准核对（细则见 → `references/audit-method.md`）：

- **硬提取字段**（name / phone / email / target_position / expected_salary / expected_city / available_date / school / major / degree / company / position / start_date / end_date）——值必须能在简历原文里**逐字符找到出处**。找不到 = 疑似编造/笔误/张冠李戴，报出来。
- **软推断字段**（`industry`）——原文本就没有出处，不核对出处；核对它**是否带 `industry_inferred: true` 标志**，以及推断依据（公司名）是否能在原文找到。漏标注必须报。
- **派生字段**（`total_experience_years` / `job_count`）——核对计算依据（`work_experience` 各段）是否成立。

脚本产出一份核对报告 `audited/<简历名>.audit.json`（逐字段核对结果 + 可追溯率），并打印摘要。退出码 0 = 全部可追溯且推断字段已合规标注；1 = 有字段对不上原文或漏标注（会逐条列出）；2 = 文件缺失。

### 第 2 步 · 按核对结果处理

核对若不通过（退出码 1），按报出的字段类型分别处理：

- **硬提取字段对不上原文**：回到 `parsing-resumes` 重新抽取这个字段，或人工核对简历原文确认正确值。不要直接改 JSON 蒙混——对不上就是对不上。
- **软推断字段漏标注**：给该段 `work_experience` 补 `industry_inferred: true`。
- 修正后重跑第 1 步，直到核对通过。

## 关键规则

- 真实性核对是 `parsing-resumes` 抽取之后的**强制下一步**，不是可选项——抽取产出不经核对不算解析完成。
- 硬提取字段对不上原文，不能靠改 JSON 绕过；只能重抽或人工确认。
- 核对报告 `audited/<简历名>.audit.json` 要留存，用于合规审计与复查。
- 这个 Skill 只做「核对」，不做抽取——抽取是 `parsing-resumes` 的事。
