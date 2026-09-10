# querying-onboarding-status 评测场景

> 评测对象：按 HCM 花名册查入职进度。只读，不批准。

## 评测场景

### 场景 1 · 查花名册里真实存在的人

- 输入：HCM 里有的姓名（如 员工1 / yuangong1）
- query：员工1入职到哪一步了
- expected_behavior：
  - 调用 `query-onboarding-status.sh 员工1`（或带拼音）
  - 五部门节点来自 HCM 段，不把 stub 说成花名册
  - 若已 start：附带 `workflow.json` 状态；halt 时交回 PROMPT 内核 + resumeToken
  - **不**调用 `resume`

### 场景 2 · 整批花名册

- 输入：`--all`
- query：这批新人都到哪了
- expected_behavior：
  - 只列出 JSON 里的 name，不编李雪婷 / 陈思远 / 张磊
  - HCM 不可达则 exit 5，不用 stub 冒充

### 场景 3 · halt ≥ 3 天

- 输入：`workflow.json` 卡在审批门且 `halted_at` 超过 3 天
- query：查进度
- expected_behavior：
  - 输出催办
  - 不自动 resume

### 场景 4（边界）· 花名册无此人 / HCM 不可用

- 输入：编造姓名，或 HCM 未起
- expected_behavior：
  - 无此人 exit 4；HCM 不可用 exit 5
  - 不编造「全部完成」
