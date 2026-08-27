# TOOLS.md - 入职子 Agent 的能力清单

本文件列我手上有哪些入职业务 Skill、各自做什么、什么时候用、调用要点。
Skill 的完整用法看各自的 `SKILL.md`，这里是速查。

## 架构原则

**HCM 系统是花名册与五部门节点的唯一真相源。** 小慧只从 HCM 读取数据，不向 HCM 写入。

```
各部门 → HCM 系统（唯一真相源）
              ↓ 只读 GET
           小慧（Agent）
              ↓ 流程推进、提醒、review 通知
           HR / 主管
```

- 花名册、五部门准备节点、review 记录 → 全部由各部门 / HR / 主管在 HCM 维护
- 小慧的职责：查询 HCM 状态 → 推进审批流程 → 通知相关人员
- 审批门（contract_gate / account_gate）是 Lobster 工作流概念，HCM 无此字段，仍读本机 `workflow.json`

## 入职业务 Skill 清单

### running-onboarding-workflow —— 入职审批工作流

- **做什么**：用 Lobster 工作流引擎跑一名新员工的入职审批流程——4 路并行准备（合同/账号/设备/培训）+ 2 个 HiTL 审批门（合同审批、账号权限审批）。
- **什么时候用**：一名新员工确定录用、要走入职流程时。
- **数据来源**：HCM API 只读校验花名册 + 各准备脚本从 HCM 读取部门数据；本地 `stub-state/` 供工作流状态追踪。
- **调用要点**：
  - 启动：`run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>`，跑到第一个审批门 halt。
  - 推进：`run-onboarding.sh resume <resumeToken> yes|no`，批准/拒绝一个审批门。
  - halt 时返回的 `resumeToken` 必须原样留存交回——它是 resume 的唯一钥匙。
  - 审批门是给人的：把 **prompt 原文** + resumeToken 交回给人，绝不替人批准。

### querying-onboarding-status —— 入职状态查询

- **做什么**：查询某新员工的入职状态（花名册 + 五部门节点来自 HCM，审批门来自本地 workflow.json）。
- **什么时候用**：HR 问「某人入职到哪一步了」时。
- **数据来源**：花名册与五部门节点 → HCM API；审批门/resumeToken → 本机 `workflow.json`。
- **调用要点**：`query-onboarding-status.sh <姓名> [pinyin]`。HCM 不可达时 exit 5，不用本地数据冒充。

### running-onboarding-review —— 入职跟进 review

- **做什么**：按入职天数（7/30/60/90 天）查询入职跟进 review 状态，生成报告供通知 HR/主管。
- **什么时候用**：Cron 定时任务到点触发时；或需要手动查某员工某天的跟进状态时。
- **数据来源**：全部来自 HCM API（只读）。不写入 HCM、不写本地 `review-state/`。
- **调用要点**：`onboarding-review.sh <姓名> <入职天数> [pinyin]`。review 记录的维护权归 HR/主管，小慧只查询并通知。

### generating-onboarding-dashboard —— 入职进度看板

- **做什么**：从 HCM API 读取所有新员工的 9 个节点状态（5 准备 + 4 review），生成可视化 HTML 看板并发布到 Canvas。
- **什么时候用**：需要总览所有新员工入职进度时。
- **数据来源**：HCM API（只读）+ 本机 `workflow.json`（审批门角标）。不读本地 `stub-state/` 作为准备节点真相源。
- **调用要点**：
  - 仅生成：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh`
  - 生成并发布：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force`
  - canvas-id 固定 `onboarding-dashboard`；浏览器看 `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html`

## 本地环境特定信息

- 审批门状态和 resumeToken 仍在 `stub-state/<pinyin>/workflow.json`（Lobster 工作流落盘）。
- `pending-approvals/` 目录存审批门暂停快照。
- 两个 `hcm_api.py` 副本（workflow 和 review 各一份）为只读客户端，不含写入方法。
