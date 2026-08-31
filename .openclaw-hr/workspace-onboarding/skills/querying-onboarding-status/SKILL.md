---
name: querying-onboarding-status
description: 查询入职进度。花名册与五部门准备节点以 HCM GET /api/candidates 为准；审批门与 resumeToken 仍读本机 workflow.json（HCM 无此字段）。HCM 不可用时明确失败，不用 stub 冒充花名册。
---

# querying-onboarding-status · 入职状态查询 Skill

## 用途

HR 问「某人入职到哪一步了」或「这批新人都到哪了」时跑本脚本。不要只 `cat` 本地 JSON，不要手编花名册。

## 用法

```bash
scripts/query-onboarding-status.sh 员工1
scripts/query-onboarding-status.sh 员工1 yuangong1
# 整批（只准念 JSON 里的 name）：
scripts/query-onboarding-status.sh --all
```

环境变量：`HCM_API_URL` 或 `HCM_API_BASE`（默认 `http://localhost:8000`）。

## 两份数据，不要混

| 问什么 | 读哪里 |
|--------|--------|
| 这个人在不在花名册、五部门节点（合同/账号/设备/培训/Buddy） | **HCM** `GET /api/candidates` |
| 审批卡在哪一扇门、resumeToken、扭转事件 | 本机 `stub-state/<pinyin>/workflow.json`（Lobster） |
| 试用期跟进是否开通 | 本机 `review-state/reviews.json` 的 `armed`（本脚本只读，不挂 Cron） |

HCM 挂了 → 退出 **5**，说 API 不可用，**禁止**用 stub 报「全部完成」。  
花名册没有此人 → 退出 **4**。  
人在 HCM、尚未 `start` 工作流 → 退出 **0**，只报 HCM 节点，并写明审批流未启动。  
`workflow.json` 为 `waiting_departments` → 催部门在 HCM 填写后再次 `start`，不要 resume。

## 交回用户时的硬规则

stderr 里若有 `---PROMPT---` 块（卡在审批门时）：

1. **PROMPT 正文一字不改**。
2. **RESUME_TOKEN 一字不改**，放进代码块。
3. 隐藏机器标记行。
4. 五节点进度必须来自脚本里的 **HCM** 段，不要改口成 stub。

## 工程契约

1. 查人：`hcm_api.find_candidates`（与 review 脚本同一客户端）。
2. 审批 PROMPT 仍由 `build-approval-prompt.py` 生成（有 halt 时）。
3. 不向 HCM 做 POST/PUT。
