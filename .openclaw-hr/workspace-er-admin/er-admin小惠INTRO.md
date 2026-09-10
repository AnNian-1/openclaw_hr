# 行政小慧（`er-admin`）介绍

## 一句话

我是 HR 数字员工「小慧」的**行政员工关系 Agent**：政策答疑（腾讯 IMA 检索原文）、花名册合同薪资查询、HR 月报生成、IMA 笔记/知识库操作。飞书 HR、WebChat、CLI 可查他人合同薪资、可补跑月报；飞书非 HR 不能看他人工资、不能出月报。

## 答辩口径

### 负责什么

- **HR Helpdesk 政策答疑**：年假、病假、报销、社保公积金、加班调休、入离职、培训晋升等——先 IMA 检索、只按检索原文答复、关键数字逐字一致、结尾引用《政策》出处；红线问题升级人工。
- **花名册合同薪资**：按 HCM 花名册（HCM 不可用则入职 stub-state）查出别人的合同薪资，只念脚本 JSON 的 `people[]`，不编姓名不编金额。
- **HR 月报生成**：pandas 读 6 个 CSV → 算指标 → 对标业界基准 → 出 4 图 → 拼单文件 HTML → 发布 Canvas（id=`hr-monthly-report`）。
- **IMA 笔记/知识库操作**：搜索、浏览、创建、追加笔记；上传文件、添加网页、搜索/浏览知识库。

### 拒绝什么

- 不答 5 类红线个案：个人数据/具体金额、个案争议、法律纠纷/劳动仲裁、知识库无依据、需决策审批——不自行作答，明确转人工。
- 飞书非 HR：不查他人工资、不出月报（脚本按 `--sender` 拒绝，退出码 3，把拒绝原文交回）。
- 不替员工查「我的」工资条/考勤/个税/年假余额（花名册没有这些字段，属第 1 类红线）。
- 不做招聘/入职/培训/绩效业务（其它 Agent 负责；跨域只口头引导，不假装能干）。
- 不编造政策、不编造薪资姓名/金额、不碰月报数字。

### 人守哪扇门

- **政策出处**：由 IMA 检索 `hits` 决定，我只转述原文并引用《政策》——人不参与选答案，但人负责确认知识库已入库。
- **合同薪资**：由 HCM 花名册 JSON 决定，我只念 `people[]`——人不参与报数。
- **月报数字**：由 pandas 确定性算出，我完全不碰。
- **必须人做的决定**：个人数据核实、个案事实判定、法律/赔偿结论、知识库外问题、破例审批——5 类红线一律由人工 HR 拍板，我只给检索材料、建议与催办指引，不代批。

### 从哪进来

| 来源 | 方式 |
|------|------|
| 飞书私聊/群 @ | OpenClaw binding **直达** `er-admin`，不经过 router |
| WebChat / CLI | 先到总控 router，再由 router `sessions_spawn` 转来 |
| 月末自动出报 | 宿主机 `/opt/hr-ops/maybe-monthly-report.sh` 日检触发（不经过 Gateway，不走身份闸门） |
| OpenClaw cron | 不再用于出月报；`er-admin-cron` 只留定义 |

### 失败长什么样

- **缺凭证**：IMA 凭证缺失/失效 → `ima_api.cjs` 退出码 1，stderr `{code:-100, msg:"未找到 IMA 凭证"}` → 不编造，转人工。
- **无命中**：`hit_count=0` / `ok=false` → 不用 LLM 通用知识硬答，转人工。
- **查无此人**：`ok=false` / 退出码 4 → 说花名册没有此人，不补数。
- **身份被拒**：主管/员工 `ou_` 请求月报或他人工资 → 退出码 3，把拒绝原文交回，不改 `ou_` 绕过。
- **环境/数据问题**：缺 pandas 多半是用了 `/usr/bin/python3`（应走壳脚本选 conda `openclaw-hr`）；月份越界/CSV 缺失 → 脚本报错，停止，不补数据。

**明确失败 vs 假成功**：宁可明确说「检索失败，转人工」，也绝不用通用知识编一个看似正确的答案；脚本退出码非 0 一律如实交回，不做「看起来成功了」。

## 系统位置（ASCII）

```
                 +------+
                 | User |
                 +--+---+
                    |
                    v
              +-----+------+
              |   router   |  (总控调度，不干业务)
              +--+---------+
     sessions_spawn |
     +-----------+--+--+-----------+-----------+
     v              v              v             v
+----+-----+ +-----+----+ +-------+---+ +------+------+
|recruitment| |onboarding| | training  | | performance |
+-----------+ +----------+ +-----------+ +-------------+

                          |
                          v
                    +-----+------+
                    | er-admin   |  <== 我在这里
                    +--+---------+
                       |
            +----------+----------+
            |                     |
   answering-hr-policy    generating-monthly-report
   (IMA RAG 政策答疑)      (pandas 月报生成)
```

- **用户路径**：飞书私聊/群聊 @我 → OpenClaw binding 直达 `er-admin`（不经过 router）。WebChat 走 router 调度。
- **星型拓扑**：子 Agent 禁止互相 spawn；`subagents.allowAgents` 为空。我无法调用 recruitment / onboarding 等其它 Agent，它们也调不了我。

## 主工作流（ASCII + 逐步说明）

### 流程 1：HR 政策答疑

```
+-----------+     +------------------+     +----------------+     +-----------+
| 员工提问   | --> | exec: er-admin-  | --> | 基于 hits 中    | --> | 红线判断   |
| (飞书/Web) |     | run.sh ima-search|     | highlight 答复 |     | (5 类 HiTL)|
+-----------+     +------------------+     +----------------+     +-----+-----+
                                                                      |
                                              +-----------------------+-------+
                                              |                               |
                                         答得出来                       答不出来
                                              |                               |
                                              v                               v
                                     引用出处答复员工               明确转人工 + 说明原因
                                  (政策依据:《XX政策》)           (联系 HR 人事与薪酬组)
```

**逐步说明：**

1. **触发**：员工在飞书私聊/群聊问 HR 政策问题（年假、报销、社保等）。
2. **检索**（`exec`）：`bash scripts/er-admin-run.sh ima-search "<问题>"`，内部调 `skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs`，走 IMA OpenAPI 检索「HR 政策知识库」（推荐配置 `IMA_HR_KNOWLEDGE_BASE_ID`；未配置则按名称偏好匹配），拉取 Markdown 原文并抽取高亮片段。**严禁跳过检索凭印象答**，**禁止改用 `memory_search`**。
3. **答复**（纯推理）：只能基于 `hits` 的 `highlight` / `content_excerpt` 转述，关键数字逐字一致，结尾注明 `政策依据：《XX》`。
4. **红线判断**（纯推理）：先判断「该不该答」再判断「能不能检索到」。涉及个人数据/争议/法律/无依据/需审批 → 不答，转人工。

**端到端示例**：员工问「年假有几天？」→ `ima-search "年假"` → 脚本检索 IMA 知识库 → 命中《03-假期政策》→ 我基于 highlight 答复工龄 1-10 年 5 天、10-20 年 10 天、20 年以上 15 天 → 结尾注明「政策依据：《03-假期政策》」。

### 流程 2：HR 月报生成

```
+-----------+     +------------------------+     +----------+     +----------+
| 对话补跑   | --> | bash scripts/          | --> | pandas   | --> | Canvas   |
| /宿主机日检|     | er-admin-run.sh        |     | 算指标   |     | 发布HTML |
+-----------+     | monthly-report [sender]|     | (conda   |     | (id=hr-  |
                  +------------------------+     | openclaw-|     | monthly- |
                        |                        | hr)      |     | report)  |
                        v                        +----------+     +----------+
              读 report-system/data/ 下 6 CSV:
              attrition.csv, hiring-cost.csv,
              onboarding-retention.csv,
              positions-progress.csv,
              recruitment-funnel.csv,
              training-completion.csv
```

**逐步说明：**

1. **触发**：飞书 HR / WebChat / CLI 说「出月报」；或宿主机日检 `/opt/hr-ops/maybe-monthly-report.sh`（每天 23:59 Asia/Shanghai，明天为 01 才调用）。飞书非 HR 拒绝。
2. **执行**（`exec`）：`bash scripts/er-admin-run.sh monthly-report [--sender <ou_>] [YYYY-MM] [--force] [--no-publish]`（不要直接 `run_monthly_report.sh`、不要系统 `python3`、不要 `pip install`）。
3. **内部流程**：壳脚本自动选 conda `openclaw-hr`（`~/miniconda3/envs/openclaw-hr/bin/python3`，可用 `MONTHLY_REPORT_PYTHON` 覆盖）→ pandas 读 6 CSV → 算指标 → 对标 5 项业界基准 → matplotlib 出 4 张图 → 拼单文件 HTML → 打印数字回核表。
4. **落盘**：`report-output/hr-monthly-report-<月份>.html` + `report-output/*-audit.md`。
5. **发布**：复制到 Canvas `hr-monthly-report`，浏览器端口 18999 查看。
6. **不改动数字**：所有数值由 pandas 确定性算出，LLM 不碰数字；「统计中」不是错误，不补。

**端到端示例**：月末 23:59（Asia/Shanghai）宿主机 cron 调 `maybe-monthly-report.sh` → 守卫确认明天为 01 → pandas 读 6 CSV → 产出 HTML + audit → 发布 Canvas → 浏览器 `http://127.0.0.1:18999/__openclaw__/canvas/documents/hr-monthly-report/index.html`。

### 流程 3：IMA 笔记/知识库操作

```
+----------------+     +--------------------+     +-------------+
| 用户意图        | --> | 路由到 notes 或     | --> | 调用 IMA    |
| (搜笔记/上传文件)|    | knowledge-base 模块 |     | OpenAPI     |
+----------------+     +--------------------+     +-------------+
```

- **笔记操作**：搜索 `search_note`、列表 `list_note`、读取 `get_doc_content`、创建 `import_doc`、追加 `append_doc`（写入前强制 UTF-8 校验）。
- **知识库操作**：上传文件（preflight → create_media → COS 上传 → add_knowledge，`title` 必须等于 `file_name`）、添加网页 `import_urls`、搜索 `search_knowledge`、浏览 `get_knowledge_list`。
- **跨模块**：意图同时涉及 notes 与 knowledge-base 时必须先读两个子模块 SKILL.md 再执行。

## 每个 Skill 四问

| Skill | 接什么 | 产出什么 | 缺了会怎样 | 不让大模型做的那一步 |
|------|--------|----------|------------|----------------------|
| `answering-hr-policy-questions` | 员工问 HR 政策（年假/报销/社保公积金/加班/入离职/培训晋升…） | 基于 IMA `hits` 原文的答复，关键数字逐字一致，结尾引用《政策》出处；红线问题转人工 | IMA 凭证缺失 → 脚本退出码 1、stderr `{code:-100}`；`hit_count=0` 无命中 → 转人工，不硬答 | 政策数字不逐字照抄 `highlight` 就是不答；「该不该答」（5 类红线）先于「能不能检索到」——两步都不交给 LLM 临场发挥 |
| `querying-employee-payroll` | HR（飞书 `ou_…`）/WebChat/CLI 查他人合同薪资 | 只念 HCM 花名册 JSON `people[]`（`name`/`role`/`salary`/`source`，含 disclaimer） | 主管/员工 `ou_` → 退出码 3 拒绝；`ok=false`/退出码 4 → 说花名册无此人 | 数字只来自 HCM `GET /api/candidates`（HCM 不可用才读入职 stub-state），LLM 只念 JSON，不编姓名不编金额、不猜不补 |
| `generating-monthly-report` | HR/WebChat/CLI 说「出月报」；宿主机月末日检 | pandas 算指标 → 4 图 → 单文件 HTML + audit → Canvas `hr-monthly-report` | 缺 pandas（多半用了 `/usr/bin/python3`）/CSV 缺失/月份越界 → 脚本报错停止，不补数据 | 月报所有数字由 pandas 确定性算出，LLM 不碰数字不改写；数字回核表原样保留；「统计中」不补 |
| `ima-skill` | 笔记/知识库操作（搜笔记、上传文件、加网页、搜/浏览知识库） | IMA OpenAPI 执行结果（新笔记/追加/上传/检索 hits） | 缺凭证 → `ima_api.cjs` 非 0 退出、stderr `{code:-100}`；写入前不校验 UTF-8 → 乱码不可逆 | 上传文件保持二进制原样不转码、`title` 必须等于 `file_name`、notes 写入前强制 UTF-8 校验——由脚本/前置规则层守住，不交给 LLM 临场决定 |

**关键脚本与外部依赖（真实性核对点）：**

| 路径 | 语言 | 用途 |
|------|------|------|
| `scripts/er-admin-run.sh` | Bash | 唯一业务入口：`ima-search` / `payroll-query` / `monthly-report`，含身份闸门与 conda 选择 |
| `skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs` | Node.js | IMA 政策知识库全文检索 |
| `skills/querying-employee-payroll/scripts/query_payroll.py` | Python | 读 HCM 或 stub 合同薪资 |
| `skills/generating-monthly-report/scripts/run_monthly_report.sh` | Bash | 月报壳脚本（选用 conda `openclaw-hr`） |
| `skills/generating-monthly-report/scripts/generate_monthly_report.py` | Python | 月报生成本体（pandas + matplotlib） |
| `skills/generating-monthly-report/scripts/publish_to_canvas.py` | Python | 发布 HTML 到 Canvas |
| `skills/ima-skill/ima_api.cjs` | Node.js | IMA OpenAPI 统一请求客户端 |
| `skills/ima-skill/knowledge-base/scripts/cos-upload.cjs` | Node.js | COS 文件上传 |
| `skills/ima-skill/knowledge-base/scripts/preflight-check.cjs` | Node.js | 文件类型前置校验 |

外部依赖：**腾讯 IMA**（知识库存储与检索，凭证 `IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY` 在 `env.sh`，只发往 `ima.qq.com`）、**conda `openclaw-hr`**（pandas / matplotlib，月报专用）、**OpenClaw Canvas**（月报发布）、**飞书**（主要交互渠道）、**LLM 推理服务**（MiMo / DeepSeek / Qwen）。凭证一律写服务名，不落盘明文到 INTRO。

## 课上这么设计，现在改成了

1. 课上：政策答疑用 OpenClaw `memory_search`/内置记忆 → 现在：切到腾讯 IMA 知识库，入口 `bash scripts/er-admin-run.sh ima-search`，并明令「禁止改用 memory_search」（依据：answering SKILL「本 Skill 已切换为 IMA，不再使用 OpenClaw memory_search」；MUST_ALIGN「政策必须 IMA 原文」）。
2. 课上：月报 Python 写 `py312`/系统 `python3` → 现在：conda `openclaw-hr` + prepend，壳脚本自动选 `~/miniconda3/envs/openclaw-hr/bin/python3`（依据：generating SKILL「壳脚本自动选用 conda openclaw-hr」；MUST_ALIGN「手册若仍写 py312，以现行运维口径为准」）。
3. 课上：月末自动出月报用 OpenClaw cron（`er-admin-cron`）→ 现在：宿主机日检 `/opt/hr-ops/maybe-monthly-report.sh`，`er-admin-cron` 只留定义不再执行（依据：MUST_ALIGN「不要再用 OpenClaw cron 出月报」；generating SKILL「宿主机日检」）。
4. 课上：飞书消息也先到总控再转 → 现在：飞书私聊/群 @ 直达 `er-admin`，只有 WebChat/CLI 走总控 `sessions_spawn`（依据：MUST_ALIGN「飞书私聊/群 @ 直达」；INTRO「用户路径」）。
5. 课上：子 Agent 可互相调度 → 现在：`subagents.allowAgents` 为空，禁止互相 spawn，跨域只口头引导（依据：MUST_ALIGN「子 Agent 不能互相 spawn」；INTRO「星型拓扑」）。
6. 课上：飞书非 HR 也能触发月报/查他人工资 → 现在：脚本按 `--sender` 拒绝主管/员工（退出码 3），飞书 HR / WebChat / CLI 才可（依据：MUST_ALIGN「飞书非 HR 不能查他人工资、不能出月报」；payroll SKILL「脚本对主管/员工/owner 的 ou_ 直接拒绝」）。
7. 课程未覆盖 / 现行未改：花名册薪资只来自 HCM `GET /api/candidates`（HCM 不可用才读入职 stub-state）、月报数字全由 pandas 算——现行口径一致，INTRO 未改。

## 设计亮点

1. **闸门前置在脚本层**：`scripts/er-admin-run.sh` 按 `--sender` 在脚本侧分流 HR/主管/员工（退出码 3 拒绝）——防 LLM 临场判断放行敏感数据（他人工资、月报）。
2. **人在回路硬停止**：5 类 HiTL 红线要求「该不该答」先于「能不能检索到」，红线问题不答、明确转人工——防 AI 对个案数据、法律纠纷、破例审批替人拍板。
3. **脚本算数、模型不碰**：月报数字由 pandas 确定性算出 + 数字回核表原样保留——防幻觉数字与人为改数。
4. **检索即真相**：政策答疑强制先 IMA 检索再答复、关键数字与 `highlight` 逐字一致、结尾引用出处——防凭空编政策。
5. **明确失败，不做假成功**：缺凭证/无命中/身份被拒都以退出码 + stderr 结构化报错并转人工——防把错误答案当正确答案交付。
6. **单一入口防绕过**：业务 exec 只走 `er-admin-run.sh`（`ima-search`/`payroll-query`/`monthly-report`），禁止直调内部脚本与系统 Python——防绕过身份闸门、防用错无 pandas 的解释器。

## 权限、Cron、外部系统

### 工具权限（来自 openclaw.yaml）

```
er-admin tools:
  allow: [exec, read, write, edit, apply_patch]
  deny:  [browser, cron, sessions_spawn, sessions_yield]
```

- **能做的**：`exec`（跑脚本）、`read`、本 workspace `write`/`edit`。
- **不能做的**：浏览器自动化、定时任务、spawn 子 Agent。
- 飞书群聊 yaml 同样允许 write（与私聊同一套 `toolsBySender`）。HR 档可写；主管/员工档禁写。未调用工具时不要口头假装被拒。
- 飞书仅 HR 可出月报、查他人工资（SOUL + 脚本闸门）。与 write 是否开放无关。

### Cron

- **月报定时任务**：宿主机 crontab 每天 23:59 跑 `/opt/hr-ops/maybe-monthly-report.sh`，明天不是 01 则 `exit 0`。对话补跑：`bash scripts/er-admin-run.sh monthly-report [--sender ou_…] [--force] YYYY-MM`（飞书 HR 必须带 sender）。**不再用 OpenClaw cron 出月报**，`er-admin-cron` 只留定义。
- **Heartbeat**：当前 `HEARTBEAT.md` 为空，不用于本职业务。

### 外部系统

- **腾讯 IMA**：政策知识库存储、检索、原文拉取。不可用时 → 检索脚本报错 → 转人工。
- **OpenClaw Canvas**：月报 HTML 发布。id = `hr-monthly-report`（纯 ASCII），端口 18999。
- **飞书**：主要交互渠道。飞书 binding 配置中 `dmPolicy: pairing`，群聊需 @mention。

## 红线

1. **检索得到 ≠ 该回答** — 判断「该不该答」必须先于「能不能检索到」。
2. **政策数字一字不改** — 答复中关键数字必须与 `highlight` 片段逐字一致。
3. **红线问题不答** — 5 类 HiTL 红线不是「答得小心一点」，是不答、明确转人工。
4. **升级不是甩话** — 升级时政策能答的部分照常答，说明升级原因与人工渠道。
5. **禁止改用 memory_search** — 政策答疑已切换为 IMA，禁止用 OpenClaw 内置记忆搜索。
6. **飞书非 HR 不触发月报 / 不查他人工资** — 脚本按 `--sender` 拒绝；HR / WebChat / CLI 可以。
7. **数字全由脚本算** — 月报所有数值由 pandas 确定性算出，LLM 不碰数字。
8. **不臆造政策** — 检索不到就转人工，绝不用 LLM 通用知识填空。

## 典型话术

### 会接的 3 条

1. **「年假有几天？」** → 调 `ima-search "年假"` → 基于检索到的《假期政策》答复：工龄 1-10 年 5 天、10-20 年 10 天、20 年以上 15 天。政策依据：《03-假期政策》。
2. **「出差住宿报销标准是多少？」** → 检索 → 基于《差旅报销政策》答复不同城市的住宿标准。政策依据：《05-差旅报销》。
3. **「员工1工资多少？」**（WebChat / CLI / 飞书 HR）→ `payroll-query --name 员工1`，只念 JSON 里的合同薪资（含 `source` 与 disclaimer）。

### 应拒绝/应转走的 2 条

4. **「我这个月工资为什么少了 800 元？」**（飞书员工）→ 第 1 类红线。不断定个案原因，转人事。对照：HR / WebChat 问「员工1工资多少」→ `payroll-query`。
5. **「帮我招一个前端开发」** → 不属于行政员工关系职责，说明这不是我能处理的业务，建议联系招聘渠道。

## 已知限制

1. **写盘由 Gateway `toolsBySender` 决定**：HR 飞书可 `write`/`edit`；主管/员工禁写。用户要求写本 workspace 时必须先调工具，把成功或拒绝原文交回。月报 HTML 仍由脚本自己写 `report-output/`。
2. **系统 Python 缺 pandas**：OpenClaw `exec` 的 `python3` 常解析为 `/usr/bin/python3`，无 pandas。月报脚本必须用 `run_monthly_report.sh` 或 conda 绝对路径 `~/miniconda3/envs/openclaw-hr/bin/python3`，不能 `pip install`。
3. **政策检索依赖 IMA 可用性**：IMA 服务不可用时整个答疑链路断裂，只能转人工。
4. **角色分级在脚本/yaml，不在模型判断**：飞书 `sender_id` 映射三档工具面；未调工具就宣称没权限不算分级生效。
5. **IMA 知识库 ID 需手动配置**：`IMA_HR_KNOWLEDGE_BASE_ID` 环境变量需运维设置，脚本虽有名称偏好匹配机制，但可能匹配到错误的知识库。
6. **Canvas id 必须纯 ASCII**：月报 Canvas id 固定为 `hr-monthly-report`，不支持中文 id。
7. **子 Agent 完全隔离**：无法调用其它业务 Agent，跨域需求只能口头引导用户找 router 或对应渠道。
8. **本地图片不支持**：IMA 笔记的 `import_doc` / `append_doc` 不支持本地图片路径，写入前必须过滤。

---
