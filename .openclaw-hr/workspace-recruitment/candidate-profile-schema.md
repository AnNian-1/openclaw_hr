# 候选人画像字段标准（candidate-profile-schema）

> **定位**：招聘子 Agent 的**数据契约成文形式**。解析照它产出、画像照它渲染、评分维度来自 §8、合规黑名单来自 §9。  
> **原则**：契约先定义、后开发——五个能力靠稳定字段结构接力。  
> **落盘路径**：
> - 运行态：`$OPENCLAW_STATE_DIR/workspace-recruitment/candidate-profile-schema.md`（本仓 profile 在 `/opt/openclaw-hr/.openclaw-hr/`，不要写成 `~/.openclaw-hr`）

---

## 目录

1. [§1 文档目的与数据生命周期](#1-文档目的与数据生命周期)
2. [§2 基础信息字段组](#2-基础信息字段组)
3. [§3 教育背景字段组](#3-教育背景字段组)
4. [§4 工作经历字段组](#4-工作经历字段组)
5. [§5 技能字段组](#5-技能字段组)
6. [§6 派生字段](#6-派生字段)
7. [§7 硬提取 vs 软推断](#7-硬提取-vs-软推断)
8. [§8 评估维度与评分产出](#8-评估维度与评分产出)
9. [§9 合规红线与分层处置](#9-合规红线与分层处置)
10. [§10 来源与跟进元数据](#10-来源与跟进元数据)
11. [附录 A · 最小合法 JSON 示例](#附录-a--最小合法-json-示例)

---

## §1 文档目的与数据生命周期

本 schema 定义候选人结构化数据的 **6 组字段**：

| # | 字段组 | 主要落点 | 谁产出 |
|---|--------|----------|--------|
| 1 | 基础信息 | 顶层平铺 | `parsing-resumes` |
| 2 | 教育背景 | `education` 对象 | `parsing-resumes` |
| 3 | 工作经历 | `work_experience[]` | `parsing-resumes` |
| 4 | 技能 | `skills[]`（+ 可选 `self_evaluation`） | `parsing-resumes` |
| 5 | 评估 | ranking / `score` 对象 | `scoring-candidates` |
| 6 | 来源与跟进 | `_resume_file` 等元数据 | 解析/流水线 |

**数据流（契约对齐点）：**

```
inbox 简历
  → parsed/*.json          （对齐 §2–§7、§9 解析闸）
  → profiles/*-full.json   （数据资产可含敏感字段，供统计）
  → scoring/clean/*.json   （§9 评分前物理剥离）
  → scoring/results/*      （§8 评估产出）
  → profile/output/*.html  （§9 展示闸：敏感标签零渲染）
  → talent-pool            （消费解析字段做向量）
```

**两道解析闸：**

| 闸 | 脚本 | 管什么 |
|----|------|--------|
| 形状对 | `validate_profile.js` | 字段组齐全、派生自洽、红线字段零出现 |
| 内容真 | `auditing-extraction` | 硬提取逐字回溯原文；软推断必须带标志 |

---

## §2 基础信息字段组

顶层平铺字段：

| 字段 | 必需 | 类型 | 抽取规则 |
|------|------|------|----------|
| `name` | ✓ | string | 逐字照抄；简历若标 `(男)/(女)`，括号内容**不**带进 name |
| `phone` | | string | 保持原文脱敏形态（如 `137**8845`），不还原、不补全 |
| `email` | | string | 同上，保持脱敏形态 |
| `target_position` | ✓ | string | 求职意向 / 目标岗位，逐字照抄 |
| `expected_salary` | | string | 期望薪资，逐字照抄（含「月薪/13薪」等说明） |
| `expected_city` | | string | 期望城市 |
| `available_date` | | string | 到岗时间 |

> `validate_profile.js` 强制：顶层至少有 `name`、`target_position`。

---

## §3 教育背景字段组

对象字段：`education`

| 字段 | 必需 | 说明 |
|------|------|------|
| `school` | 建议 | 学校全名（含括号英文名也保留） |
| `major` | 建议 | 专业 |
| `degree` | 建议 | 学历层次（本科/硕士/博士等） |
| `graduation_year` | 建议 | 从最高学历结束年取，如 `2017.09 - 2018.11` → `"2018"` |
| `school_tier` | 可选 | 院校层次（如 `985`/`211`/`海外`）。**可进数据资产与 parsed；评分前必须剥离（§9）** |

**规则：**

- 简历列多段学历时，`education` **只取最高学历**那一段。
- 例：某某大学3硕士 + 某某大学4本科 → 取硕士。

---

## §4 工作经历字段组

数组字段：`work_experience[]`，每段一条。

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `company` | ✓ | string | 公司名，硬提取 |
| `position` | ✓ | string | 职位，硬提取 |
| `start_date` | ✓ | string | 统一 `YYYY-MM` 或 `YYYY.MM` |
| `end_date` | ✓ | string | 同上；在职写 `"至今"` |
| `industry` | | string | **软推断**（见 §7） |
| `industry_inferred` | 条件必需 | boolean | 当 `industry` 非空时必须为 `true` |

---

## §5 技能字段组

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `skills` | ✓（组级） | string[] | 对应简历「专业技能」段，逐项照抄，不归并、不改写 |
| `self_evaluation` | | string | 自我评价自由文本（可选）。字段级黑名单清不掉其中藏匿的敏感信息，评分 prompt 仍需合规兜底声明 |

---

## §6 派生字段

派生字段**不是**从原文某处抄来，而是按工作经历**算**出来：

| 字段 | 计算方式 | 校验 |
|------|----------|------|
| `total_experience_years` | 各段工作经历时长之和（年） | 与按起止时间累加月数换算的年数偏差 ≤ 1 年 |
| `job_count` | `work_experience.length` | 必须等于数组长度 |

> **以计算值为准**：简历自述「工作年限」可能笔误或写长；schema 约定派生字段一律以可计算的客观数据为准。自述值只作参照。

---

## §7 硬提取 vs 软推断

抽取产出的字段按可信度来源分三类：

### 7.1 硬提取字段

值在简历原文有明确出处，核对标准是**逐字符匹配**（归一化后子串命中）。

| 范围 | 字段 |
|------|------|
| 顶层 | `name`, `phone`, `email`, `target_position`, `expected_salary`, `expected_city`, `available_date` |
| education | `school`, `major`, `degree` |
| work_experience | `company`, `position`, `start_date`, `end_date` |

### 7.2 软推断字段

原文没直接写，靠上下文推导。典型：`industry`（从公司名推行业）。

**工程约定：**

- 产出非空 `industry` 时，必须同时带 `"industry_inferred": true`
- 推断依据（公司名）须能在原文找到
- 下游评分 / 审计能一眼区分「简历事实」与「AI 判断」

### 7.3 派生字段

见 §6：`total_experience_years`、`job_count`——不回溯原文，只校验计算自洽。

### 7.4 对应 Skill

| 能力 | Skill / 脚本 |
|------|----------------|
| 形状校验 | `parsing-resumes` → `validate_profile.js` |
| 内容核对 | `auditing-extraction` → `audit_extraction.js` |

---

## §8 评估维度与评分产出

> 本节是**评估字段组**的契约。由 `scoring-candidates` 产出，不在解析 JSON 顶层。

### 8.1 八个固定维度（各 1–5 分）

维度清单固定，不靠 LLM 临场发明：

| 维度 | 简历阶段评分依据 |
|------|------------------|
| 专业技能 | 技能清单、项目技术、证书 |
| 经验匹配 | 行业、职级、职责与目标岗位相关性 |
| 逻辑能力 | 业绩叙述逻辑、项目复盘深度 |
| 学习力 | 技能更新、转型、学历进修 |
| 沟通能力 | 简历表述清晰度、跨团队经历 |
| 协作能力 | 团队角色、跨部门项目 |
| 抗压能力 | 高强度项目、稳定性 |
| 价值观 | 职业选择一致性、自我评价 |

对应代码常量：`score_candidate.js` 的 `DIMENSIONS`。

### 8.2 综合匹配分与评级

| 字段 | 含义 |
|------|------|
| `dimension_scores` | 8 维分数字典 |
| `dimension_reasons` | 每维一句理由 |
| `jd_match_score` | 综合匹配分 0–100。**不是** 8 维算术加权；含能力画像 + 岗位 fit（薪资/城市/年限错配） |
| `overall_rating` | A/B/C/D（脚本切分：A≥85，B≥75，C≥60，D&lt;60） |
| `score_reasoning` | 综合理由 |
| `highlights` | 亮点列表 |
| `concerns` | 顾虑（岗位匹配度问题，如薪资过高） |
| `hard_issues` | 硬伤：仅三类——工作经历时间矛盾、学历存疑、简历自相矛盾 |
| `suggested_action` | 只允许「建议进入面试候选名单」「建议人工复核」等；**禁止**「通过/淘汰」 |

### 8.3 合规边界（评估层）

- **只评分不淘汰**：最终录用/淘汰由人工决定（个保法第 24 条）。
- 数字出现在自由文本中时，必须经 `auditing-numbers` 回核（基准只能是候选人原简历，不能用 JD）。

---

## §9 合规红线与分层处置

### 9.1 底层原则

**可记录、禁评分、禁展示**（按数据流环节分别设闸）：

| 环节 | 处置 | 执行者 |
|------|------|--------|
| 数据资产 `profiles/` | 可保留敏感字段供 HR 统计 | 人工/导入 |
| 解析产出 `parsed/` | 身份类敏感字段**零出现** | `validate_profile.js` |
| 评分输入 `scoring/clean/` | 身份类 + 院校层次 + 政治面貌**物理删除** | `filter_sensitive.js` |
| HTML 画像 | 敏感标签**零渲染** | `validate_profile_html.js` |

> 核心：**不是求大模型别用敏感特征，是让它根本看不到。**

### 9.2 解析闸黑名单（`validate_profile.js`）

身份类字段（中英文键）不得出现在解析 JSON 任意层级：

- 年龄/出生：`age`, `birth`, `birthday`, `birthdate`, `date_of_birth`, `年龄`, `出生`, …
- 性别：`gender`, `sex`, `性别`
- 婚育：`marriage`, `marital`, `marital_status`, `children`, `婚育`, `婚姻`, …
- 户籍籍贯：`hukou`, `household`, `native_place`, `birthplace`, `origin`, `户籍`, `籍贯`, …
- 民族：`ethnicity`, `nation`, `race`, `民族`
- 健康：`health`, `disability`, `健康`, …

法律依据：《个人信息保护法》第 24 / 28 条，《就业促进法》第 26–31 条。

### 9.3 评分闸黑名单（`filter_sensitive.js`）

在解析闸基础上**额外**剥离：

| 类别 | 键名示例 | 定性 |
|------|----------|------|
| 院校层次 | `school_tier`, `school_rank`, `院校层次`, `第一学历` | 政策强烈反对（间接歧视） |
| 政治面貌 | `political_status`, `政治面貌` | 个保法 §28「等」从严保护 |

并配合 `FORBIDDEN_STEMS` 词干自检（兜住驼峰/变体）；自检残留 → 退出码 1，绝不放行。

### 9.4 展示闸

画像 HTML 不得出现敏感中文标签：`出生年月`、`性别`、`婚育`、`政治面貌`、`户籍`、`籍贯`、`民族`、`健康状况` 等。

---

## §10 来源与跟进元数据

| 字段 | 说明 |
|------|------|
| `_resume_file` | 来源简历文件名（如 `resume-tech-员工1-后端开发.md`） |
| `resume_json` | ranking 明细中指向结构化文件的路径/名 |
| `audited_at` / `audited/*.audit.json` | 抽取核对产物时间与报告 |

跟进状态（面试进度、offer 等）可在业务侧扩展，本课交付以解析/评分/画像链路为主。

---

## 附录 A · 最小合法 JSON 示例

对齐 `parsed/员工1-后端开发.json` 的形状（节选）：

```json
{
  "name": "员工1",
  "target_position": "后端技术专家 / 后端架构师",
  "expected_salary": "60K-75K",
  "expected_city": "上海",
  "available_date": "一个月内",
  "education": {
    "school": "某某大学1",
    "major": "软件工程",
    "degree": "硕士",
    "graduation_year": "2018",
    "school_tier": "985"
  },
  "work_experience": [
    {
      "company": "某某公司1",
      "position": "后端技术专家",
      "start_date": "2018.04",
      "end_date": "至今",
      "industry": "电商",
      "industry_inferred": true
    }
  ],
  "total_experience_years": 14.8,
  "job_count": 1,
  "skills": ["Java", "Go", "微服务架构"],
  "self_evaluation": "……",
  "_resume_file": "resume-tech-员工1-后端开发.md"
}
```

**注意：**

- `school_tier` 可出现在 parsed / profiles；进入评分前必须被 `filter_sensitive.js` 删掉。
- `industry` 非空时必须有 `industry_inferred: true`，否则 `validate_profile.js` 失败。
- `job_count` 必须等于 `work_experience.length`。

---

## 附录 B · 与代码落点对照

| Schema 章节 | 权威代码 / 文档 |
|-------------|-----------------|
| §2–§6 解析结构 | `skills/parsing-resumes/references/field-extraction.md` |
| §6–§7 校验 | `skills/parsing-resumes/scripts/validate_profile.js` |
| §7 核对 | `skills/auditing-extraction/scripts/audit_extraction.js` |
| §8 维度 | `skills/scoring-candidates/scripts/score_candidate.js` → `DIMENSIONS` |
| §8 方法 | `skills/scoring-candidates/references/scoring-method.md` |
| §9 评分剥离 | `skills/filtering-sensitive-fields/scripts/filter_sensitive.js` |
| §9 政策说明 | `skills/filtering-sensitive-fields/references/sensitive-fields.md` |
| §9 展示 | `skills/generating-candidate-profiles/scripts/validate_profile_html.js` |

---

*本文档由手册（pre_docs/3、4）与 `workspace-recruitment` 落盘脚本/样例交叉还原。若与运行脚本冲突，以脚本强制校验为准，并回写本契约。*
