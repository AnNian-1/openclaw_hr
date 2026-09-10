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
- 试用期 7/30/60/90 跟进 → 本机 `review-state/reviews.json`（HR 在 CLI `review-store.sh record`；飞书只催办）
- 小慧的职责：查询 HCM 准备状态 + 本地跟进表 → 推进审批流程 → 通知相关人员
- 审批门（contract_gate / account_gate）是 Lobster 工作流概念，HCM 无此字段，仍读本机 `workflow.json`

## 入职业务 Skill 清单

### running-onboarding-workflow —— 入职审批工作流

- **做什么**：用 Lobster 跑一名新员工的入职**审批**流程——从 HCM 只读快照五部门节点 + 2 个 HiTL 审批门。不代替其它部门在 HCM 填节点。
- **什么时候用**：一名新员工确定录用、要走入职审批时。
- **数据来源**：HCM GET 花名册与节点；本地 `workflow.json` 管审批门。
- **调用要点**：
  - 启动：`bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>`。合同节点未开始则退出 6，催部门后重试。
  - 推进：`bash skills/running-onboarding-workflow/scripts/run-onboarding.sh resume <resumeToken> yes|no`。
  - halt 时的 `resumeToken` 必须原样留存。材料 pending 时不要建议批准。
  - 两道门批完 ≠ 试用期跟进已挂；须五节点 `completed`。

### querying-onboarding-status —— 入职状态查询

- **做什么**：查询某新员工（或整批）的入职状态。花名册 + 五部门节点来自 HCM，审批门 / resumeToken 来自本地 `workflow.json`，halt 快照来自 `pending-approvals/`。
- **什么时候用**：HR 问「某人入职到哪一步了」「这批新人都到哪了」时。
- **数据来源**：花名册与五部门节点 → HCM API；审批门 / resumeToken → 本机 `workflow.json`；halt 对比 → `pending-approvals/`。
- **调用要点**：
  - 单人：`bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh <姓名> [pinyin]`（例：`员工1` / `yuangong1`）
  - 整批：`bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh --all`（只准念 JSON 里的 name）
  - **本 Skill 只查询，不批准 / 拒绝。** 拿到 token 后仍须人走 `bash skills/running-onboarding-workflow/scripts/run-onboarding.sh resume <token> yes|no`。
  - halt ≥ 3 天只催办，不自动 resume。只读，**不**注册 Cron。HCM 不可达 exit 5。

### running-onboarding-review —— 入职跟进 review

- **做什么**：按入职天数（7/30/60/90 天）查询入职跟进 review 状态，生成报告供通知 HR/主管。
- **什么时候用**：Cron 定时任务到点触发时；或需要手动查某员工某天的跟进状态时。
- **数据来源**：花名册与五部门节点 → HCM API（只读）；跟进 completed → 本机 `review-state/reviews.json`。
- **调用要点**：`bash skills/running-onboarding-review/scripts/onboarding-review.sh <姓名> <入职天数> [pinyin]` 只查询催办；五节点未齐时 `action=not_armed`，**不会**偷偷 ensure。HR 回填：`bash skills/running-onboarding-review/scripts/review-store.sh record ... --outcome ok|watch|risk|skipped`。开通跟进用 `bash skills/running-onboarding-review/scripts/sync-reviews-if-ready.sh`（勿直接 `schedule-onboarding-reviews.sh`，以免未全绿就挂 Cron）。根目录 `review-system/` 是旧入口，不要用。

### generating-onboarding-dashboard —— 入职进度看板

- **做什么**：从 HCM 读取 5 个准备节点 + 本机 `workflow.json` 审批门角标 + 本地试用期跟进表，生成可视化 HTML 看板并发布到 Canvas。
- **什么时候用**：需要总览所有新员工入职进度时。
- **数据来源**：HCM API（五节点，只读）+ 本机 `workflow.json`（审批门角标）+ `review-state/reviews.json`（7/30/60/90）。
- **调用要点**：
  - 仅生成：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh`
  - 生成并发布：`bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force`
  - canvas-id 固定 `onboarding-dashboard`；浏览器看 `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html`

## 本地环境特定信息

- 审批门状态和 resumeToken 在 `stub-state/<pinyin>/workflow.json`（Lobster 落盘；halt 时 attach 回填）。
- `pending-approvals/<pinyin>-<gate>.json` 存 halt 快照 + 回填后的 `resume_token`（查询优先读这里，不扫 lobster 内部目录）。
- 两个 `hcm_api.py` 副本（workflow 和 review 各一份）为只读客户端，不含写入方法。
- 真源工作流文件：`skills/running-onboarding-workflow/scripts/hr-onboarding.lobster`。根目录 `workflows/hr-onboarding.lobster` 是课程早期裸跑副本，不要用。
