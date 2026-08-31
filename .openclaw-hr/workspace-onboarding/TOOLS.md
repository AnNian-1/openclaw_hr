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

- 花名册、五部门准备节点 → 各部门在 HCM 维护（小慧只读）
- 试用期 7/30/60/90 跟进 → 本机 `review-state/reviews.json`（HR 确认后小慧 `review-store.sh mark-done`）
- 小慧的职责：查询 HCM 准备状态 + 本地跟进表 → 推进审批流程 → 通知相关人员
- 审批门（contract_gate / account_gate）是 Lobster 工作流概念，HCM 无此字段，仍读本机 `workflow.json`

## 入职业务 Skill 清单

### running-onboarding-workflow —— 入职审批工作流

- **做什么**：用 Lobster 跑一名新员工的入职**审批**流程——从 HCM 只读快照五部门节点 + 2 个 HiTL 审批门。不代替其它部门在 HCM 填节点。
- **什么时候用**：一名新员工确定录用、要走入职审批时。
- **数据来源**：HCM GET 花名册与节点；本地 `workflow.json` 管审批门。
- **调用要点**：
  - 启动：`run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>`。合同节点未开始则退出 6，催部门后重试。
  - 推进：`run-onboarding.sh resume <resumeToken> yes|no`。
  - halt 时的 `resumeToken` 必须原样留存。材料 pending 时不要建议批准。
  - 两道门批完 ≠ 试用期跟进已挂；须五节点 `completed`。

### querying-onboarding-status —— 入职状态查询

- **做什么**：查询某新员工的入职状态（花名册 + 五部门节点来自 HCM，审批门来自本地 workflow.json）。
- **什么时候用**：HR 问「某人入职到哪一步了」时。
- **数据来源**：花名册与五部门节点 → HCM API；审批门/resumeToken → 本机 `workflow.json`。
- **调用要点**：`query-onboarding-status.sh <姓名> [pinyin]`。查到人后会尝试 `sync-reviews-if-ready`（五节点未齐则跳过）。HCM 不可达时 exit 5。

### running-onboarding-review —— 入职跟进 review

- **做什么**：按入职天数（7/30/60/90 天）查询入职跟进 review 状态，生成报告供通知 HR/主管。
- **什么时候用**：Cron 定时任务到点触发时；或需要手动查某员工某天的跟进状态时。
- **数据来源**：花名册与五部门节点 → HCM API（只读）；跟进 completed → 本机 `review-state/reviews.json`。
- **调用要点**：`onboarding-review.sh <姓名> <入职天数> [pinyin]` 只查询催办；五节点未齐时 `action=not_armed`，**不会**偷偷 ensure。HR 确认后 `review-store.sh mark-done ...`。开通跟进用 `sync-reviews-if-ready.sh`（勿直接 `schedule-onboarding-reviews.sh`，以免未全绿就挂 Cron）。

### generating-onboarding-dashboard —— 入职进度看板

- **做什么**：从 HCM 读取准备节点 + 从本地表读取 review 状态，生成可视化 HTML 看板并发布到 Canvas。
- **什么时候用**：需要总览所有新员工入职进度时。
- **数据来源**：HCM API（五节点，只读）+ 本机 `review-state/reviews.json` + 本机 `workflow.json`（审批门角标）。
- **调用要点**：
  - 仅生成：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh`
  - 生成并发布：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force`
  - canvas-id 固定 `onboarding-dashboard`；浏览器看 `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html`

## 本地环境特定信息

- 审批门状态和 resumeToken 仍在 `stub-state/<pinyin>/workflow.json`（Lobster 工作流落盘）。
- `pending-approvals/` 目录存审批门暂停快照。
- 两个 `hcm_api.py` 副本（workflow 和 review 各一份）为只读客户端，不含写入方法。
