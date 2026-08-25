# 入职审批工作流设计细则

> running-onboarding-workflow Skill 的工作流设计依据。SKILL.md 在需要时引用本文件。
> 工作流文件：`scripts/hr-onboarding.lobster`。设计依据：hr-wiki《09-入职流程》。

## 目录

- 1. 五个节点
- 2. 4 路并行：为什么是这 4 条、怎么实现的
- 3. 两个 HiTL 审批门：为什么设在合同和账号
- 4. stub 系统：为什么用 stub
- 5. Lobster 工作流的两个工程约束

## 1. 五个节点

| 节点 | step id | 类型 | 说明 |
|---|---|---|---|
| 4 路并行准备 | `prep` | shell（单 step 内并行）| 合同 / IT 账号 / 设备 / 培训 4 条工作并行推进 |
| 合同审批门 | `contract_gate` | run + approval | HiTL：HR 主管审批劳动合同后才能进签约 |
| 账号权限审批门 | `account_gate` | run + approval | HiTL：IT 安全负责人核准账号权限范围 |
| Buddy 匹配 | `buddy` | shell（条件执行）| 两个审批门都通过后，为新员工匹配带教导师 |
| 入职归档 | `complete` | shell（条件执行）| 全部审批通过，五项就绪，归档 |

节点 4、5 带 `when: $contract_gate.approved && $account_gate.approved`——只有两个审批门都批准才执行。

## 2. 4 路并行：为什么是这 4 条、怎么实现的

**为什么并行**：合同、账号、设备、培训四件准备工作之间没有依赖关系——准备合同不需要等账号开通，排培训不需要等设备到位。没有依赖就能并行。人工 HR 一项一项 ping IT、行政、培训部门，总耗时是 4 条之和；并行后总耗时取决于最慢的 1 条。

**怎么实现**：Lobster 工作流文件的 steps 是**严格串行**的——`runWorkflowFile` 按数组顺序一个接一个跑，没有 `needs` / `parallel` 这类声明式并行 key。所以"4 路并行"不能靠"写 4 个并列 step 让 Lobster 自己调度"，要在**单个 `run` step 内部**用 shell 后台任务做：

```bash
( bash "$STUB/contract.sh"   "${name}" "${role}" "${salary}" ) &
( bash "$STUB/it-account.sh" "${name}" "${pinyin}" ) &
( bash "$STUB/device.sh"     "${name}" ) &
( bash "$STUB/training.sh"   "${name}" ) &
wait
```

一个 `run` step 里启 4 个后台子 shell，`wait` 等全部结束。这是操作系统级的真并行。

> Buddy 匹配为什么不进并行：它有依赖——只有合同和账号都批准、确认这个人真要入职，才值得占用一位资深员工的带教精力。所以 Buddy 放在审批门之后。

## 3. 两个 HiTL 审批门：为什么设在合同和账号

合同审批、账号权限审批这两个节点是"有责任的不可逆决策"：

- **合同条款**定了法律责任，不能让 AI 单独拍板。
- **账号权限范围**定了系统访问边界，开通后即拥有访问权限，必须人工核准。

设备申请、培训排期是低风险事务性工作，不设审批门。**审批门设在哪里是业务判断，不是技术决定。**

审批门的实现：每个审批步骤同时带 `run` 和 `approval: true`。`run` 读对应的 stub 状态文件、用 python 拼出一段带 `prompt` 字段的 JSON（prompt 里已填好候选人专属信息），`approval: true` 标记它是审批门。流程跑到这里 halt，把 `json.prompt` 作为审批问题交出来。

## 4. stub 系统：为什么用 stub

账号、设备申请本课不接真实 IT 系统。5 个 stub 脚本（与工作流文件同在 `scripts/`）各模拟一个企业系统：

| stub 脚本 | 模拟的系统 | 产出 |
|---|---|---|
| `contract.sh` | 合同文件系统 | `contract.json`（status=待审批）|
| `it-account.sh` | IT 账号系统 | `account.json`（工号 + 邮箱 + 企业微信）|
| `device.sh` | 行政设备系统 | `device.json`（笔记本 + 门禁卡 + 工位）|
| `buddy.sh` | Buddy 匹配系统 | `buddy.json`（Buddy + 导师）|
| `training.sh` | 培训安排系统 | `training.json`（Onboarding 第一课排期）|

每个 stub 把"已申请/已开通"的结构化状态写成 JSON 文件落到 workspace 根的 `stub-state/`，再 echo 一行进度。真实环境里这些 stub 换成调用企业微信 API、IT 工单系统、AD 域控的真实接口——工作流文件本身不用动，只换 stub 脚本的实现。

> stub 状态产出落在 workspace 根的 `stub-state/`，不是落在本 Skill 目录里——因为 `running-onboarding-review`（Cron review）和 `generating-onboarding-dashboard`（看板）两个下游 Skill 都要读这些状态文件。它是跨 Skill 共享的数据资产。

## 5. Lobster 工作流的两个工程约束

这两条是读 `@clawdbot/lobster` 编译产物才发现的、文档不写的坑：

### 约束 1 · `approval:` 字段不做模板替换

`run` / `command` / `pipeline` / `stdin` 都过 `resolveTemplate`（做 `${arg}` 替换），唯独 `step.approval` 不过。所以审批问题不能直接写在 `approval:` 字段里（`${name}` 不会被替换）。绕过办法：审批步骤同时带 `run`（产出带 `prompt` 字段的 JSON）和 `approval: true`，Lobster 用 `run` 产出的 `json.prompt` 当审批问题——`run` 是过模板替换的。

### 约束 2 · `env` 块覆盖外部环境变量，所以本工作流文件不写死路径

Lobster 工作流文件的 `env` 块优先级高于外部环境变量。如果在 `env` 块里写死 `STUB` / `STATE` 的绝对路径，工作流就和某个固定路径绑死、不可移植。所以本工作流文件**不写 `env` 块**，`$STUB` / `$STATE` 由启动脚本 `run-onboarding.sh` 在调 lobster 前 export 进环境——`run` step 是 shell，会继承外部环境变量。启动脚本由自身位置反推这两个路径，不依赖调用方在哪个目录。
