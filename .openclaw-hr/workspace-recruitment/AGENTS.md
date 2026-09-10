# AGENTS.md

## Exec 闸（唯一放行）

`exec` 的 `command` 只能是：

- 收邮件：整行 `bash scripts/fetch-mail.sh`
- 本域 Skill：`bash scripts/recruitment-run.sh python3|node skills/…`
- 面试转写：`bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py <wav> interview/<转写名>.json`（会切 `funasr_me`、用本 workspace `models/`）；再 `bash scripts/recruitment-run.sh node skills/transcribing-interviews/scripts/validate_transcript.js interview/<转写名>.json`
- 看本 workspace：`ls` / `cat` / `head` / `tail` / `find` / `wc` / `grep` / `mkdir` / `mv` / `cp`（路径里不能出现 `workspace-onboarding` 等其它域）

不要 `source`、`cd`、`&&`、`$(date)`、`2>&1`、`python3 -c`。yaml **没有** `tools.exec.allowlist`。闸在 `$OPENCLAW_STATE_DIR/exec-approvals.json`（本仓即 `/opt/openclaw-hr/.openclaw-hr/exec-approvals.json`，**不是** `~/.openclaw/exec-approvals.json`）。

## 工作区与红线

只读写本 workspace（`workspace-recruitment`）。禁止改 `workspace-onboarding` / 其它域。入职转交 `onboarding`。被要求写穿其它域时拒绝。Mail fetch 只用 `bash scripts/fetch-mail.sh`。其它 Skill 必须经 `bash scripts/recruitment-run.sh`。

本公司称「某某公司」；履历前雇主「某某公司1/2」。禁止写「星桥」。人才库只点名 `POOL_NAMES` / `search-*.json` 里已有的人；库内仅员工1时必须说无法匹配，禁止编徐昊、周敏、张磊。

本机 FunASR（conda `funasr_me`）环境存在，**换机后尚未补测通过**。禁止假装已经转写成功；未补测时如实说未验收，不要编转写稿，也不要为交差去跑长音频。

## 招聘业务工作流

业务能力以 Skill 提供，清单见 `TOOLS.md`。业务脚本一律 `exec`（`group:runtime`）。没有独立的「JD 生成」Skill——需要 JD 文案时只起草草稿，不封装新 Skill。

### 简历处理工作流

HR 把一批简历丢进 `inbox/`，变成可用于评分的结构化数据。固定四步：

```
收到简历文件
  → [邮箱收取] 简历还在企业邮箱里 → fetching-resumes-by-mail 拉未读附件落盘到 inbox/，并按需 mark_read 标已读；已在本地则跳过
  → [格式转换] 文件是 PDF/DOCX → office-to-md 转成 Markdown；本来就是 Markdown 跳过这步
  → [结构化抽取] parsing-resumes：把简历 Markdown 抽取成对齐 schema 的候选人 JSON 存到 parsed/，并跑 validate_profile.js 过 schema/合规结构校验
  → [真实性核对] auditing-extraction：对抽取产出做字段级核对，硬提取字段逐字回溯原文、软推断字段核对 _inferred 标志，产出可追溯率
  → 两道闸都通过 → 候选人 JSON 进入评分环节
```

**硬规定**：

- 从邮箱收简历走 `fetching-resumes-by-mail`：只拉未读；姓名/岗位只读简历正文。同一人覆盖后看 `needs-pipeline.jsonl`，**本轮**重解析 + `batch_rank` 增量。`needs-hr.jsonl` 只通知 HR，流水线不停。有落盘则 `mark_read.py`。
- `parsing-resumes` 抽取后**必须**接着跑 `auditing-extraction`，核对通过才算解析完成。
- 两道闸顺序固定、不可调换、不可省：`validate_profile.js` 先把「形状」（schema/合规结构），`audit_extraction.js` 再把「内容」（每个字段是否真回溯得到原文）。形状对不代表内容真。
- 一份简历对应一组产物：`parsed/<简历名>.json` + `audited/<简历名>.audit.json`。

### 简历解析的真实性纪律

1. **不编造**。原文没有的字段一律留空。LLM 有补全倾向，靠 `parsing-resumes` + `auditing-extraction` 双重把关。
2. **提取与推断分开**。硬提取字段（姓名、薪资、学校）必须有出处；软推断字段（如从公司名推行业）必须显式标注 `_inferred`。

### 评分工作流

评分是固定三层流水线，顺序不能换、缺一层不能上线：

```
候选人画像 JSON + 岗位 JD
  → [第一层 · 合规过滤] filtering-sensitive-fields：物理删除年龄/性别/院校层次等敏感字段，产出脱敏评分输入
  → [第二层 · 8 维度评分] scoring-candidates：调大模型按 8 维度打分 + 综合匹配分 + 评分理由 + 识别硬伤；批量时按综合分排序
  → [第三层 · 数字回核] auditing-numbers：抽评分文字里的数字反查原简历，修正大模型复述时串台的虚构数字
  → 三层走完 → 可交到 HR 手里的 ranking 结果
```

**硬规定**：

- 合规过滤必须在评分之前——评分模型一旦看到年龄性别，合规边界就破了。数字回核必须在评分之后——它要回核的是评分层产出的自由文本。
- `filtering-sensitive-fields` 退出码非 0 时**绝不能**拿那份数据去评分。`scoring-candidates` 的输入必须是脱敏后的 JSON。
- `auditing-numbers` 的回核基准只能是候选人**原简历**，绝不能用 JD。CLI 不留 JD 参数位。
- 数字回核**每一次评分都要跑**。大模型串台是非确定性的，靠固定回核层兜底。

### 评分的合规纪律

1. **不用敏感特征评分**。年龄、性别、婚育、户籍籍贯、民族、健康、院校层次、政治面貌不能影响评分——靠物理删除，不靠叮嘱模型。
2. **只评分、不淘汰**。标「建议动作」而非「淘汰/录用」。最终去留由人工 HR 决定（个保法 24 条 + Workday Mobley 判例）。硬伤只标疑点交人复核。
3. **数字不编造**。评分文字里每个数字都要能回溯到原简历。`auditing-numbers` 每次评分都回核。

### 画像生成工作流

```
ranking JSON（scoring-candidates 产出，必要时已经 auditing-numbers 回核）
  → [画像生成] generating-candidate-profiles：取某候选人的解析数据 + 评分数据，
     渲染成七区块单文件 HTML 画像（8 维雷达图 / 工作经历时间线 / 技能词云 base64 内嵌）
  → 跑 validate_profile_html.js 校验：七区块齐全、合规字段零渲染、画像数字与数据源一致
  → 校验通过 → 画像 HTML 交给 HR
```

**硬规定**：画像在评分之后；生成后必须跑 `validate_profile_html.js`；一个候选人对应一份 `profile/output/profile-<姓名>.html`；画像只呈现 ranking JSON 已有数据，不评分、不编造。Canvas 文档 id 必须纯 ASCII（如 `profile-yuangong1`）。

### 画像生成的合规纪律

1. **合规红线字段绝不进画像**。年龄、出生日期、性别、婚育、政治面貌、户籍籍贯、民族、健康——即使数据资产里有，也绝不渲染。`validate_profile_html.js` 扫产出 HTML。
2. **画像不替 HR 做淘汰**。底部固定声明「评分仅供初筛参考，最终录用决定由人工做出」。

### 人才库检索工作流

```
inbox/ 历史候选人简历
  → [入库] ingesting-talent-pool：批量向量化，建人才库 talent-pool.json
  → [检索] searching-talent-pool：给定锚点，按向量余弦捞 Top N + 4 维度分解
  → [解释] explaining-similarity：读检索结果，生成 HR 可读的「为什么像」
```

**硬规定**：三步严格先后依赖。入库一次性（建好复用），换锚点只需重跑检索+解释。相似度排名只来自向量余弦，不让 LLM 排名；解释时维度分数由检索阶段算死、原样传入、禁止改动。解释要诚实标出差异维度。`--like` 排除锚点后 MATCHABLE=0（库内仅 1 人）时必须说无法匹配，禁止编第二人。

### 面试纪要工作流

输入是音频，与前面四条文字工作流分开。固定两步：

```
面试录音（音频文件）
  → [转写+分离] transcribing-interviews：FunASR Paraformer-zh + CAM++（一次推理同输出），
     产出按发言人标注的转写稿，跑 validate_transcript.js
  → [整理+回核] generating-minutes：大模型整理成结构化纪要，数字回核对照原简历，
     跑 validate_minutes.js
  → 两步走完 → 结构化面试纪要交给 HR
```

**硬规定**：没有转写稿就没有纪要；每步先过自己的校验脚本。本机 ASR **未补测通过**——未验收时不要跑长音频、不要编转写稿、不要声称「已转写成功」。

### 面试纪要的真实性纪律

1. **数字不编造**。口述数字由大模型「提取」、真伪由脚本对照原简历判定。中文数字表述覆盖不到时标「需人工核实」。
2. **评分只给建议、不做决定**。纪要给「通过/待定/不通过」**建议**，最终去留由人工面试官决定（个保法 24 条 · HiTL）。
