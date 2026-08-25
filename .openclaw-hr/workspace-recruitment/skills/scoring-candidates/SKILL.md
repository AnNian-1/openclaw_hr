---
name: scoring-candidates
description: Score a desensitized candidate against a job description across 8 fixed dimensions, producing dimension scores, an overall 0-100 match score, an A/B/C/D rating, scoring rationale, highlights, concerns, and hard-issue flags. Use this skill as the second stage of the scoring pipeline, after filtering-sensitive-fields has stripped sensitive fields and before auditing-numbers checks the numbers. Supports single-candidate scoring and batch scoring of a candidate pool with ranking by match score. The input must already be desensitized — this skill scores, it does not do compliance filtering or resume parsing.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# scoring-candidates

对一份脱敏后的候选人数据 + 岗位 JD，按 8 个固定维度评分，产出综合匹配分、评级、评分理由、亮点、顾虑、硬伤。这是评分 Pipeline 的第二层。

## 何时用这个 Skill

候选人数据经 `filtering-sensitive-fields` 脱敏之后用。它是评分 Pipeline 三层的第二层，前面是合规过滤、后面是数字回核。

它和相邻的几个 Skill 边界清楚：
- 它**不做合规过滤**——剥离敏感字段是 `filtering-sensitive-fields` 的事，本 Skill 的输入必须已经是脱敏数据。
- 它**不做简历解析**——把简历变结构化数据是 `parsing-resumes` 的事。
- 它的产出（评分文字里的数字）需要 `auditing-numbers` 回核，但回核不是它自己做。

本 Skill 只负责"评分"这一件事。

## 输入前提

输入的候选人 JSON **必须是 `filtering-sensitive-fields` 脱敏后的**，不能是含年龄性别的原始画像。评分模型一旦在数据里看到敏感字段就可能拿它打分，合规边界就破了。如果不确定输入是否脱敏过，先跑 `filtering-sensitive-fields`。

## 工作流程

按要评的是单份还是一批，分两条路：

### 单份评分

```bash
node skills/scoring-candidates/scripts/score_candidate.js <脱敏候选人json> <JD-md> [输出json]
```

调大模型按 8 维度打分，产出综合匹配分 + 评级 + 评分理由 + 亮点 + 顾虑 + 硬伤。退出码 0 = 成功，1 = 评分失败（大模型多次重试仍不可用），2 = 文件/用法问题。

### 批量评分 + 排序

```bash
node skills/scoring-candidates/scripts/batch_rank.js <JD-md> <脱敏候选人json目录> [输出json] [文件名前缀]
```

对目录里每份脱敏候选人 JSON 依次评分，全部评完按综合匹配分降序排序。每份候选人最多评 3 次——批量任务偶发失败是常态，3 次全失败的会显式标记为"待人工处理"，不静默丢弃。

8 维度清单、综合分含义、评级切分、concerns/hard_issues 边界、批量纪律的细则见 → `references/scoring-method.md`

## 关键规则

- **8 维度而不是一个总分**。8 个固定维度（专业技能、经验匹配、逻辑能力、学习力、沟通能力、协作能力、抗压能力、价值观），每维度 1-5 分，各配一句理由——评分要可解释（个保法 24 条）。
- **只评分、不淘汰**。产出标"建议动作"（建议进入面试 / 建议人工复核），绝不出现"淘汰/录用"。识别出硬伤也只是标出疑点交人复核。最终决定由人工 HR 做。
- **concerns 和 hard_issues 不能混**。硬伤只装简历真实性问题（经历时间矛盾、学历存疑、内容自相矛盾）；薪资高、城市不符、跳槽频繁这些匹配度/稳定性问题进 concerns。把匹配度问题误判成硬伤，会触发过重的处置建议。
- **评分有非确定性波动**。同一份简历多次评分，综合分会有正负几分浮动。拿到 ranking 后看评级大类 + 评分理由，不要抠 1-2 分之差。
- 评分产出的自由文本（亮点、理由）里的数字可能有串台风险，进 HR 决策前要过 `auditing-numbers` 回核。
