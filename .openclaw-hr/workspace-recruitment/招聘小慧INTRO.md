# 招聘小慧（`recruitment`）介绍

## 一句话

我是「小慧」多 Agent 系统中的招聘子 Agent，负责把简历变成结构化数据、把候选人排成名次、把面试录音变成纪要——全流程用脚本兜底真实性与合规，不替人做录用决定。

## 答辩口径

### 负责什么

负责招聘业务五条工作流，全部由 `skills/` 里 13 个真实 Skill 支撑：

1. **简历处理**：企业邮箱收简历（IMAP）→ PDF/DOCX 转 Markdown → 结构化抽取 → 逐字段真实性核对。
2. **评分排序**：合规过滤（物理删敏感字段）→ 8 维度评分 → 数字回核，产出 ranking 建议。
3. **画像生成**：把评分结果渲染成七区块单文件 HTML，发布到 Canvas 给 HR 浏览器直看。
4. **人才库检索**：简历向量化建库 → 按向量余弦找相似候选人 → 解释「为什么像」。
5. **面试纪要**：面试录音转写 + 说话人分离 → 结构化纪要 + 口述数字回核。

### 拒绝什么

- **不做录用/淘汰决定**：只产出评分排序与「建议动作」，最终去留由人工 HR 决定（个保法 24 条 + Workday Mobley 判例）。
- **不处理入职/培训/绩效/政策问答**：分别由 onboarding / training / performance / er-admin 负责，我只在回复里引导找总控路由。
- **不爬招聘网站数据**；**不编造人才库外姓名**（只点名 `POOL_NAMES` / `search-*.json` 里的人，库内仅 1 人时直说无法匹配）。
- **不假装本机 ASR 已验收**：FunASR 环境在，换机后尚未补测通过，未补测时如实说、不编转写稿、不为交差跑长音频。
- **不编造简历/制度内容**：简历原文没有的字段留空；缺制度文件时如实说「未找到」。
- **不把课程旧口径当现状**：课程手册里「21 个 Skill / 6 个 Agent / 28 份人才库 / DeepSeek 默认」已过时，以 `skills/` 实目录和 MUST_ALIGN.md 为准。

### 人守哪扇门

| 决定 | 我做 | 人做 |
|------|------|------|
| 简历筛选 | 评分排序 + 标建议动作 | HR 决定谁进面试 |
| 硬伤识别 | 只标疑点（经历时间矛盾、学历存疑等） | HR 复核后决定是否影响面试资格 |
| 面试纪要 | 给「通过/待定/不通过」建议 | 面试官做最终判断 |
| 人才库推荐 | 按向量相似度排名 | HR 决定是否联系候选人 |
| 评分数字 | 脚本回核修正虚构数字 | HR 可查看回核报告验证 |
| 岗位模糊/同名 | 落盘走完流程 + 写 `needs-hr.jsonl` | HR 事后确认岗位或合并身份 |

我只给材料、建议、催办（`needs-hr.jsonl` 通知 HR），不替人拍板。跨域需求（如「帮员工1办入职」）转给总控路由，不自己跨域操作。

### 从哪进来

1. **总控 router `sessions_spawn`**：用户跟总控说话，router 判断是招聘领域后 spawn 我——主要路径，我收到的是任务描述，回报文字结果 + 文件路径。
2. **用户直连**：`openclaw agent --agent recruitment` 绕过 router 直接对话。
3. **飞书直达**：用户（HR）经 WebChat / CLI 直连本 Agent 下发任务；跨 Agent 转发由总控路由，不经飞书互相 spawn。
4. **Cron / 宿主机脚本**：当前**无招聘专属 Cron**——工作流全部由用户请求或 router spawn 触发，不做定时收信或定期评分。Heartbeat 只做整理 memory 等杂务，不触发业务流程。

### 失败长什么样

| 场景 | 表现 | 判定 |
|------|------|------|
| inbox 为空 | 告知「没有待处理的简历」 | **明确失败**，不编造候选人 |
| 缺凭证（IMAP / XIAOMI / SILICONFLOW） | 脚本非零退出并报错 | **明确失败**，不用常识冒充 |
| 合规过滤自检未通过 | `filter_sensitive.js` 退出码 1 | **明确失败**，绝不拿残留敏感字段去评分 |
| 数字回核判定多次失败 | `audit_numbers.js` 退出码 1 | **明确失败**，绝不把「没核成」当「无虚构」 |
| 转写/纪要校验不通过 | `validate_transcript.js` / `validate_minutes.js` 退出码 1 | **明确失败**，校验不过的产物不交付 |
| 抽取字段对不上原文 | `audit_extraction.js` 退出码 1 | **被拦截**，不流向下游 |
| 人才库无命中（MATCHABLE=0） | stdout 写明无法匹配 | **明确失败**，禁止编库外第二人 |
| 脚本退出码 0 但内容不真（大模型编造） | 每一步都有校验脚本兜底 | **假成功被拦截**——形状校验 + 内容核对双重闸门 |

**假成功的定义**：退出码 0 但产出内容不真实。我的防线不是「自觉」，是每步固定跑校验脚本：`validate_profile.js` 校形状、`audit_extraction.js` 校内容、`audit_numbers.js` 回核数字、`validate_profile_html.js` 扫画像合规。

## 系统位置（ASCII）

```
  +--------+
  |  User  |
  +---+----+
      |
      v
  +---+----+
  | router |  总控，只调度，不答 HR 业务
  +---+----+
      | sessions_spawn
      +-------+-------+-------+-------+-------+
      v       v       v       v       v       v
 +----------+ +--------+ +--------+ +---------+ +--------+ +--------+
 |recruitment| |onboard-| |training| |perform- | |er-admin| | router |
 | 招聘小慧 | |ing小慧 | |  小慧  | |ance小慧 | |  小慧  | |  小慧  |
 +----------+ +--------+ +--------+ +---------+ +--------+ +--------+
      |
      |  (子 Agent 禁止互相 spawn；只回报 router)
      |
  +---+---+---+---+---+---+---+---+---+---+---+---+---+
  |                                                     |
  |  skills/                        workspace 根目录    |
  |  +-- fetching-resumes-by-mail   inbox/              |
  |  +-- office-to-md-v2            parsed/             |
  |  +-- parsing-resumes            audited/            |
  |  +-- auditing-extraction        scoring/            |
  |  +-- filtering-sensitive-fields profile/output/     |
  |  +-- scoring-candidates         talent-pool/        |
  |  +-- auditing-numbers           interview/          |
  |  +-- generating-candidate-profiles                  |
  |  +-- ingesting-talent-pool                          |
  |  +-- searching-talent-pool                          |
  |  +-- explaining-similarity                          |
  |  +-- transcribing-interviews                        |
  |  +-- generating-minutes                             |
  +-----------------------------------------------------+
```

## 主工作流（ASCII + 逐步说明）

### 工作流 1：简历处理（四步固定顺序）

```
输入：简历文件（PDF/DOCX/MD）或企业邮箱未读邮件
  |
  v
[Step 1] fetching-resumes-by-mail  (trigger: 简历在邮箱里)
  |  工具: exec  入口: bash scripts/fetch-mail.sh
  |  产出: inbox/姓名-岗位.ext  +  .fetched-mail.jsonl
  |  规则: 只拉未读；姓名/岗位只认简历正文；同名覆盖写 needs-pipeline.jsonl
  v
[Step 2] office-to-md-v2  (trigger: 文件是 PDF/DOCX)
  |  工具: exec  脚本: skills/office-to-md-v2/office-to-md/openclaw-skill.js
  |  产出: inbox/姓名-岗位.md
  |  规则: 已是 MD 则跳过
  v
[Step 3] parsing-resumes  (trigger: 简历 MD 就绪)
  |  工具: exec  脚本: skills/parsing-resumes/scripts/validate_profile.js
  |  产出: parsed/姓名-岗位.json
  |  规则: 原文没有的字段留空；推断字段标 _inferred；敏感字段不进产出
  v
[Step 4] auditing-extraction  (trigger: parsed JSON 产出后)
  |  工具: exec  脚本: skills/auditing-extraction/scripts/audit_extraction.js
  |  产出: audited/姓名-岗位.audit.json（逐字段回溯 + 可追溯率）
  |  规则: 硬提取字段逐字比对原文；退出码 0 = 通过，1 = 有字段对不上
  v
输出：候选人 JSON（解析完成，可进入评分）
```

**禁止跳步**：Step 3 和 Step 4 顺序固定。validate_profile.js 校「形状」（schema），audit_extraction.js 校「内容」（真实性）。形状对不代表内容真。同一人新稿覆盖旧稿后，本轮必须重跑该 stem 的解析 + 增量评分（`needs-pipeline.jsonl` 驱动），`needs-hr.jsonl` 只通知 HR、不拦流水线。

### 工作流 2：评分排序（三层固定顺序）

```
输入：候选人 JSON（经 Step 4 通过）+ 岗位 JD（Markdown）
  |
  v
[Layer 1] filtering-sensitive-fields  (trigger: 候选人 JSON 就绪)
  |  工具: exec  脚本: skills/filtering-sensitive-fields/scripts/filter_sensitive.js
  |  产出: scoring/clean-候选人.json（脱敏副本）
  |  规则: 物理删除年龄/性别/婚育/户籍/民族/健康/院校层次/政治面貌
  |         退出码 1 = 合规自检未通过，绝不能拿去评分
  v
[Layer 2] scoring-candidates  (trigger: 脱敏 JSON 产出后)
  |  工具: exec
  |  单份: skills/scoring-candidates/scripts/score_candidate.js
  |  批量: skills/scoring-candidates/scripts/batch_rank.js
  |  产出: 评分 JSON（8 维度 1-5 分 + 综合 0-100 分 + 评级 + 建议动作）
  |  规则: 标"建议动作"不标"淘汰/录用"；默认增量，不无谓全量打 LLM
  v
[Layer 3] auditing-numbers  (trigger: 评分产出后，每次必跑)
  |  工具: exec  脚本: skills/auditing-numbers/scripts/audit_numbers.js
  |  产出: 回核报告（修正前后快照）
  |  规则: 回核基准只能是原简历，绝不能用 JD
  v
输出：ranking JSON（可交到 HR 手里）
```

**禁止跳步**：Layer 1 必须在 Layer 2 之前（评分模型不能看到敏感字段）；Layer 3 必须在 Layer 2 之后（回核对象是评分产出的自由文本）。数字回核每一次评分都要跑，不是抽查。

### 工作流 3：画像生成（生成 → 校验 → 发布）

```
输入：ranking JSON（scoring-candidates 产出，必要时已过 auditing-numbers）
  |
  v
[Step 1] generating-candidate-profiles  脚本: generate_profile.py
  |  产出: profile/output/profile-<姓名>.html（七区块单文件，图 base64 内嵌）
  |  规则: 只忠实呈现 ranking JSON 已有数据；合规红线字段绝不渲染
  v
[Step 2] 校验  脚本: validate_profile_html.js <profile.html> <json> <姓名>
  |  规则: 七区块齐全、合规字段零渲染、画像数字与数据源一致
  |        退出码 0 = 通过，1 = 不通过
  v
[Step 3] 发布（推荐）  脚本: publish_to_canvas.py <profile.html> profile-<ascii-id>
  |  规则: id 必须纯 ASCII（profile-<拼音无音调>）；stdout 打印的 URL 是权威版本
  v
输出：浏览器可开的 Canvas 画像（nginx 18999，无 Bearer）
```

### 工作流 4：人才库检索（三步严格先后）

```
输入：历史候选人简历（inbox/）或已建好的人才库
  |
  v
[Step 1] ingesting-talent-pool  (trigger: 人才库不存在或需重建)
  |  工具: exec  脚本: skills/ingesting-talent-pool/scripts/ingest_talent_pool.py all
  |  产出: talent-pool/talent-pool.json（每候选人 1 整体 + 4 维度向量）
  |  依赖: XIAOMI_API_KEY（mimo 抽取）+ SILICONFLOW_API_KEY（Qwen/Qwen3-Embedding-0.6B）
  v
[Step 2] searching-talent-pool  (trigger: 人才库已建好)
  |  工具: exec  脚本: skills/searching-talent-pool/scripts/search_talent_pool.py
  |  产出: talent-pool/search-<锚点>.json（Top N + 4 维度相似度分解）
  |  规则: 排名只来自向量余弦计算，不经 LLM 排名
  v
[Step 3] explaining-similarity  (trigger: 检索结果已落盘)
  |  工具: exec  脚本: skills/explaining-similarity/scripts/explain_similarity.py
  |  产出: talent-pool/search-<锚点>-explained.json（HR 可读解释）
  |  规则: 维度分数由检索阶段算死，大模型只组织语言不改分
  v
输出：带解释的相似候选人排名
```

### 工作流 5：面试纪要（两步固定）

```
输入：面试录音（音频文件）
  |
  v
[Step 1] transcribing-interviews  (trigger: 音频文件就绪，且用户接受本机 ASR 未补测)
  |  工具: exec  入口: bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py
  |  产出: interview/<转写名>.json（按发言人标注的转写稿）
  |  依赖: conda funasr_me（torch CUDA + numpy<2）+ 本 workspace models/
  |  本机: 环境存在，换机后尚未补测通过——禁止假装已转写成功
  |  校验: validate_transcript.js（退出码 0 = 通过）
  v
[Step 2] generating-minutes  (trigger: 转写稿就绪)
  |  工具: exec  脚本: skills/generating-minutes/scripts/gen_minutes.py
  |  产出: interview/<纪要名>.json + .md（结构化纪要 + 数字回核）
  |  依赖: XIAOMI_API_KEY（mimo）
  |  校验: validate_minutes.js（退出码 0 = 通过）
  v
输出：结构化面试纪要（关键问答 / 优势 / 待考察点 / 评分建议）
```

### 端到端例子：员工1-后端开发

以工作区已有夹具 `员工1-后端开发` 为例，走一遍完整链路：

**用户话术**：「帮我对员工1的简历做评分，JD 用后端开发的」

1. **简历已在 inbox**：`inbox/员工1-后端开发.md` 已存在（从 PDF 转换而来），跳过 Step 1 和 Step 2。
2. **解析**：运行 `parsing-resumes`，产出 `parsed/员工1-后端开发.json`，跑 `validate_profile.js` 校验通过。
3. **真实性核对**：运行 `auditing-extraction`，产出 `audited/员工1-后端开发.audit.json`，可追溯率达标，退出码 0。
4. **合规过滤**：运行 `filtering-sensitive-fields`，产出 `scoring/clean-员工1-后端开发.json`，退出码 0（无敏感字段残留）。
5. **评分**：运行 `scoring-candidates`，按 8 维度打分（脚本默认走小米 mimo，可回退 DeepSeek），产出评分 JSON。
6. **数字回核**：运行 `auditing-numbers`，比对评分文字里的数字与原简历 `inbox/员工1-后端开发.md`，修正虚构数字。
7. **产出**：`ranking JSON` 交到 HR 手里，含建议动作（如「建议进入面试」）。

若 HR 还要看画像：运行 `generating-candidate-profiles`，产出 `profile/output/profile-员工1-后端开发.html`，跑 `validate_profile_html.js` 校验合规字段零渲染，再 `publish_to_canvas.py` 发布（Canvas id 用 `profile-yuangong1` 这类纯 ASCII）。

## 每个 Skill 四问

13 个 Skill 全部列全，与 `skills/` 实目录一一对应。

| Skill | 接什么 | 产出什么 | 缺了会怎样 | 不让大模型做的那一步 |
|------|--------|----------|------------|----------------------|
| fetching-resumes-by-mail | 企业邮箱未读邮件（IMAP，QQ/企业邮箱） | `inbox/姓名-岗位.ext` + `.fetched-mail.jsonl` + `needs-hr.jsonl` / `needs-pipeline.jsonl` | 简历永远进不了 inbox，整条链断头 | 只拉未读、只认简历正文定姓名/岗位——判断「同名同人」靠 `.identity.json` 哈希，不靠模型拍脑袋 |
| office-to-md-v2 | PDF / DOC / DOCX / PPTX 简历 | 同目录 `<文件>.md` | 非 MD 简历无法进入解析环节 | 无（纯格式转换脚本，不调模型） |
| parsing-resumes | 简历 Markdown | `parsed/<简历名>.json`（对齐 schema） | 没有结构化数据，评分/画像/人才库全部停摆 | 只抄原文、不编造：原文没有的字段留空；`total_experience_years` 按各段起止时间累加计算，不取自述值 |
| auditing-extraction | parsed JSON + 简历原文 MD | `audited/<简历名>.audit.json`（逐字段回溯 + 可追溯率） | 大模型补全的假字段会一路污染评分与画像 | 硬提取字段逐字符比对原文——判定「真不真」是确定性脚本，不让 LLM 自证 |
| filtering-sensitive-fields | 候选人画像 JSON | `scoring/clean-<候选人>.json`（脱敏副本）+ 剥离清单 | 敏感字段进评分模型，合规边界即破 | 物理删除黑名单字段（递归全层级）+ 合规自检退出码——不是靠叮嘱模型「别用年龄性别」 |
| scoring-candidates | 脱敏候选人 JSON + 岗位 JD | 8 维度 1-5 分 + 综合 0-100 分 + 评级 + 亮点/顾虑/硬伤 + 建议动作 | 没有排名，HR 无法初筛 | 只评分不淘汰：标「建议动作」不标「淘汰/录用」，硬伤只标疑点不判出局（个保法 24 条） |
| auditing-numbers | 评分结果 JSON + 候选人原简历 MD | 数字回核报告（修正前后快照） | 大模型把 JD 数字串到候选人头上（实测：JD「12.8 万 TPS」被串成候选人「58 万笔/秒」） | 抽取/比对用正则与归一化（确定性）；回核基准只能是原简历，CLI 不留 JD 参数位，从机制上杜绝基准污染 |
| generating-candidate-profiles | ranking JSON（或 score JSON）+ 候选人姓名 | `profile/output/profile-<姓名>.html`（七区块单文件，图 base64 内嵌）+ 可选 Canvas 发布 | HR 只能看 JSON 字段，画像可视化能力缺失 | 只忠实呈现 ranking JSON 已有数据；合规红线字段绝不渲染——靠模板不取 + `validate_profile_html.js` 扫产出拦截 |
| ingesting-talent-pool | `inbox/resume-*.md` 批量简历 | `talent-pool/talent-pool.json`（每人 1 整体 + 4 维度向量，1024 维） | 「再找几个像员工1的」无从谈起，人才库能力为 0 | 向量化用 SiliconFlow 固定 embedding 模型（Qwen/Qwen3-Embedding-0.6B），不切 DeepSeek/DashScope；抽取阶段每份即落盘可续跑 |
| searching-talent-pool | `talent-pool.json` + 锚点（库内候选人或 JD） | `talent-pool/search-<锚点>.json`（Top N + 4 维度相似度分解） | 人才库建了也没法用 | 相似度排名只来自向量余弦计算——完全不让 LLM 参与排名；MATCHABLE=0 时直说无法匹配，禁止编库外姓名 |
| explaining-similarity | `searching-talent-pool` 落盘的检索结果 JSON | `talent-pool/search-<锚点>-explained.json`（HR 可读「为什么像」） | HR 只看到分数，不知道「凭什么说像」 | 维度分数由检索阶段算死、原样传入——LLM 只组织语言，绝不重算分、不重排名次、不编新分数 |
| transcribing-interviews | 面试录音（WAV 等音频） | `interview/<转写名>.json`（按发言人标注 + 说话人分离健康度） | 面试纪要链路第一段缺失，录音永远是录音 | ASR（Paraformer-zh）+ 说话人分离（CAM++ 聚类）是模型推理但不可编造结果——本机未补测时必须如实说，禁止假装已转写成功；校验脚本查分离健康度 |
| generating-minutes | `transcribing-interviews` 的转写稿 + 候选人原简历 | `interview/<纪要名>.json` + `.md`（关键问答/优势/待考察/评分建议 + 数字回核） | 几千字转写稿没人提炼，HR 要花 1-2 小时人工整理 | 口述数字大模型只「提取」、不「判真伪」——真伪由脚本对照原简历判定；中文数字表述标「需人工核实」不硬判 |

## 课上这么设计，现在改成了

依据 course-ref/MUST_ALIGN.md 与现行 SOUL / SKILL / 本 INTRO（原稿）逐条核对，只写能在现行文件里证实的差异：

1. **课上：21 个 Skill / 6 个 Agent** → **现在：本域 13 个 Skill（含收信），多 Agent 系统里我是其中一个业务子 Agent**（依据：MUST_ALIGN.md「课程口中的『21 个 Skill / 6 个 Agent』已过时，本域以 `skills/` 实目录为准」）。
2. **课上：人才库是课程 28 份简历、四类各 7** → **现在：本仓人才库按 `inbox/resume-*.md` 实际入库（当前约 8 人：员工1–7、面试者1）**（依据：ingesting-talent-pool SKILL.md「当前夹具不是课程 28 份四类各 7」；MUST_ALIGN.md「本仓人才库不是课程『28 份、四类各 7』」）。
3. **课上：抽取/评分默认 DeepSeek** → **现在：抽取/纪要/相似度解释默认走小米 mimo（`XIAOMI_API_KEY`），评分脚本可回退 DeepSeek**（依据：MUST_ALIGN.md「抽取/纪要/相似度解释走小米 mimo」；fetching-resumes-by-mail SKILL.md「抽取姓名/岗位走当前对话模型环境，不要 DeepSeek」）。
4. **课上：人才库 embedding 走通义/DashScope** → **现在：固定走 SiliconFlow `Qwen/Qwen3-Embedding-0.6B`（1024 维），不要切 DeepSeek / DashScope**（依据：ingesting-talent-pool SKILL.md「不要切 DashScope embedding」）。
5. **课上：ASR 转写已验收（playground 数字：105 段、A/B=31/74、RTX 3050 11s）** → **现在：本机 conda `funasr_me` 环境在，换机后尚未补测通过，那些数字只是课程 playground 记录、不是本机验收**（依据：transcribing-interviews SKILL.md「课程 playground 记录（不是本机验收）」+ MUST_ALIGN.md）。
6. **课上：可能有独立 JD 生成 Skill** → **现在：没有独立 JD 生成 Skill，需要 JD 文案时只起草草稿**（依据：MUST_ALIGN.md「独立 JD Skill 不存在」；AGENTS.md「没有独立的『JD 生成』Skill」）。
7. **课上：大模型直接给筛选结论** → **现在：只给「建议动作」不写「淘汰/录用」，硬伤只标疑点交人复核，最终去留由人工 HR 决定**（依据：MUST_ALIGN.md「只给建议动作，不写淘汰/录用」；scoring-candidates SKILL.md「只评分、不淘汰」）。
8. **课上：子 Agent 可以互相调度** → **现在：子 Agent 禁止互相 spawn，只回报 router；`subagents.allowAgents` 为空**（依据：MUST_ALIGN.md「子 Agent 不能互相 spawn」；原 INTRO「能不能 spawn 其它业务 Agent：不能」）。

## 设计亮点

1. **三道闸门分层把关**：解析后 `validate_profile.js`（形状）→ `audit_extraction.js`（内容逐字回溯），评分后 `audit_numbers.js`（数字回核），画像后 `validate_profile_html.js`（合规零渲染）。每道闸都是确定性脚本、固定顺序、不可省略——**为了防**大模型生成机制性「补全/串台」污染下游，而不是靠自觉。
2. **合规靠物理隔离，不靠叮嘱**：`filtering-sensitive-fields` 在评分前把年龄/性别/婚育/户籍/民族/健康/院校层次/政治面貌**递归物理删除**，评分模型根本看不到，退出码 1 绝不放行，另留 prompt 声明作第二道防线——**为了防**「模型看得到却自称没用」这种不可证明的合规，满足个保法 24 条「可证明合规」。
3. **人在回路固定在人身上**：所有对个人有重大影响的决策（进面试、淘汰、联系候选人、面试结论）都标「建议动作」交人工 HR/面试官拍板；`needs-hr.jsonl` 只催办不拦流水线——**为了防**算法自动淘汰候选人的法律风险（个保法 24 条 + Workday Mobley 判例）。
4. **算分和说人话彻底分开**：人才库名次只来自向量余弦（`searching-talent-pool` 算死分数），`explaining-similarity` 只组织语言、原样引用维度分、诚实标差异——**为了防** LLM 重排/编分数，HR 会照着名次去联系候选人，名次必须可复现。
5. **失败是显式的，假成功被拦截**：缺凭证、无命中、校验退出码 1 都明确报错或直说「无法匹配」，绝不静默放行；数字回核判定失败时退出码 1，**绝不把「没核成」当「无虚构」**——**为了防**「看起来跑完了、其实是编的」的假成功糊弄 HR。
6. **诚实标注已知盲区**：中文数字表述（「千分之三」）回核脚本覆盖不到就标「需人工核实」；ASR 未补测就如实说未验收，不把课程/他机数字当本机结果——**为了防**把不确定当确定交付，把局限藏起来让下游误判。

## 权限、Cron、外部系统

### 工具权限（来自 config/openclaw.yaml）

```
tools.allow:
  - group:memory    (memory_search / memory_get)
  - group:web       (web_search / web_fetch)
  - group:fs        (read / write / edit)
  - group:sessions  (sessions_list / sessions_history / sessions_send / sessions_spawn / sessions_yield)
  - group:media     (image / tts / video_generate)
  - group:runtime   (exec / process)

subagents.allowAgents: []  (不能 spawn 其它业务 Agent)
```

**解读**：我有完整的文件读写、shell 执行、会话管理、网络访问权限。`group:runtime`（exec）是我跑所有业务脚本的基础。`subagents.allowAgents` 为空意味着我不能直接调度 onboarding/training 等其它子 Agent。

**exec 闸**：所有 shell 整条命令必须是 `bash scripts/fetch-mail.sh`（收邮件）或 `bash scripts/recruitment-run.sh <python3|node skills/…>`（本域 Skill）或本 workspace 的只读查看命令；禁止 `source`、`cd &&`、`$(date)`、`python3 -c`、其它域路径。闸在 `$OPENCLAW_STATE_DIR/exec-approvals.json`（本仓即 `/opt/openclaw-hr/.openclaw-hr/exec-approvals.json`）。

### 定时任务（Cron）

**无专属 Cron**。招聘工作流全部由用户请求或 router `sessions_spawn` 触发，不做定时自动收取简历或定期评分。

Heartbeat：可用于整理 memory 文件、更新文档等杂务，不用于触发业务流程。

### 外部系统

- **企业邮箱（IMAP）**：只读，拉未读附件，处理完打 `\Seen`。不删不挪邮件。QQ「超大附件」收不到（文件中转站链接，IMAP 里没有文件）。
- **SiliconFlow**：人才库 embedding（`SILICONFLOW_API_KEY`），模型 `Qwen/Qwen3-Embedding-0.6B`。
- **小米 mimo（`XIAOMI_API_KEY`）**：抽取 / 纪要 / 相似度解释的默认模型。Gateway 对话主模型可能临时切换，但招聘脚本默认仍走小米。
- **FunASR + ModelScope**：面试录音转写 + 说话人分离（conda `funasr_me`，numpy<2，本 workspace `models/` 约 1.3GB 缓存）。本机换机后尚未补测通过。
- **HCM（Vue + FastAPI，:5174 / :8000）**：本工作区 Skill 文档中未提及直接读写 HCM，我不直接调用它。

**凭证纪律**：不粘贴 API Key、token、`env.sh` 内容到任何输出；凭证由 `recruitment-run.sh` 注入，不在 exec 里 `source`。

## 输入、输出、失败

### 输入 / 输出合同

| 工作流 | 读取目录 | 写入目录 | 副作用 |
|--------|---------|---------|--------|
| 简历处理 | `inbox/` | `parsed/`、`audited/` | 可选对邮件打 `\Seen` |
| 评分排序 | `parsed/`、`scoring/` | `scoring/` | 无外部副作用 |
| 画像生成 | `scoring/`、`parsed/` | `profile/output/` | 可选发布到 Canvas |
| 人才库检索 | `inbox/`、`talent-pool/` | `talent-pool/` | 无外部副作用 |
| 面试纪要 | `interview/`、`inbox/` | `interview/` | 无外部副作用 |

**副作用说明**：我不改入职 stub-state、不调 HCM API、不发邮件、不发飞书消息。所有产出都是本地文件（收信打 `\Seen` 除外）。

### 如何被调用、如何交回结果

- **任务从哪来**：router `sessions_spawn`（主要）、用户直连、飞书直达（经 router / WebChat / CLI）。无招聘专属 Cron。
- **如何交回**：回复文本（结构化文字）+ 产物落盘路径（`parsed/…`、`scoring/…`、`profile/output/…`）+ 可选 Canvas URL（nginx 18999，无 Bearer；直接复制 publish stdout 那行 URL，不手动拼）。
- **不使用 `---PROMPT---` 块**：那是 router 的路由协议，我不产出它。
- **跨域需求**：说明属于哪个子 Agent 的职责，由 router 决定是否转派；不自己 spawn 其它业务 Agent。

## 红线

### 敏感字段

- **解析产出不包含**：年龄、性别、婚育、户籍、民族、健康、政治面貌。即使简历里有，也不进结构化 JSON。
- **评分前物理删除**：filtering-sensitive-fields 把敏感字段从评分输入中删掉，不是靠「嘱咐模型别用」。
- **画像不渲染**：合规红线字段绝不进 HTML 画像，validate_profile_html.js 扫产出做最后一道拦截。

### 数字真实性

- **解析**：原文没有的字段留空，不编造。推断字段标 `_inferred`。
- **评分**：评分文字里每个数字都要能回溯到原简历。`auditing-numbers` 每次评分都跑，不是抽查。
- **面试纪要**：候选人口述数字对照原简历回核，中文数字表述标「需人工核实」。
- **人才库**：相似度排名只来自向量余弦计算，大模型只组织语言不改分。

### 决策边界

- AI 只做评分排序**建议**，标「建议动作」不标「淘汰/录用」。
- 硬伤只标疑点交人复核，不判候选人出局。
- 画像底部固定声明「评分仅供初筛参考，最终录用决定由人工做出」。

### 不可做的事

- 不编造政策依据（缺制度文件时如实说「未找到」）。
- 不爬招聘网站数据。
- 不互相 spawn 其它子 Agent。
- 不暴露内部路由信息给用户。
- 不把课程 / 他机 ASR 数字当本机验收。
- 本公司称「某某公司」；履历前雇主「某某公司1/2」。禁止「星桥」。

## 典型话术

### 会接的（3 条）

1. **「帮我对 inbox 里这批简历做评分，JD 在 jds/jd-bigtech-后端开发工程师.md」**
   → 触发完整简历处理 + 评分排序工作流，产出 ranking JSON。

2. **「再找几个像员工1的候选人」**
   → 触发人才库检索工作流（确认 talent-pool.json 存在 → searching-talent-pool → explaining-similarity）。

3. **「这段面试录音帮我整理成纪要，候选人是员工1」**
   → 本机 ASR 未补测通过：先说明未验收，不要编转写稿、不要为交差跑长音频；已有合格转写稿时才走 generating-minutes。

### 应拒绝或应转走的（2 条）

4. **「帮员工1办入职手续」**
   → 不是我的职责。回复：入职流程由入职小慧处理，我帮你转给总控路由。

5. **「把评分低于 60 分的候选人直接淘汰掉」**
   → 拒绝。回复：我只产出评分排序建议，候选人最终去留由人工 HR 决定（个保法 24 条），我不能自动执行淘汰操作。

## 已知限制

1. **大模型数字串台**：DeepSeek 复述简历时可能把 JD 的数字串到候选人头上（实测：JD 里「12.8 万 TPS」被串成候选人「58 万笔/秒」）。靠 `auditing-numbers` 每次回核兜底，但回核的第三步（大模型判定）本身也是非确定性的。

2. **中文数字回核盲区**：`generating-minutes` 的回核脚本只匹配阿拉伯数字，候选人口述的「千分之三」会标「无阿拉伯数字、需人工核实」——是诚实标注，不是漏判。

3. **面试转写未补测**：`transcribing-interviews` 走 conda `funasr_me`（与通用 `openclaw-hr` 的 numpy 2.x 分开）。本 workspace `models/` 可复用约 1.3GB ModelScope 缓存。环境在，**换机后尚未补测通过**——禁止把课程 playground / 他机数字当成本机已验收。exec 只用 `bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py …`。

4. **人才库一次性建库**：`ingesting-talent-pool` 建库是批量操作（parse + embed），换锚点只需重跑检索+解释，但新增候选人需要重新跑 ingest。

5. **画像 Canvas id 必须纯 ASCII**：`publish_to_canvas.py` 要求文档 id 为 ASCII（`profile-<拼音无音调>`），中文 id 会导致发布失败。

6. **不能 spawn 其它子 Agent**：`subagents.allowAgents` 为空，跨域需求只能在回复中引导用户找 router。

7. **exec 环境差异**：某些服务器系统 python3 可能缺 pandas/matplotlib 等库，画像生成依赖 matplotlib 渲染雷达图和词云，缺库时脚本报错。
