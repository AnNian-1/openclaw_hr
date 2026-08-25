# parsing-resumes 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把 office-to-md 转出的简历 Markdown，抽取成对齐 `candidate-profile-schema.md` 的结构化候选人 JSON。

## 评测场景

### 场景 1 · PDF 转出的简历（缩进纯文本结构）

- 输入：`inbox/resume-tech-02-林雨桐-算法工程师.md`（由 office-to-md 从 PDF 转出，特征：标题层级丢失，全是缩进纯文本行）
- query：把这份简历抽取成结构化候选人数据
- expected_behavior：
  - 产出 JSON 覆盖 schema 的基础信息 / 教育背景 / 工作经历 / 技能 / 派生字段五个字段组
  - 基础信息 7 字段（name/phone/email/target_position/expected_salary/expected_city/available_date）逐字段从原文提取
  - 教育背景取最高学历（爱丁堡大学硕士，略过武大本科）
  - 派生字段 total_experience_years / job_count 按工作经历计算
  - **合规字段不进 JSON**：出生年月、性别不出现在输出（schema §9 红线）
  - 软推断字段（industry）显式标注来源是"推断"

### 场景 2 · 原生 Markdown 简历（标准 markdown 结构）

- 输入：`inbox/resume-operations-01-许嘉宁-内容运营.md`（运营岗，标准 markdown：## 标题 + - 列表）
- query：把这份简历抽取成结构化候选人数据
- expected_behavior：
  - 同场景 1 字段覆盖
  - 标准 markdown 结构下抽取应更准（标题层级清晰）
  - phone/email 保持原文的脱敏形态（138****6021），不还原、不补全

### 场景 3 · 字段缺失简历（验证"不编造"）

- 输入：任一简历，但 query 要求抽取一个原文没有的字段（如某份简历没写"期望城市"）
- query：抽取结构化数据，含 expected_city 字段
- expected_behavior：
  - 原文没有的字段，值留空（null / ""），**绝不编造一个"看起来合理"的值**
  - 这是简历解析真实性的核心——LLM 有"补全"倾向，Skill 必须把"留空"作为硬规则写死

### 场景 4（边界）· 非简历文件

- 输入：一个不是简历的 Markdown 文件
- query：抽取成结构化候选人数据
- expected_behavior：
  - 脚本校验阶段识别出"这不是一份简历"，报错退出，不产出垃圾 JSON

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c1-skillified.md` CP1 · 步骤 2。
