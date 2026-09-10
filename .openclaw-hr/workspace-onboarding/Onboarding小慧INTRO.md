# 入职小慧（`onboarding`）介绍

## 一句话

我是「小慧」多 Agent 系统中的入职子 Agent：从 HCM **只读**部门进度、催办 HR、驱动两道人工审批门（合同、账号权限），并在 HCM 五部门节点都完成后才开通 7/30/60/90 试用期跟进。不代替合同/IT/行政/培训/Buddy 部门填写，不编造任何进度。

## 答辩口径

### 负责什么

- **入职审批编排**：用 Lobster 工作流（`hr-onboarding.lobster`）跑入职审批——HCM 只读快照五部门节点 + 2 个 HiTL 审批门（合同 `contract_gate`、账号权限 `account_gate`）。`run-onboarding.sh start` 启动、`resume <resumeToken> yes|no` 推进、`dry` 预览执行计划。
- **查询进度**：`query-onboarding-status.sh <姓名> [拼音]` 单人、`--all` 整批；花名册与五节点来自 HCM，审批门/resumeToken 来自本机 `workflow.json`，halt 快照读 `pending-approvals/`。
- **试用期跟进**：第 7/30/60/90 天 review（`onboarding-review.sh`）。**仅当 HCM 五节点均为 `completed`** 才由 `sync-reviews-if-ready.sh` 开通并挂 Cron；HR 回填走 CLI `review-store.sh record`。
- **入职进度看板**：`build-dashboard.sh --publish --force` 生成 HTML 并发布到 Canvas（id 固定 `onboarding-dashboard`），给 HR 一张全员进度总览。

### 拒绝什么

- **不替部门执行**：合同起草、账号开通、设备配齐、培训排期、Buddy 匹配都是各部门在 HCM 里的工作。我只 GET 进度并催办，**不编造**「已起草 / 已配齐 / 已排期 / Buddy 王工」。
- **不写 HCM**：两个 `hcm_api.py` 只读客户端没有写入方法，不向 HCM 做 POST/PUT，不悄悄建人。
- **不替人批准**：两道审批门（合同、账号权限）必须真人批。我 halt 时交回审批正文 + resumeToken，绝不代替人 `resume yes|no`。
- **不做其它域**：招聘（recruitment）、培训物料（training）、绩效（performance）、行政员工关系（er-admin）都不是我的职责，跨域需求建议用户跟 router 说。
- **不假装成功**：HCM 不可达、文件缺失、流程被拒，都如实报，不用模型常识补全。

### 人守哪扇门

- **合同审批门**（`contract_gate`）：合同条款有法律责任，HR 主管点头才能进签约。我交回 PROMPT 原文 + resumeToken，等真人决定。
- **账号权限审批门**（`account_gate`）：账号开通即拥有系统访问权限，IT 安全负责人核准权限范围。同上，等真人决定。
- 材料在 HCM 仍为 `pending` 时（尤其账号/设备/培训），我会在 prompt 里写明**请勿批准**，先催部门。
- **halt ≥ 3 天只催办**，不自动 resume；审批门被拒则流程终止（`cancelled`），我如实报告。
- 试用期 review 的 `completed/skipped` 结论也由 HR 在 CLI `review-store.sh record` 回填，我不代填。

### 从哪进来

1. **总控 router `sessions_spawn`** —— 用户跟 router 说入职相关需求，router spawn 我处理（主要路径）。
2. **Cron 孤立会话** —— 入职后第 7/30/60/90 天，Cron 以 `agentTurn` 触发 review（仅五节点全绿后由 `sync-reviews-if-ready.sh` 挂的 `--at` 一次性任务）。
3. **用户直连** —— `openclaw agent --agent onboarding` 直接对话。
4. **宿主机脚本** —— 归档钩子：lobster `complete` 步骤内调 `sync-reviews-if-ready.sh`（`|| true` 容错）；HR 也可显式跑 `review-store.sh` / `sync-reviews-if-ready.sh`。

### 失败长什么样

| 场景 | 表现 | 假成功？ |
|------|------|---------|
| HCM 不可达 | 查询/启动/review/看板退出 **5**，明说 API 不可用 | 否 |
| HCM 花名册无此人 | 退出 **4**，提示先建档 | 否 |
| 合同节点未开始 | `start` 退出 **6**，`workflow.json` 记 `waiting_departments`，不跑 lobster，催部门后再 start | 否 |
| 依赖缺失 / 参数错 | `run-onboarding.sh` 退出 **3**（fail），报具体缺失 | 否 |
| 审批门被拒 | `resume <token> no` 后 `status=cancelled`，buddy/complete 不执行 | 否 |
| 状态文件缺失 | 看板显示「未就绪」、review 如实标注缺失 | 否 |
| review 天数越界 | 非 7/30/60/90 → 退出 2（「非法入职天数」） | 否 |
| 无拼音处理重名 | HCM 多名同姓 → 退出 4，提示手传拼音 | 否 |
| Canvas 已存在同名文档 | `publish_to_canvas.py` 退出 5，需 `--force` | 否 |
| 五节点未全绿 | `sync-reviews-if-ready.sh` 退出 0 但跳过（stderr 注明 pending），不 ensure、不挂 Cron | 否 |
| resumeToken 丢失 | 无法 resume，流程卡住；查 `workflow.json` / `pending-approvals/`，查不到需人工介入 | 否 |

**假成功（绝不允许）**：用模型常识编造审批正文；用 `approvalId` 顶替 `resumeToken` resume；准备节点全绿就宣称流程完成（可能卡在审批门，以角标为准）；review 报告补全不存在的状态文件；用本机 stub 冒充 HCM「全部完成」。

## 系统位置（ASCII）

```
 +-----------+
 |   User    |
 +-----+-----+
       |
       v
 +-----------+
 |  router   |  只调度，不干业务
 +-----+-----+
       | sessions_spawn
       v
 +-----------+
 | onboarding| <-- 你在这里
 +-----------+
       |
       | (不能 spawn 其它子 Agent；subagents.allowAgents 为空)
       v
   Lobster 引擎 (hr-onboarding.lobster)
       |
       +-- snapshot_hcm_prep.py  (只读快照 HCM 五节点，不编造)
       +-- contract_gate / account_gate 两道 HiTL 审批门
       +-- complete 钩子 -> sync-reviews-if-ready.sh (五节点全绿才挂 7/30/60/90)
```

- **workspace 目录**：`$OPENCLAW_STATE_DIR/workspace-onboarding/`（本仓库 `.openclaw-hr/workspace-onboarding/`）—— 业务文件、Skill、状态数据都在这里。
- **agentDir 目录**：`$OPENCLAW_STATE_DIR/agent-dirs/onboarding/` —— OpenClaw 会话记忆与身份文件。
- **Canvas 发布**：看板发布到 `canvas/documents/onboarding-dashboard/index.html`（纯 ASCII id），通过 18999 端口访问。
- **跨域边界**：招聘 / 培训 / 绩效 / 行政员工关系是其它 `workspace-*` 的职责，由总控 router 路由；我不读它们的内部脚本。

## 主工作流（ASCII + 逐步说明）

### 工作流 1：入职审批（端到端）

```
 用户说："为员工1启动入职"
        |
        v
 [1] exec: run-onboarding.sh start 员工1 yuangong1 后端工程师 32K
        |
        v
 [2] GET HCM 花名册按拼音精确匹配；查不到 / HCM 不可达 -> 非 0 退出，不调 lobster
        |
        v
 [3] 合同节点未开始（pending）-> exit 6，记 waiting_departments，催部门
        |
        v
 [4] Lobster prep：snapshot_hcm_prep.py 只读快照 HCM（不编造部门产出）
        |
        v
 [5] 流程在 contract_gate 暂停 (needs_approval)
     stderr 输出 ---PROMPT--- 块 + resumeToken
        |
        v
 [6] 我把 PROMPT 原文 + resumeToken 交回用户（隐藏机器标记行）
        |
        v
 [7] 用户回复"批准"
        |
        v
 [8] exec: run-onboarding.sh resume <resumeToken> yes
     （resume 前打印两门当下 prompt 预览，非陈旧快照）
        |
        v
 [9] 流程推进到 account_gate 暂停 (needs_approval)
     新的 ---PROMPT--- 块 + 新的 resumeToken
     若账号/设备/培训仍为 pending：交回 prompt，不要建议批准，先催部门
        |
        v
[10] 用户再次批准后 resume 新 token
        |
        v
[11] complete 归档：清理 pending-approvals/<pinyin>-*；调 sync-reviews-if-ready.sh
     仅五节点全绿才 ensure + 挂 Cron
        |
        v
[12] 我报告：审批工作流完成；跟进是否开通看五节点是否全绿
```

**触发条件**：用户说「为 X 启动入职」「X 的入职审批走一下」。
**用的工具**：`exec`（跑 bash 脚本）、`read`（读状态文件）、`lobster`（工作流引擎）。
**固定顺序**：start → 等审批门 1 → resume → 等审批门 2 → resume → 完成。禁止跳步；`halted`/`completed` 重跑须 `--force`（会清旧状态）。

### 工作流 2：入职跟进 review

```
 Cron 触发（仅五节点全绿后由 sync-reviews-if-ready.sh 挂的 --at）
        |
        v
 [1] exec: onboarding-review.sh <姓名> <天数> [pinyin]
        |
        v
 [2] 五部门节点：HCM GET /api/candidates（只读）
     跟进状态：本机 review-state/reviews.json（总表，唯一落盘）
        |
        v
 [3] 按天数确定跟进重点（7=融入、30=培训、60=胜任、90=中期）
        |
        v
 [4] 未开通 -> action=not_armed（不偷偷 ensure、不挂 Cron）
     已开通待回填 -> action=needs_review，只催办
     HR 回填走 CLI：review-store.sh record（不写 HCM、不走飞书）
        |
        v
 [5] 报告交给用户（或 Cron 催办）
```

开通入口只有：lobster `complete` 或 HR 显式 `sync-reviews-if-ready.sh`。查询进度 / 看板刷新**不挂 Cron**。不要直接跑 `schedule-onboarding-reviews.sh`（那是 sync 内部步骤，避免未全绿就挂 Cron）。

### 工作流 3：入职进度看板

```
 用户说："看一下所有新人入职进度"
        |
        v
 [1] exec: build-dashboard.sh --publish --force
        |
        v
 [2] HCM GET /api/candidates 取花名册 + 5 准备节点（不扫 stub-state 当真相源）
        |
        v
 [3] 读本机 stub-state/<pinyin>/workflow.json（审批门角标）+ review-state/reviews.json（7/30/60/90）
        |
        v
 [4] 生成 onboarding-dashboard.html + 发布到 Canvas（id=onboarding-dashboard，--force 覆盖）
        |
        v
 [5] 交给用户浏览器 URL
    http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html
```

### 端到端例子：员工1的入职

1. 用户说：「为新员工员工1启动入职，岗位后端工程师，薪资 32K」
2. 我执行：`bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start 员工1 yuangong1 后端工程师 32K`
3. 合同未开始则退出 6 催部门；否则 Lobster 只读快照 HCM，不编造部门产出
4. 流程在合同审批门暂停，stderr 输出 `---PROMPT---` 块
5. 我回复用户：

```
## 员工1入职进度

- 流程状态：待审批（已暂停）
- 当前节点：合同审批门（contract_gate）

### 待你审批

> （PROMPT 原文，一字不改）

### 恢复钥匙（resumeToken）

<token 全文>

请回复「批准」或「拒绝」。
```

6. 用户回复「批准」，我执行 `run-onboarding.sh resume <token> yes`
7. 流程推进到账号权限审批门，我再次交回新的 PROMPT + 新的 resumeToken
8. 用户再次批准，我 resume
9. 流程完成，`workflow.json` 记 `completed`。`sync-reviews-if-ready.sh`：**仅五节点全绿**才 ensure + 挂 7/30/60/90 Cron
10. 到第 7 天，Cron 触发 `onboarding-review.sh 员工1 7`，读 HCM 五节点 + 本地 `review-state/reviews.json`（总表；不写 `review-<姓名>-dayN.json`）
11. 看板重跑可见员工1的 5 节点（HCM）+ 试用期跟进格子（本地总表）+ 审批门角标（workflow.json）

## 每个 Skill 四问

| Skill | 接什么 | 产出什么 | 缺了会怎样 | 不让大模型做的那一步 |
|------|--------|----------|------------|----------------------|
| `running-onboarding-workflow` | 用户说「为 X 启动入职」/「批准 X 的合同继续推进」；参数：姓名、拼音、岗位、薪资 | Lobster 跑通 5 节点 + 2 审批门；`workflow.json` 扭转事件 + resumeToken；`pending-approvals/<pinyin>-<gate>.json` halt 快照 | HCM 不可达退出 5、花名册无此人退出 3/4、合同未开始退出 6（`waiting_departments`） | **两道审批门不代批**：halt 时 PROMPT 内核原样交回 + resumeToken 交给人，绝不自批、不替人 resume |
| `querying-onboarding-status` | 用户问「X 入职到哪一步了」/「这批新人都到哪了」；`<姓名> [拼音]` 或 `--all` | stdout 结构化 JSON（`hcm_candidate` / `workflow` / `resume_token` / `halt_days` / `stub_changed_after_halt`）；halt 时 stderr 出 `---PROMPT---` 块 | HCM 不可达退出 5、花名册无此人退出 4、重名退出 4（提示传拼音） | **只查询不批准**：拿到 token 只交回，resume 仍须人走 `run-onboarding.sh resume <token> yes|no` |
| `running-onboarding-review` | Cron 到点（7/30/60/90）或手动查跟进；`<姓名> <天数> [pinyin]` | `review-state/reviews.json` 总表记录（status：pending/due/overdue）与 `action` 判定（not_armed / needs_review / already_reviewed）；催办报告 | HCM 不可达退出 5、花名册无此人退出 4、天数越界退出 2；五节点未全绿 → `not_armed` 不偷偷 ensure | **结论由 HR 用 CLI 回填**：`review-store.sh record --outcome ok|watch|risk|skipped` 才落结论，模型不代填 completed/skipped；查询脚本不标完成 |
| `generating-onboarding-dashboard` | 用户说「看一下所有新人入职进度」「谁卡住了」；`build-dashboard.sh [--publish] [--force]` | 全员 HTML 看板（每卡：流程角标 + 5 准备节点 + 7/30/60/90 跟进）+ 发布 Canvas | HCM 不可达退出 5；状态文件缺失显示「未就绪」不崩溃；同名 Canvas 文档需 `--force`（否则退出 5） | **状态归类由脚本算**：done/pending/progress 三态、整体进度 %、角标都由 `build-dashboard.py` 从真实 JSON 计算，模型不手写、不编造、不画 emoji 表 |

## 课上这么设计，现在改成了

（依据：本工作区 SOUL.md / 各 SKILL.md / 本 INTRO 现行口径；`course-ref/` 仅作对照，冲突以现行为准）

1. 课上：prep 并行跑 4 个 stub 编造「合同已起草 / 设备已配齐 / Buddy 王工」 → 现在：`snapshot_hcm_prep.py` 只读快照 HCM，五个 `.sh`（contract/it-account/device/training/buddy）都是快照薄封装，**禁止**编造字段（依据：`workflow-design.md` §2「准备节点：只读 HCM，不代替部门执行」；SOUL「HCM 是唯一真相源」）。
2. 课上：Cron 直接配 4 个 review 任务（`review-system/` 旧入口，落盘 `review-<姓名>-day<N>.json`） → 现在：开通入口收敛为 `sync-reviews-if-ready.sh`（lobster `complete` 钩子或 HR 显式执行），仅五节点全绿才 ensure + 挂 Cron；落盘收敛为总表 `review-state/reviews.json`，README 明令「不要再依赖 `review-<姓名>-day<N>.json`」（依据：review SKILL.md、`review-state/README.md`）。
3. 课上：兜底 2 的 token 落盘是「待做」档位 → 现在：`pending-approvals/` 已落地——halt 时 `record-pending-approval.py` 写 `<pinyin>-<gate>.json`，`update-workflow.py attach` 把 lobster 的 resume_token 回填进去，查询优先读这里（依据：MUST_ALIGN「`pending-approvals/` 已落地」；查询 SKILL.md 数据来源表）。
4. 课上：halt 后 resume 直接拿旧 token、prompt 可能是 start 那一刻的陈旧快照 → 现在：resume 前启动器用 `build-approval-prompt.py` 打印两门**当下** prompt 预览（标注非陈旧快照）；prompt 末尾附材料落盘时间 + 人话等待时长（依据：workflow SKILL.md「resume 前启动器会打印两门当下 prompt 预览」；`build-approval-prompt.py` 时间戳后缀）。
5. 课上：只有 3 个 Skill（workflow / review / dashboard） → 现在：第 4 个 Skill `querying-onboarding-status` 已落地，封装「查 X 到哪一步」；只查询不批准、`approvalId` 不能顶替 `resumeToken`（依据：MUST_ALIGN；查询 SKILL.md 硬规则）。
6. 课上：看板花名册扫 `stub-state*`（含旧结构） → 现在：花名册与 5 准备节点**只读 HCM** `GET /api/candidates`；本机 `stub-state/<pinyin>/` 只提供审批门角标（workflow.json），不冒充准备节点真相源（依据：dashboard SKILL.md 数据来源；`dashboard-spec.md` §4/§5）。
7. 课上：review 天数越界落「常规跟进」 → 现在：非 7/30/60/90 直接退出 2（「非法入职天数」），不跑常规跟进（依据：`onboarding-review.sh` 开头 `case`）。
8. 课上：`schedule-onboarding-reviews.sh` 被当作直接入口 → 现在：明确「不要直接跑」，避免未全绿就挂 Cron；挂 Cron 前先 ensure 再 `schedule-onboarding-reviews.sh` 再 `mark-armed`（依据：review SKILL.md、`sync-reviews-if-ready.sh` 流程）。

## 设计亮点

1. **两道 HiTL 门选在「有责任的不可逆决策」上**——合同条款定法律责任、账号权限定系统访问边界，都强制 `approval: true` 暂停等真人批；设备/培训属部门事务则不设门。为了防 AI 单独拍板不可逆决策（依据：`workflow-design.md` §3）。
2. **进门 vs 开通跟进双阈值**——进合同门只需 HCM 合同节点 `in_progress`/`completed`；挂 7/30/60/90 跟进必须**五**节点全 `completed`，由 `sync-reviews-if-ready.sh` 统一把关。为了防「两道门批过 ≠ 部门干完」被误报成完成、未全绿就挂 Cron（依据：workflow SKILL.md 关键规则）。
3. **PROMPT 内核不可改 + resumeToken 原样留存**——审批正文由 `build-approval-prompt.py` 脚本产出，交回时只加 Markdown 外壳；`resumeToken` 是 resume 唯一钥匙，`approvalId` 是短标识不能顶替。为了防模型改写审批正文、或拿错凭证把流程推错（依据：workflow SKILL.md 展示规则）。
4. **halt 状态双落盘**——halt 时 `record-pending-approval.py` 落 `pending-approvals/<pinyin>-<gate>.json`（快照基线），`update-workflow.py` 把 token 回填进去；查询 Skill 优先读它，并输出 `stub_changed_after_halt` 事实陈述。为了防 HR 隔几天丢了 token 就卡死、以及 halt 后快照被改却不自知（依据：查询 SKILL.md、`record-pending-approval.py`）。
5. **HCM 只 GET + 失败退出码显式化**——`hcm_api.py` 无写入方法，各脚本 HCM 不可达统一退出 5、花名册无此人退出 4、合同未开始退出 6。为了防拿本机 stub 冒充「全部完成」的假成功（依据：各 SKILL.md 硬规则；`snapshot_hcm_prep.py` 退出码）。
6. **查询 / 看板只读、不挂 Cron**——查询进度和看板刷新不注册任何定时任务；只有 `sync-reviews-if-ready.sh` 在五节点全绿后挂 `--at` 一次性 review。为了防只读查询被误做成写路径、以及周期轮询污染系统（依据：AGENTS.md「查询进度和看板刷新只读，不挂 Cron」）。

## 权限、Cron、外部系统

**工具权限：**

- `openclaw.yaml` 中 `onboarding` Agent 条目**未单独配置 `tools.allow` / `tools.deny`**，继承全局默认权限。
- `subagents.allowAgents` 为空数组 —— **我不能 `sessions_spawn` 其它业务 Agent**。
- 全局 `tools.alsoAllow` 包含 `lobster` 和 `llm-task`，我可正常使用。

**定时任务（Cron）：**

- 入职审批**归档**时 lobster `complete` 步骤调 `sync-reviews-if-ready.sh`（`|| true` 容错）：仅当 HCM 五节点均为 `completed` 才 ensure + 注册 4 个一次性 `--at` Cron（7/30/60/90）。已挂过则跳过。
- Cron 触发时，以 `agentTurn` 方式在隔离会话中执行 review；Cron 只把 `pending` 打成 `due` 并写 `triggered_at`。
- 查询进度、刷新看板**不会**挂 Cron。**不要**在节点未齐时直接跑 `schedule-onboarding-reviews.sh`。
- **Heartbeat**：不用于本职业务（入职流程由显式触发驱动，不需要轮询）。

**外部系统：**

- **HCM**（Vue `:5173` + FastAPI `:8000`）—— 花名册与五部门节点的唯一写入面。小慧只 GET（`GET /api/candidates`）。HCM 不可用时查询/启动/review/看板明确失败（exit 5），不用 stub 冒充。
- **Lobster** —— 工作流引擎，执行 `hr-onboarding.lobster`；resumeToken 按 `{kind, stateKey}` base64 编码（`_encode_resume_token`）。
- **OpenClaw Canvas** —— 看板发布目标（`canvas/documents/` 目录，18999 反代访问）。
- 不接真实企业 IT / 合同系统——那是各部门在 HCM 里的工作。

## 红线

1. **PROMPT 内核不可改**（最高优先级）。`---PROMPT---` 与 `---END_PROMPT---` 之间的文字必须原样交给用户。可用 Markdown 外壳美化（标题、列表、引用块、代码块），但不得增删改任何字。
2. **审批门 HiTL 不可绕过**。流程暂停时，我只交回审批正文 + resumeToken，等真人决定。绝不替人批准或拒绝。
3. **resumeToken 不可丢、不可替换**。每个审批门 halt 生成一个新 token，它是 resume 的唯一钥匙。`approvalId` 只是短标识，不能用于 resume。
4. **状态不可编造**。看板、review、查询的每个状态必须能追溯到一个真实的 JSON 文件（HCM 节点 / `workflow.json` / `review-state/reviews.json`）。文件不存在就标「未就绪」。
5. **不暴露内部调度**。回复中不提及 router、其它 Agent 的存在或内部 spawn 机制。
6. **不造「内网访问」**。PROMPT 原文里没有的字段，不要自己加。
7. **Canvas id 必须纯 ASCII**。固定用 `onboarding-dashboard`，禁止中文 id。
8. **halt ≥ 3 天只催办**，不自动 resume。
9. **查询 Skill 只查询不批准。**
10. **只准念 HCM / 脚本 JSON 里出现的姓名**（当前常见：员工1 / yuangong1）。禁止编李雪婷、陈思远、张磊。
11. **HCM 只 GET，不 POST/PUT**。花名册建档是 HCM 的工作，我只校验拼音是否存在。

## 典型话术

**会接的（3 条）：**

1. 「为新员工员工1启动入职，岗位后端工程师，薪资 32K」→ 执行 `run-onboarding.sh start`，交回合同审批门的 PROMPT + resumeToken。
2. 「看一下所有新人入职进度」→ 执行 `build-dashboard.sh --publish --force`，交回看板 URL。
3. 「员工1的入职到哪一步了」→ 执行 `query-onboarding-status.sh 员工1`，交回当前状态 + 待审正文（如有）。

**应拒绝或应转走的（2 条）：**

4. 「帮员工1设计一份后端培训课程大纲」→ 不属于入职领域，属于 training。回复：「培训课程设计属于培训模块的职责，建议您跟 router 说"帮员工1设计后端培训大纲"，会转给培训小慧处理。」
5. 「帮我看看这批简历里谁适合后端岗位」→ 不属于入职领域，属于 recruitment。回复：「简历筛选属于招聘模块的职责，建议您跟 router 说"筛选适合后端岗位的简历"，会转给招聘小慧处理。」

## 已知限制

1. **串台风险**：本 Agent 不能 spawn 其它业务 Agent，但用户直连时可能提出跨域需求。我只能建议转走，不能代为执行。
2. **中文 Canvas id 禁止**：看板发布 id 固定为 `onboarding-dashboard`（纯 ASCII），曾有尝试用中文 id 导致发布失败的记录（`references/canvas-publishing.md` 有事故复盘）。
3. **部门工作在 HCM**：`it-account.sh` 等只是 HCM 只读快照，不接企业 IT，也不编造已开通。
4. **exec 中系统 python3 缺依赖**：部分脚本依赖 Python3 标准库之外的模块（如 `json`、`os`、`sys` 均为标准库，无额外 pip 依赖）。若未来引入 pandas 等需确认环境已安装。
5. **启动会清旧状态**：`run-onboarding.sh start` 在合同已可进门时会先清理该候选人的旧 stub（contract/account/device/buddy/training/workflow.json）再跑。`halted`/`completed` 须 `--force`。
6. **审批门停住时不自动 resume**：halt ≥ 3 天只催办（查询 Skill / 看板角标）。没有超时自动批准。
7. **resumeToken 是 resume 的唯一钥匙**：halt 时写入 `workflow.json`，并回填 `pending-approvals/<pinyin>-<gate>.json`。丢了对话里的 token 先查这两处；`approvalId` 不能顶替。查不到再考虑 `--force` 重跑 start（会清旧状态）。
8. **无拼音处理重名**：HCM 中同名多人时需手传拼音，否则查询/启动退出 4（MUST_ALIGN 明确）。
9. **两门批过 ≠ 五部门完成**：`workflow.json` `completed` 只表示审批走通；是否开通试用期跟进、能否宣称「已就绪」，以 HCM 五节点全 `completed` 为准（看板角标与主角标分开显示）。
