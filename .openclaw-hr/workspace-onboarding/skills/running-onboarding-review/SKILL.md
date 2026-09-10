---
name: running-onboarding-review
description: Run a probation-period follow-up review for a new hire at day 7/30/60/90. Use when a scheduled review fires, or when asked to follow up. Prep nodes come from HCM (read-only). Reviews live in the local table and are armed only after all 5 HCM nodes are completed. Query does not auto-complete; HR backfill uses review-store.sh record (CLI only). Feishu is notify-only.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# running-onboarding-review

按入职天数节点，查询新员工入职跟进 review 状态，生成报告供通知 HR/主管。

## 何时用这个 Skill

新员工入职不是报到当天就结束——试用期内有 7 / 30 / 60 / 90 天四个跟进节点。这个 Skill 在两种情况用：

- **Cron 定时任务到点触发** —— 入职后第 7/30/60/90 天，Cron 自动触发一次跟进 review。
- **手动跟进** —— 有人要求查某新员工的入职进展时，手动跑一次。

## 数据来源

- **花名册与五部门准备节点**：HCM `GET /api/candidates`（只读）
- **review 状态**：本机 `review-state/reviews.json`（入职小慧经 `review-store.sh` 维护）
- **不向 HCM 写入**；到点只催办，**不自动标 completed**
- **飞书只通知**；回填只走 CLI，不走飞书 spawn / 行政 exec

HCM 不可达时脚本退出 **5**，花名册无此人退出 **4**。

## 工作流程

### 查询（Cron / 手动）

```bash
bash skills/running-onboarding-review/scripts/onboarding-review.sh <姓名> <入职天数> [pinyin]
```

`<入职天数>` 取 7 / 30 / 60 / 90。例：`onboarding-review.sh 员工1 7 yuangong1`。

JSON 中 `action` 字段：
- `"not_armed"` —— 试用期跟进尚未开通（HCM 五节点未全部 `completed`）。只催部门，**不要** `ensure` / 挂 Cron。
- `"already_reviewed"` —— 本地表该天已是 `completed` / `skipped`
- `"needs_review"` —— 已开通且待 HR 回填（`due` / `overdue` / 未到点的 `pending`）

### HR 回填（只走 CLI）

不要在飞书里改表。在主节点：

```bash
bash skills/running-onboarding-review/scripts/review-store.sh record <姓名> <pinyin> <7|30|60|90> \
  --outcome ok|watch|risk|skipped \
  --summary "纪要..." \
  --next-action "下一步" \
  --next-action-due YYYY-MM-DD \
  --reviewer "HR"

# 兼容旧入口（等价 outcome=ok）
bash skills/running-onboarding-review/scripts/review-store.sh mark-done <姓名> <pinyin> <7|30|60|90> [--content "纪要..."]
```

### 本地表维护

```bash
bash skills/running-onboarding-review/scripts/review-store.sh list [--pending] [--pinyin <pinyin>]
bash skills/running-onboarding-review/scripts/review-store.sh get <pinyin> <day>
bash skills/running-onboarding-review/scripts/review-store.sh ensure <姓名> <pinyin>
```

工作流**归档**（lobster complete）或 HR 显式执行时，`sync-reviews-if-ready.sh` 仅在五节点全绿时 `ensure` + 挂 Cron（已挂过则跳过）。查询进度与看板刷新**不**挂 Cron。**不要**在节点未齐时直接跑 `schedule-onboarding-reviews.sh`。

## 跟进重点（按入职天数）

- 第 7 天：完成公司级 Onboarding / 导师启动带教 / 融入团队
- 第 30 天：部门岗位培训 / HR 第一次新人关怀沟通
- 第 60 天：带教进展检查 / 岗位胜任度初评
- 第 90 天：导师带教结束 / 6 个月试用期者中期反馈

## 关键规则

- review 天数只允许 7/30/60/90。
- **查询脚本不标完成、不偷偷 ensure。** 只有五节点全绿才开通；只有 CLI `record` 成功后才变 `completed` / `skipped`。Cron 只把 `pending` 打成 `due` 并写 `triggered_at`。
- 准备节点未就绪时如实报告，不编造。
- 入职跟进的天数节点说明见 → `references/review-milestones.md`。
