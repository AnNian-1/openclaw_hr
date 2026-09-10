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

| 数据 | 真相源 | 本 Skill |
|------|--------|----------|
| 花名册 + 五部门准备节点 | HCM `GET /api/candidates` | 只读；不可用 exit 5 |
| 试用期跟进 | 本机 `review-state/reviews.json` | 查询催办；回填只走 CLI `review-store.sh record` |

某个 HCM 节点未返回时，状态显示「未就绪」，不编造「已完成」。

**不要**再写或依赖 `review-<姓名>-day<N>.json`。看板读的是同一份 `reviews.json`。本机 `stub-state/<pinyin>/*.json` 只是 HCM 快照，不是 review 的五节点真相源。

开通条件：HCM **五**节点均为 `completed`，才由 `sync-reviews-if-ready.sh` ensure + 挂 Cron。查询脚本在未开通时返回 `action=not_armed`，**不会**偷偷 ensure。

## 4. Cron 触发与本 Skill 的边界

这个 Skill 只负责「被触发后跑一次 review / 催办」。**Cron 任务的注册是另一回事**：

- 开通入口：lobster `complete` 或 HR 显式执行 `sync-reviews-if-ready.sh`（内部才调 `schedule-onboarding-reviews.sh`）。
- **查询进度和看板刷新只读，不挂 Cron。**
- 调度用 `--at` 一次性任务（入职日 +7/30/60/90），不要写成周期 `--cron`。
- 本仓 Cron 投递策略以现行 `cron/jobs.json` 为准；不要为了对齐课程去改 yaml / 飞书 bindings。

把「可变的调度」和「不变的执行」分开：Skill 不负责 `cron add`。
