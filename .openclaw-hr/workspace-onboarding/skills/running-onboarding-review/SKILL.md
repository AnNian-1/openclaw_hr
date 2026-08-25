---
name: running-onboarding-review
description: Run a probation-period follow-up review for a new hire at a given onboarding day milestone (7, 30, 60, or 90 days). Use this skill when a scheduled onboarding review is triggered, or when someone asks to follow up on a new hire's onboarding progress. It loads the real onboarding-workflow state for the 5 preparation nodes, applies the day-specific follow-up focus from the company onboarding playbook, and writes a structured review record that the onboarding dashboard reads.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# running-onboarding-review

按入职天数节点，跑一名新员工的入职跟进 review。

## 何时用这个 Skill

新员工入职不是报到当天就结束——试用期内有 7 / 30 / 60 / 90 天四个跟进节点。这个 Skill 在两种情况用：

- **Cron 定时任务到点触发** —— 入职后第 7/30/60/90 天，Cron 自动触发一次跟进 review。
- **手动跟进** —— 有人要求查某新员工的入职进展时，手动跑一次。

> Cron 任务的注册（schedule、触发时间、绑定哪个 Agent）是调度配置。
> 入职工作流 `complete` 节点会自动调用 `scripts/schedule-onboarding-reviews.sh` 挂 7/30/60/90 的一次性 `--at` 任务；
> 也可事后手动：`bash skills/running-onboarding-review/scripts/schedule-onboarding-reviews.sh <姓名> <pinyin> [入职日]`。
> 本 Skill 本体只负责"被触发后跑一次 review"。

## 工作流程

跑一次入职跟进 review 只有一步：

```bash
bash skills/running-onboarding-review/scripts/onboarding-review.sh <姓名> <入职天数> [pinyin]
```

`<入职天数>` 取 7 / 30 / 60 / 90。例：`onboarding-review.sh 小黑狗 7`（拼音可省，会扫 `stub-state/*/workflow.json`）。

脚本读的是 **`stub-state/<pinyin>/`** 下合同/账号/设备/Buddy/培训 JSON（与入职工作流候选人隔离目录一致），不是旧的扁平 `stub-state/*.json`。

1. **按入职天数确定跟进重点** —— 不同天数有不同的跟进事项（依据公司《入职流程》第四节）：
   - 第 7 天：完成公司级 Onboarding / 导师启动带教 / 融入团队
   - 第 30 天：部门岗位培训 / HR 第一次新人关怀沟通
   - 第 60 天：带教进展检查 / 岗位胜任度初评
   - 第 90 天：导师带教结束 / 6 个月试用期者中期反馈
2. **读入职工作流的真实状态** —— 从 `stub-state/<pinyin>/` 读 5 个准备节点（合同/账号/设备/Buddy/培训）的真实状态。review 看的是真实进度，不是脚本写死的。
3. **产出 review 报告并结构化落盘** —— 打印人类可读报告，并把结构化记录写到 `review-state/review-<姓名>-day<N>.json`，供入职进度看板读取。

## 关键规则

- review 的跟进重点对应固定的入职天数节点（7/30/60/90），不要传别的天数——别的天数会落到"常规跟进"。
- review 读的 5 节点状态来自入职审批工作流的真实落盘文件。如果某节点显示「未就绪」，说明这名员工的入职工作流还没产出该节点状态——如实报告，不要替它编一个状态。
- 结构化落盘文件 `review-<姓名>-day<N>.json` 是入职看板的数据源，文件名格式不能改。
- 入职跟进的天数节点为什么是 7/30/60/90、各节点为什么跟进这些事，见 → `references/review-milestones.md`。
