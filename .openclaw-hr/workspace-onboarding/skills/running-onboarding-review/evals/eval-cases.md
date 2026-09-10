# running-onboarding-review 评测场景

> 评测对象：按入职天数（7/30/60/90）查一次入职跟进。五部门节点读 HCM；跟进读本机 `review-state/reviews.json`。查询不 ensure、不标完成。夹具用员工1 / yuangong1。

## 评测场景

### 场景 1 · 第 7 天跟进（已开通）

- 输入：HCM 五节点均为 completed、本地表已 armed 的员工（如 员工1）+ 天数 7
- query：为这名新员工跑第 7 天的入职跟进 review
- expected_behavior：
  - 跟进重点：完成公司级 Onboarding / 导师启动带教 / 融入团队
  - 5 节点状态来自 HCM，不是脚本写死
  - `action` 为 `needs_review` 或 `already_reviewed`，只催办 / 报告，不 `record`
  - 不写 `review-<姓名>-day7.json`（真源是 `reviews.json`）

### 场景 2 · 不同天数的跟进重点正确

- 输入：同一员工，入职天数 30 / 60 / 90
- expected_behavior：
  - 第 30 天重点 = 部门岗位培训 / HR 第一次新人关怀沟通
  - 第 60 天重点 = 带教进展检查 / 岗位胜任度初评
  - 第 90 天重点 = 导师带教结束 / 6 个月试用期者中期反馈

### 场景 3 · 五节点未齐时不偷偷开通

- 输入：HCM 仍有 pending 节点的员工
- expected_behavior：
  - `action=not_armed`
  - **不**调用 `ensure` / `schedule-onboarding-reviews.sh`
  - 看板 / 查询路径也不挂 Cron

### 场景 4（边界）· 花名册 / HCM 查无此人

- 输入：花名册里不存在的姓名
- expected_behavior：
  - 花名册无此人 **4**；HCM 不可用 **5**
  - 不把「未就绪」包装成一次成功的跟进

## 基线测试（没有 Skill 时）

见本实验记录 CP2 · 步骤 2。
