---
name: running-onboarding-review
description: Run a probation-period follow-up review for a new hire at a given onboarding day milestone (7, 30, 60, or 90 days). Use this skill when a scheduled onboarding review is triggered, or when someone asks to follow up on a new hire's onboarding progress. It queries the HCM system API for the latest preparation-node status and review status, then outputs a structured report for the agent to notify HR/management. Does not write to HCM or local files.
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
- **review 状态**：HCM 返回的 `candidate.reviews` 字段（只读）
- **不向 HCM 写入**，不写本地 `review-state/`——review 记录由 HR/主管在 HCM 维护。

HCM 不可达时脚本会报错退出，不会用本地数据冒充。

## 工作流程

```bash
bash skills/running-onboarding-review/scripts/onboarding-review.sh <姓名> <入职天数> [pinyin]
```

`<入职天数>` 取 7 / 30 / 60 / 90。例：`onboarding-review.sh 郭超 7`。

脚本输出：
- **stdout**：结构化 JSON（供小慧解析后通知 HR）
- **stderr**：人话摘要（供直接展示）

JSON 中 `action` 字段指示下一步：
- `"already_reviewed"` —— 该天数 review 已由 HR/主管完成，无需操作
- `"needs_review"` —— review 待触发，小慧应通知 HR/主管

## 跟进重点（按入职天数）

- 第 7 天：完成公司级 Onboarding / 导师启动带教 / 融入团队
- 第 30 天：部门岗位培训 / HR 第一次新人关怀沟通
- 第 60 天：带教进展检查 / 岗位胜任度初评
- 第 90 天：导师带教结束 / 6 个月试用期者中期反馈

## 关键规则

- review 的跟进重点对应固定的入职天数节点（7/30/60/90），不要传别的天数。
- **本脚本只查询、不写入。** review 记录的维护权归 HR/主管，小慧只负责查询状态并通知。
- 如果 HCM 中某准备节点显示「未就绪」，如实报告，不要编造状态。
- 入职跟进的天数节点为什么是 7/30/60/90，见 → `references/review-milestones.md`。
