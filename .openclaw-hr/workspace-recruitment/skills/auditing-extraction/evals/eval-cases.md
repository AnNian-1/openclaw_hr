# auditing-extraction 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测「没有 Skill 时的基线表现」，再写最小 SKILL.md，按观察迭代。
> 评测对象：把 parsing-resumes 抽取出的候选人 JSON 逐字段回溯简历原文，核对真实性、产出可追溯率。

## 评测场景

### 场景 1 · 干净产出（迭代后的标准件，应通过）

- 输入：`parsed/resume-tech-03-候选人E-前端开发.json` + `inbox/resume-tech-03-候选人E-前端开发.md`
- query：核对这份解析产出，确认每个字段都真来自简历
- expected_behavior：
  - 18 个硬提取字段 100% 可逐字回溯到原文
  - 2 个软推断字段（industry）均带 `industry_inferred: true`、推断依据（公司名）成立
  - 2 个派生字段计算依据成立
  - 核对通过，退出码 0
  - 产出核对报告 `audited/resume-tech-03-候选人E-前端开发.audit.json`

### 场景 2 · 软推断字段漏标注（应报错）

- 输入：`parsed/resume-tech-02-候选人A.json` + `inbox/resume-tech-02-候选人A-算法工程师.md`
- 说明：这份 JSON 是 CP1 迭代前的产出，`work_experience` 里的 `industry`（内容社区 / 短视频）没有带 `industry_inferred` 标志
- query：核对这份解析产出的真实性
- expected_behavior：
  - 18 个硬提取字段仍 100% 可逐字回溯（硬字段本身没问题）
  - **核对抓出 2 处软推断字段漏标注**：`work_experience[0].industry`、`work_experience[1].industry` 缺 `industry_inferred: true`
  - 核对不通过，退出码 1，逐条列出问题字段
  - 这正是真实性核对的价值——它能发现「parsing-resumes 抽得不规范」的产出

### 场景 3 · 硬提取字段被编造（应精确抓出）

- 输入：一份被故意篡改的候选人 JSON——某个硬提取字段的值改成简历原文里没有的（如 expected_salary 改成原文没有的薪资、school 改成原文没有的学校）
- query：核对这份解析产出，确认每个字段都真来自简历
- expected_behavior：
  - **核对精确抓出被篡改的硬提取字段**，报「在简历原文找不到出处，疑似编造/笔误，需人工核实」
  - 其余未篡改字段不误报
  - 可追溯率相应下降（如 16/18 → 88.9%）
  - 核对不通过，退出码 1
  - 关键：带括号补充说明的值被篡改核心部分时（如 `30K-40K（月薪）`，「月薪」在原文里、`30K-40K` 是编造的），核对不能被括号里的通用词放水，照样要判不可追溯

### 场景 4（边界）· 文件缺失

- 输入：parsed JSON 或简历原文有一个不存在
- query：核对真实性
- expected_behavior：
  - 脚本识别文件缺失，报错退出（退出码 2），不产出虚假核对结果

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c1-skillified.md` CP2 · 步骤 2。
