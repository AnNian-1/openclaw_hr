---
name: querying-onboarding-status
description: Query onboarding progress. Roster and 5 department nodes come from HCM GET /api/candidates; approval gates and resumeToken come from local workflow.json. Never invent names or statuses. This skill only queries — the agent never approves on a human's behalf.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# querying-onboarding-status · 入职状态查询 Skill

## 用途

HR 问「某人入职到哪一步了」或「这批新人都到哪了」时跑本脚本。不要只 `cat` 本地 JSON，不要手编花名册。

## 用法

```bash
bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh 员工1
bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh 员工1 yuangong1
# 整批（只准念 JSON 里的 name）：
bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh --all
```

环境变量：`HCM_API_URL` 或 `HCM_API_BASE`（默认 `http://127.0.0.1:8000`）。

## 硬规则

> **本 Skill 只负责查询，不负责批准 / 拒绝。** 拿到 token 之后，HR 仍须用 `running-onboarding-workflow/scripts/run-onboarding.sh resume <token> yes|no` 走人工确认路径。审批决策权始终在人，不在本 Skill。halt ≥ 3 天只催办，不自动 resume。`approvalId` 不能顶替 `resumeToken`。

## 两份数据，不要混

| 问什么 | 读哪里 |
|--------|--------|
| 这个人在不在花名册、五部门节点（合同/账号/设备/培训/Buddy） | **HCM** `GET /api/candidates` |
| 审批卡在哪一扇门、resumeToken、扭转事件 | 本机 `stub-state/<pinyin>/workflow.json`（Lobster） |
| halt 快照 / stub 是否在 halt 后被改 | 本机 `pending-approvals/<pinyin>-<gate>.json`（优先；回退扫 lobster state 仅作 token 兜底） |
| 试用期跟进是否开通 | 本机 `review-state/reviews.json` 的 `armed`（本脚本只读，不挂 Cron） |

HCM 挂了 → 退出 **5**，说 API 不可用，**禁止**用 stub 报「全部完成」。  
花名册没有此人 → 退出 **4**。  
人在 HCM、尚未 `start` 工作流 → 退出 **0**，只报 HCM 节点，并写明审批流未启动。  
`workflow.json` 为 `waiting_departments` → 催部门在 HCM 填写后再次 `start`，不要 resume。  
halt ≥ 3 天 → 输出催办，不 resume。

JSON 里的 `stub_changed_after_halt` 是事实陈述（halt 后快照字段变过），不是建议批准。

## 交回用户时的硬规则

stderr 里若有 `---PROMPT---` 块（卡在审批门时）：

1. **PROMPT 正文一字不改**。
2. **RESUME_TOKEN 一字不改**，放进代码块。
3. 隐藏机器标记行。
4. 五节点进度必须来自脚本里的 **HCM** 段，不要改口成 stub。
5. 只准念脚本 JSON 里出现的姓名（常见：员工1 / yuangong1）。

## 工程契约

1. 查人：`hcm_api.find_candidates`（与 review 脚本同一客户端）。
2. 审批 PROMPT 仍由 `build-approval-prompt.py` 生成（有 halt 时）。
3. 不向 HCM 做 POST/PUT。不调用 `run-onboarding.sh resume`。
4. 输出形态见 → `references/status-shape.md`。
