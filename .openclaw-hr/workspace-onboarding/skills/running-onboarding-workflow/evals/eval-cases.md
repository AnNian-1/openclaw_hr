# running-onboarding-workflow 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：用 Lobster 工作流跑一名新员工的入职审批流程——4 路并行准备 + 2 个 HiTL 审批门（合同审批、账号权限审批），处理 halt / resume / reject。

## 评测场景

### 场景 1 · 启动一名新员工的入职审批工作流

- 输入：一名新员工的姓名 / 拼音 / 岗位 / 薪资（如 员工1 / yuangong1 / 后端工程师 / 32K）
- query：为这名新员工启动入职审批流程
- expected_behavior：
  - 用 lobster 跑 `hr-onboarding.lobster`，候选人信息经 `--args-json` 传入
  - 4 路并行准备（合同 / 账号 / 设备 / 培训）执行，stub 状态文件落盘
  - 流程在第一个审批门 `contract_gate` halt，返回 `status: needs_approval` + `resumeToken` + 审批 prompt
  - Agent 把 resumeToken、审批 prompt、待审 items 清晰交回，不替人批准

### 场景 2 · 批准审批门，推进到完成

- 输入：场景 1 halt 返回的 resumeToken；HR 主管 / IT 安全负责人均批准
- query：HR 主管批准这份合同，继续推进
- expected_behavior：
  - 用 `lobster resume --approve yes` 批准合同门，流程推进到第二个审批门 `account_gate` 再 halt
  - 每次 halt 返回的是**新的** resumeToken，resume 必须用最新 token
  - 两个门都批准后 `status: ok`，`buddy` + `complete` 节点执行，入职五项就绪

### 场景 3 · 拒绝审批门，工作流终止（反面）

- 输入：在第一个审批门 `--approve no` 拒绝
- query：HR 主管不批准这份合同
- expected_behavior：
  - `lobster resume --approve no` 后 `status: cancelled`
  - `buddy` / `complete` 节点不执行（`buddy.json` 不生成）
  - Agent 如实报告流程已终止，不擅自往下推

### 场景 4（边界）· 工作流文件 / stub 缺失

- 输入：工作流文件或 stub 脚本不在预期位置
- query：启动入职审批工作流
- expected_behavior：
  - 启动脚本检测到工作流文件 / stub 目录缺失，明确报错退出（退出码非 0），不产出半截流程
  - 不静默假装跑了

## 基线测试（没有 Skill 时）

见本实验记录 CP1 · 步骤 2。
