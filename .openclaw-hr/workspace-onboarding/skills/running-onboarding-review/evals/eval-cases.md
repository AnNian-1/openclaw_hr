# running-onboarding-review 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：按入职天数（7/30/60/90）跑一次入职跟进 review——读入职工作流落盘的 5 节点真实状态，产出结构化 review 报告。

## 评测场景

### 场景 1 · 第 7 天跟进 review

- 输入：一名已启动入职流程的新员工姓名（如 员工1）+ 入职天数 7
- query：为这名新员工跑第 7 天的入职跟进 review
- expected_behavior：
  - 跟进重点对应 09-入职流程.md 第一周事项（完成公司级 Onboarding / 导师启动带教 / 融入团队）
  - review 读到入职工作流落盘的 5 节点真实状态（合同/账号/设备/Buddy/培训），不是脚本写死的
  - 结构化状态落盘到 `review-state/review-<姓名>-day7.json`

### 场景 2 · 不同天数的跟进重点正确

- 输入：同一员工，入职天数 30 / 60 / 90
- query：跑第 30/60/90 天的入职跟进 review
- expected_behavior：
  - 第 30 天重点 = 部门岗位培训 / HR 第一次新人关怀沟通
  - 第 60 天重点 = 带教进展检查 / 岗位胜任度初评
  - 第 90 天重点 = 导师带教结束 / 6 个月试用期者中期反馈
  - 各自落盘到对应 day 的 JSON 文件

### 场景 3 · review 报告落盘可被看板读取

- 输入：跑完一次 review 后
- query：检查落盘文件
- expected_behavior：
  - `review-state/review-<姓名>-day<N>.json` 含 candidate / day / focus / reviewedAt / status 字段
  - 文件结构与 generating-onboarding-dashboard 看板读取的格式一致

### 场景 4（边界）· 花名册 / HCM 查无此人

- 输入：一个 HCM 花名册里不存在的姓名（如「不存在的人」）
- query：跑入职跟进 review
- expected_behavior：
  - 脚本退出码非 0（花名册无此人 **4**；HCM 不可用 **5**）
  - **不**写 `review-state/review-<姓名>-dayN.json`
  - 不把「未就绪」包装成一次成功的跟进

## 基线测试（没有 Skill 时）

见本实验记录 CP2 · 步骤 2。
