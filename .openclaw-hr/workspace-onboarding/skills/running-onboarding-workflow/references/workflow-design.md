# 入职审批工作流设计细则

> running-onboarding-workflow Skill 的工作流设计依据。SKILL.md 在需要时引用本文件。
> 工作流文件：`scripts/hr-onboarding.lobster`。设计依据：hr-wiki《09-入职流程》。

## 目录

- 1. 五个节点
- 2. 准备节点：只读 HCM，不代替部门执行
- 3. 两个 HiTL 审批门：为什么设在合同和账号
- 4. 本地快照：为什么还有 stub-state
- 5. Lobster 工作流的两个工程约束

## 1. 五个节点

| 节点 | step id | 类型 | 说明 |
|---|---|---|---|
| HCM 快照 | `prep` | shell | 只读快照合同 / IT / 设备 / 培训；不编造部门产出 |
| 合同审批门 | `contract_gate` | run + approval | HiTL：HR 主管审批劳动合同后才能进签约 |
| 账号权限审批门 | `account_gate` | run + approval | HiTL：IT 安全负责人核准账号权限范围 |
| Buddy 快照 | `buddy` | shell（条件执行）| 两道门都通过后，再快照 HCM Buddy 节点 |
| 入职归档 | `complete` | shell（条件执行）| 审批走通后归档；**不**无条件挂试用期 Cron |

节点 4、5 带 `when: $contract_gate.approved && $account_gate.approved`——只有两个审批门都批准才执行。

**进门 vs 开通跟进：**

| 条件 | 要求 |
|------|------|
| 进入合同审批门 | HCM 合同节点 `in_progress` **或** `completed`（`GATE_READY_STATUSES`） |
| 开通 7/30/60/90 跟进 | HCM **五**节点均为 `completed`（`DONE_STATUSES`） |

Lobster `complete`（两道门都批过）≠ 各部门已执行完毕。跟进只由 `sync-reviews-if-ready.sh` 开通（归档钩子或 HR 显式执行）。**查询进度和看板刷新只读，不挂 Cron。**

## 2. 准备节点：只读 HCM，不代替部门执行

合同、账号、设备、培训、Buddy 是**各部门在 HCM 上的工作**，不是入职小慧的工作。小慧只 GET 进度、向 HR 汇报/催办。

历史上 prep 曾并行跑 4 个 stub、编造「劳动合同已起草 / 设备已配齐 / Buddy 王工」，等于替其它部门干活。现已改为：

```bash
python3 "$STUB/snapshot_hcm_prep.py" "${pinyin}" --name "${name}" \
  --nodes contract,account,device,training
```

`contract.sh` / `it-account.sh` / `device.sh` / `training.sh` / `buddy.sh` 都是该快照的薄封装：写出真实 `hcm_status`，**禁止**编造字段。

合同仍为 `pending` 时，`run-onboarding.sh start` 退出 **6**，`workflow.json` 记 `waiting_departments`，不启动 lobster。部门补齐后可再次 `start`。

## 3. 两个 HiTL 审批门：为什么设在合同和账号

合同审批、账号权限审批这两个节点是"有责任的不可逆决策"：

- **合同条款**定了法律责任，不能让 AI 单独拍板。
- **账号权限范围**定了系统访问边界，开通后即拥有访问权限，必须人工核准。

设备申请、培训排期是部门事务，不由小慧执行，也不设第三道门。账号门 prompt 会带上账号/设备/培训的 HCM 状态；仍为 `pending` 时写明**请勿批准**，先催部门。

审批门的实现：每个审批步骤同时带 `run` 和 `approval: true`。`run` 读 HCM（及本地快照）、用 python 拼出带 `prompt` 的 JSON，`approval: true` 触发 halt。

## 4. 本地快照：为什么还有 stub-state

HCM 没有审批门 / resumeToken。本机 `stub-state/<pinyin>/` 只承担：

| 文件 | 作用 |
|---|---|
| `contract.json` 等 | HCM 节点的只读快照，供拼审批 prompt、halt 对比 |
| `workflow.json` | Lobster 扭转、halt、resumeToken |

快照脚本**不编造**工号、资产号、导师姓名。字段以 HCM `nodes[].data` 为准，没有就空着。

> 产出仍落在 workspace 根的 `stub-state/`，因为查询 Skill、看板、审批 prompt 都要读。试用期跟进另存在 `review-state/reviews.json`。

## 5. Lobster 工作流的两个工程约束

这两条是读 `@clawdbot/lobster` 编译产物才发现的、文档不写的坑：

### 约束 1 · `approval:` 字段不做模板替换

`run` / `command` / `pipeline` / `stdin` 都过 `resolveTemplate`（做 `${arg}` 替换），唯独 `step.approval` 不过。所以审批问题不能直接写在 `approval:` 字段里（`${name}` 不会被替换）。绕过办法：审批步骤同时带 `run`（产出带 `prompt` 字段的 JSON）和 `approval: true`，Lobster 用 `run` 产出的 `json.prompt` 当审批问题——`run` 是过模板替换的。

### 约束 2 · `env` 块覆盖外部环境变量，所以本工作流文件不写死路径

Lobster 工作流文件的 `env` 块优先级高于外部环境变量。如果在 `env` 块里写死 `STUB` / `STATE` 的绝对路径，工作流就和某个固定路径绑死、不可移植。所以本工作流文件**不写 `env` 块**，`$STUB` / `$STATE` 由启动脚本 `run-onboarding.sh` 在调 lobster 前 export 进环境——`run` step 是 shell，会继承外部环境变量。启动脚本由自身位置反推这两个路径，不依赖调用方在哪个目录。
