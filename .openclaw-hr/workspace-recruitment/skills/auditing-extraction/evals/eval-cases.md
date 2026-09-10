# auditing-extraction 评测场景

> 评测对象：把 parsing-resumes 抽出的候选人 JSON 逐字段回溯简历原文。
> 用本仓真实路径；不要写课程已删除的 `resume-tech-03-候选人E`。

## 评测场景

### 场景 1 · 干净产出（应通过）

- 输入：`parsed/员工1-后端开发.json` + `inbox/resume-tech-员工1-后端开发.md`（或同人的 `inbox/员工1-后端开发.md`，以实际抽取源为准）
- query：核对这份解析产出，确认每个字段都真来自简历
- expected_behavior：
  - 硬提取字段可逐字回溯到原文
  - 软推断字段带 `industry_inferred: true`、推断依据（公司名）在原文
  - 派生字段计算依据成立
  - 退出码 0，报告落 `audited/<简历名>.audit.json`

### 场景 2 · 软推断字段漏标注（应报错）

- 输入：一份 `industry` 有值但缺 `industry_inferred` 的 parsed JSON + 对应原文
- expected_behavior：核对抓出漏标注，退出码 1，逐条列出问题字段

### 场景 3 · 硬提取字段被编造（应精确抓出）

- 输入：故意把 `expected_salary` 或 `school` 改成原文没有的值
- expected_behavior：精确抓出被篡改字段；带括号值不能被补充词放水；退出码 1

### 场景 4（边界）· 文件缺失

- expected_behavior：退出码 2，不产出虚假核对结果
