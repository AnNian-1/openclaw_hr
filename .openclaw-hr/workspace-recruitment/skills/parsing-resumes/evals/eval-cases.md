# parsing-resumes 评测场景

> 评测对象：把简历 Markdown 抽取成对齐 `candidate-profile-schema.md` 的结构化候选人 JSON。
> 本仓 inbox 用 `resume-<类>-员工N-岗位.md` 与邮件落盘名；不要用课程里已删除的「候选人A/林雨桐」路径。

## 评测场景

### 场景 1 · 技术岗 Markdown（标准结构）

- 输入：`inbox/resume-tech-员工1-后端开发.md`
- query：把这份简历抽取成结构化候选人数据
- expected_behavior：
  - 产出 JSON 覆盖 schema 的基础信息 / 教育背景 / 工作经历 / 技能 / 派生字段
  - 基础信息字段从原文提取；原文没有的留空
  - 派生字段 `total_experience_years` / `job_count` 按工作经历计算，不取自述值
  - **合规字段不进 JSON**：年龄、性别、婚育等红线字段不出现
  - 软推断字段（`industry`）带 `industry_inferred: true`
  - 本公司/前雇主按简历原文占位呈现（某某公司 / 某某公司1），不改成「星桥」

### 场景 2 · 运营岗 Markdown

- 输入：`inbox/resume-operations-员工5-增长运营.md`
- query：抽取结构化候选人数据
- expected_behavior：同场景 1 字段覆盖；phone/email 保持原文脱敏形态，不还原、不补全

### 场景 3 · 字段缺失（验证「不编造」）

- 输入：任一本仓简历，query 要求抽取原文没有的字段（如没写期望城市）
- expected_behavior：该字段留空（null / ""），绝不编造「看起来合理」的值

### 场景 4（边界）· 非简历文件

- 输入：一个不是简历的 Markdown
- expected_behavior：校验阶段识别并报错退出，不产出垃圾 JSON
