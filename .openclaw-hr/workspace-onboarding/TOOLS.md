# TOOLS.md - 入职子 Agent 的能力清单

本文件列我手上有哪些入职业务 Skill、各自做什么、什么时候用、调用要点。
Skill 的完整用法看各自的 `SKILL.md`，这里是速查。

## 入职业务 Skill 清单

### running-onboarding-workflow —— 入职审批工作流

- **做什么**：用 Lobster 工作流引擎跑一名新员工的入职审批流程——4 路并行准备（合同/账号/设备/培训）+ 2 个 HiTL 审批门（合同审批、账号权限审批）。
- **什么时候用**：一名新员工确定录用、要走入职流程时。
- **调用要点**：
  - 启动：`run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>`，跑到第一个审批门 halt。
  - 推进：`run-onboarding.sh resume <resumeToken> yes|no`，批准/拒绝一个审批门。
  - halt 时返回的 `resumeToken` 必须原样留存交回——它是 resume 的唯一钥匙，`approvalId` 不能代替。
  - 每个审批门 halt 生成一个新 token，下次 resume 用最新的。
  - 审批门是给人的：把 **prompt 原文** + resumeToken 交回给人，绝不替人批准。prompt 必须原样展示（含状态；配套文件仅在有数据时出现），禁止自造表格漏字段。

### running-onboarding-review —— 入职跟进 review

- **做什么**：按入职天数（7/30/60/90 天）跑一次入职跟进 review，读入职工作流的 5 节点真实状态，产出结构化 review 报告。
- **什么时候用**：Cron 定时任务到点触发时；或需要手动跑一次某员工的跟进 review 时。
- **调用要点**：`run-review.sh <姓名> <入职天数>`。review 状态落盘到 workspace 根的 `review-state/`，看板会读它。Cron 注册本身是调度配置，不属于这个 Skill。

### generating-onboarding-dashboard —— 入职进度看板

- **做什么**：把每个新员工入职流程的 9 个节点状态（5 准备节点 + 4 review 节点）汇成一张可视化 HTML 看板，并可发布到 OpenClaw Canvas。
- **什么时候用**：需要总览所有新员工入职进度、看谁卡在哪一步时。
- **调用要点**：
  - 仅生成：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh`
  - 生成并发布：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force`
  - canvas-id 固定 `onboarding-dashboard`；浏览器看 `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html`
  - 数据全部读自真实落盘文件（`stub-state*` + `review-state` + `workflow.json`），不编造。状态变了重跑并 `--force` 覆盖 Canvas。

## 本地环境特定信息

- 入职流程的 stub 状态文件落在 workspace 根的 `stub-state/`（含张磊、郭超、李四、李鑫、雷武等员工数据）。
- review 状态文件落在 workspace 根的 `review-state/`，文件名格式为 `review-<中文名>-<type>.json`。
- 三个 Skill 共享这两类状态文件：工作流写、review 读+写、看板只读。
