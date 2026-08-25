---
name: filtering-sensitive-fields
description: Strip legally sensitive fields from a candidate profile JSON before it goes to scoring. Use this skill as the first stage of the scoring pipeline, right before scoring-candidates, whenever a candidate profile needs to become a scoring input. Physically deletes age, gender, marital status, ethnicity, household registration, health, school tier, and political status — recursively across all nesting levels — then runs a compliance self-check that refuses to pass if any sensitive key remains. This is field-level removal for legal compliance, not the truthfulness audit done by auditing-extraction.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# filtering-sensitive-fields

把候选人画像 JSON 里受法律和政策约束的敏感字段物理删除，产出一份可以安全进评分的脱敏数据。这是评分 Pipeline 的第一层。

## 何时用这个 Skill

一份候选人画像 JSON 准备进入评分之前用。它是评分 Pipeline 三层里的第一层，固定排在 `scoring-candidates` 之前——评分模型一旦在 prompt 里看到了候选人的年龄和性别，合规边界就破了，所以脱敏必须发生在评分之前。

它和 `auditing-extraction`（简历解析的真实性核对）是两件不同的事：`auditing-extraction` 核对"字段真不真"，这个 Skill 做的是"把不能用于评分的字段删掉"。它也不评分——评分是 `scoring-candidates` 的事。这个 Skill 只负责评分 Pipeline 第一层的合规过滤。

## 为什么必须物理删除

合规过滤"做对"靠的不是在评分 prompt 里叮嘱大模型"别用年龄性别"——大模型看得到这些字段，你无法证明它没用。**正确做法是让评分模型根本看不到**：进评分之前，把敏感字段从数据里物理删除。这是《个人信息保护法》第 24 条对自动化决策"可证明合规"的硬要求，不是"差不多就行"的地方。

## 工作流程

合规过滤分两步，按顺序做：

### 第 1 步 · 过滤

对一份候选人画像 JSON，跑过滤脚本——它物理删除敏感字段并做合规自检：

```bash
node skills/filtering-sensitive-fields/scripts/filter_sensitive.js profiles/<候选人>.json scoring/clean-<候选人>.json
```

脚本做三件事：

- **递归物理删除黑名单字段**——扫所有层级（顶层 + `education` 等子层 + `work_experience` 数组）。敏感字段不只在顶层，院校层次嵌在 `education` 里，只扫顶层会漏。
- **合规自检**——剥离后递归重扫，用词干匹配找残留的疑似敏感 key。残留任何一个，退出码 1，绝不放行。
- **产出脱敏 JSON + 剥离清单**——剥离清单是结构化、可留存的合规日志。

黑名单覆盖（中英文键名都管）：年龄/出生日期、性别、婚育、户籍籍贯、民族、健康/残疾、院校层次、政治面貌。完整字段清单与法律依据见 → `references/sensitive-fields.md`

退出码 0 = 过滤通过（自检剩余敏感字段 = 0）；1 = 自检未通过（脱敏后仍有残留）；2 = 文件/用法问题。

### 第 2 步 · 按自检结果处理

- **退出码 0**：脱敏 JSON 可以交给 `scoring-candidates` 评分。
- **退出码 1**：自检报出了残留的疑似敏感字段。把它加进脚本 `FORBIDDEN_KEYS` 黑名单，重跑第 1 步。**绝不能跳过自检直接拿这份数据去评分**——残留的敏感字段会进评分模型。

## 关键规则

- 合规过滤是评分前的**强制第一步**，不是可选项。脱敏未通过的数据不能进评分。
- 物理删除的是画像数据的一个副本——脚本不动原始画像。原始画像保留敏感字段供 HR 做统计、画像展示（敏感字段"可记录、禁评分"）；进评分的副本才脱敏。这是"画像要完整、评分要干净"的分层设计。
- 合规自检通过那一行日志是写进审计记录的合规证据，要留存。
- 评分阶段的 prompt 里仍保留一段"禁止使用年龄性别"的声明作为第二道防线——万一敏感信息藏在自我评价这种自由文本字段里，字段级黑名单清不掉，prompt 声明兜底。两道防线：物理删除是主、prompt 声明是兜底。
