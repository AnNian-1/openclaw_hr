# 入职跟进的天数节点细则

> running-onboarding-review Skill 的跟进节点设计依据。SKILL.md 在需要时引用本文件。
> 依据：hr-wiki《09-入职流程》第四节「入职后跟进」。

## 目录

- 1. 为什么是 7/30/60/90 四个节点
- 2. 四个节点各跟进什么
- 3. review 的数据从哪来
- 4. Cron 触发与本 Skill 的边界

## 1. 为什么是 7/30/60/90 四个节点

入职不是报到当天就结束。试用期内新员工的状态会经历几个明显阶段——刚到岗（第 1 周）、初步上手（第 1 个月）、进入岗位（第 2-3 个月）、试用期收尾（第 3 个月）。每个阶段 HR 和导师要关注的事不同。把这些阶段落成 4 个固定的天数节点，就能用 Cron 定时任务自动跟进，HR 不必靠脑子记日期。

人工做这件事的痛点：HR 同时带多个新人，每人 4 个跟进点，记混、记漏；不主动想起就没人跟进。固定天数节点 + Cron 定时触发，把"记得跟进"这件事从人脑挪到系统。

## 2. 四个节点各跟进什么

| 入职天数 | 对应阶段 | 跟进重点 |
|---|---|---|
| 第 7 天 | 报到第一周 | 完成公司级 Onboarding；导师启动带教；融入团队 |
| 第 30 天 | 入职第一个月 | 部门岗位培训；HR 第一次新人关怀沟通 |
| 第 60 天 | 入职第二个月 | 带教进展检查；岗位胜任度初评 |
| 第 90 天 | 入职第三个月 | 导师带教结束；6 个月试用期者中期反馈 |

这四组跟进事项写死在 `onboarding-review.sh` 的 `case` 分支里。传 7/30/60/90 以外的天数会落到"常规跟进"——所以 review 只在这四个节点跑。

## 3. review 的数据从哪来

review 报告里的「入职准备 5 节点状态」不是 review 脚本自己造的，是从入职审批工作流（`running-onboarding-workflow` Skill）落盘的 `stub-state/` 真实状态文件读出来的：

- `stub-state/contract.json` → 合同节点状态
- `stub-state/account.json` → IT 账号节点状态
- `stub-state/device.json` → 设备节点状态
- `stub-state/buddy.json` → Buddy 节点状态
- `stub-state/training.json` → 培训节点状态

某个节点的 JSON 文件不存在时，状态显示「未就绪」——说明这名员工的入职工作流还没跑到产出该节点的步骤。review 如实读出来，HR 才知道这名新人卡在哪。

review 自己的产出落盘到 workspace 根的 `review-state/review-<姓名>-day<N>.json`，结构是 `candidate / day / focus / reviewedAt / status` 五字段。这个文件是入职进度看板（`generating-onboarding-dashboard` Skill）的数据源。

## 4. Cron 触发与本 Skill 的边界

这个 Skill 只负责"被触发后跑一次 review"。**Cron 任务的注册是另一回事**——它是调度配置，用 `openclaw cron add` 做，要指定 schedule（在入职后第 7/30/60/90 天触发）、绑定 onboarding Agent、`--no-deliver`（HR 隔离 profile 没配聊天 channel，不加这个参数 Cron 任务跑完会因投递失败而报 error）。

调度配置不进 Skill 的原因：Cron schedule 是"什么时候跑"，会随每个新员工的入职日期变；Skill 是"跑的时候做什么"，对所有员工一致。把可变的调度和不变的执行分开。
