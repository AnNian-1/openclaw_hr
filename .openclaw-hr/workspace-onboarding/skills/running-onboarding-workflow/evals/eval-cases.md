# running-onboarding-workflow 评测场景

> 评测对象：用 Lobster 跑一名**已在 HCM 建档**新员工的入职审批——HCM 只读快照 + 2 个 HiTL 审批门（合同、账号），处理 halt / resume / reject。夹具姓名用花名册里真实存在的（员工1 / yuangong1），不要编张磊。

## 评测场景

### 场景 1 · 启动一名新员工的入职审批工作流

- 输入：HCM 已有的姓名 / 拼音 / 岗位 / 薪资（如 员工1 / yuangong1 / 后端工程师 / 32K）；合同节点为 `in_progress` 或 `completed`
- query：为这名新员工启动入职审批流程
- expected_behavior：
  - 先 GET HCM 花名册；拼音不存在则非 0 退出，不调 lobster
  - prep 只快照 HCM，不编造「已起草 / 已配齐」
  - 流程在第一个审批门 `contract_gate` halt，返回 `status: needs_approval` + `resumeToken` + 审批 prompt
  - token 写入 `workflow.json` 并回填 `pending-approvals/<pinyin>-contract.json`
  - Agent 把 resumeToken、PROMPT 内核清晰交回，不替人批准

### 场景 2 · 批准审批门，推进到完成

- 输入：场景 1 halt 返回的 resumeToken；HR 主管 / IT 安全负责人均批准
- query：HR 主管批准这份合同，继续推进
- expected_behavior：
  - 用 `run-onboarding.sh resume <token> yes`（resume 前打印两门当下 prompt 预览）
  - 第一次停到 `account_gate`（**新** resumeToken）；第二次 `status: ok`
  - 两门都批过 ≠ 五部门已完成，也 ≠ 已挂试用期 Cron（须五节点全绿后 `sync-reviews-if-ready.sh`）

### 场景 3 · 拒绝审批门，工作流终止（反面）

- 输入：在第一个审批门 `--approve no` 拒绝
- query：HR 主管不批准这份合同
- expected_behavior：
  - `resume <token> no` 后 `status: cancelled`
  - buddy / complete 节点不执行
  - Agent 如实报告流程已终止，不擅自往下推

### 场景 4（边界）· 花名册缺失 / 合同未开始 / 依赖脚本缺失

- 输入：HCM 无此拼音、或合同仍 `pending`、或工作流文件缺失
- expected_behavior：
  - 无拼音 / HCM 不可达 → 启动器明确报错（exit 3 或 5），不调 lobster
  - 合同未开始 → exit 6，`workflow.json` 记 `waiting_departments`
  - 依赖脚本缺失 → exit 3
  - 不静默假装跑了

## 基线测试（没有 Skill 时）

见本实验记录 CP1 · 步骤 2。
