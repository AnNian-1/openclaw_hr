# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Exec（D-011）

所有 shell **整条命令**必须是下面之一：

- 收邮件：`bash scripts/fetch-mail.sh`
- 其它本域 Skill：`bash scripts/recruitment-run.sh <python3|node skills/…>`
- 看 inbox：`ls inbox/`、`cat inbox/…`（不要 `2>/dev/null`、不要 `$(date)`、不要 `source &&`）
- `mkdir -p profile/output`、`mv a b` 必须**单独一条**，禁止 `mkdir … && bash …`

禁止路径里出现 `workspace-onboarding` 等其它域。禁止 `python3 -c`。yaml 没有 `tools.exec.allowlist`。凭证由 `recruitment-run.sh` 注入。

不要直接 `python3 -c` / `sed` / `tee` 写 `workspace-onboarding`。闸会拒绝其它域路径。

## 招聘业务 Skill 清单

招聘子 Agent 的业务能力以 Skill 形式装在 `skills/` 目录下。下面是各 Skill 的用途和调用要点——具体怎么用看每个 Skill 的 `SKILL.md`。

### fetching-resumes-by-mail — 企业邮箱收简历

- **做什么**：经 IMAP 拉未读邮件里的简历附件（PDF/DOCX；ZIP/RAR 解压后再提），用 LLM **只读简历文件正文**抽出姓名/岗位，落盘为 `inbox/姓名-岗位.ext`；可选 `mark_read.py` 打 `\Seen`。
- **什么时候用**：简历还在企业邮箱 / QQ 邮箱，需要自动进 `inbox/` 再交给解析流水线。
- **调用要点**：
  - 收取（整条原样）：`bash scripts/fetch-mail.sh`
  - 标已读：`bash scripts/recruitment-run.sh python3 skills/fetching-resumes-by-mail/scripts/mark_read.py --uid "<uid...>"`（UID 来自本轮 `.fetched-mail.jsonl`）。
  - **身份与待办**：同一人覆盖后写 `needs-pipeline.jsonl`，本轮重解析+增量评分。岗位/同名说不清仍落盘走完流程，只写 `needs-hr.jsonl` 问 HR。`hr_queue.py list` / `list-pipeline`
  - 需要 `exec` 工具（`group:runtime` 权限组）。

### parsing-resumes — 简历解析

- **做什么**：把一份已转成 Markdown 的简历，抽取成对齐 `candidate-profile-schema.md` 的结构化候选人 JSON。
- **什么时候用**：收到一份简历 Markdown、需要把它变成结构化候选人数据时（评分 / 画像 / 人才库检索的上游）。
- **调用要点**：
  - 简历若是 PDF / DOCX，先用 `office-to-md` 转成 Markdown，再用本 Skill。
  - 抽取产出存到 `parsed/<简历名>.json`。
  - 抽取后必须用 `skills/parsing-resumes/scripts/validate_profile.js` 校验，跑通才算完成。
  - 跑校验脚本需要 `exec` 工具（`group:runtime` 权限组）。

### auditing-extraction — 抽取结果真实性核对

- **做什么**：对 `parsing-resumes` 的产出做字段级真实性核对——把候选人 JSON 逐字段回溯简历原文。硬提取字段逐字符比对原文出处，软推断字段核对 `_inferred` 标志且推断依据成立，并产出可追溯率。这是「内容真不真」的核对，与 `validate_profile.js` 的「形状对不对」（schema/合规结构校验）是两件事。
- **什么时候用**：一份候选人 JSON 抽取完、进入评分之前。解析产出是整条招聘链的地基，进评分前必须先核对真实性。
- **调用要点**：
  - 输入是 `parsed/<简历名>.json` + 对应的简历原文 Markdown（`inbox/<简历名>.md`），两个参数都要给。
  - 核对脚本 `node skills/auditing-extraction/scripts/audit_extraction.js parsed/<简历名>.json inbox/<简历名>.md`，做硬提取字段的逐字回溯，需要 `exec` 工具（`group:runtime` 权限组）。
  - 核对报告存到 `audited/<简历名>.audit.json`（逐字段核对结果 + 可追溯率）；退出码 0 = 核对通过，1 = 有字段对不上原文或漏标注。

### office-to-md — 办公文档转 Markdown

- **做什么**：把 PDF / DOC / DOCX / PPTX 转成 Markdown 文本。
- **什么时候用**：收到的简历是办公文档格式，需要先转成 Markdown 才能交给 `parsing-resumes`。

### filtering-sensitive-fields — 评分前合规过滤层

- **做什么**：在候选人画像 JSON 进入评分模型之前，物理删除受法律和政策约束的敏感字段——年龄/出生日期、性别、婚育、户籍籍贯、民族、健康/残疾、院校层次、政治面貌。递归扫所有层级（顶层 + `education` 等子层），剥完做合规自检。
- **什么时候用**：候选人画像准备进评分之前。它是评分 Pipeline 三层的**第一层**，固定排在 `scoring-candidates` 之前。评分模型一旦看到年龄性别，合规边界就破了——脱敏必须在评分之前。
- **调用要点**：
  - 命令 `node skills/filtering-sensitive-fields/scripts/filter_sensitive.js profiles/<候选人>.json scoring/clean-<候选人>.json`，需要 `exec` 工具（`group:runtime` 权限组）。
  - 退出码 0 = 过滤通过（合规自检剩余敏感字段 = 0）；1 = 自检未通过（脱敏后仍有残留，绝不能拿去评分）；2 = 文件/用法问题。
  - 物理删除的是画像的副本——原始画像保留敏感字段供 HR 统计、画像展示（敏感字段"可记录、禁评分"）。
  - 这是"删字段做合规"，与 `auditing-extraction` 的"核对字段真不真"是两件事。

### scoring-candidates — 8 维度评分 + 综合分 + 硬伤识别

- **做什么**：对一份脱敏后的候选人数据 + 岗位 JD，调大模型按 8 个固定维度（专业技能、经验匹配、逻辑能力、学习力、沟通能力、协作能力、抗压能力、价值观，各 1-5 分）打分，给出 0-100 综合匹配分、评级、评分理由、亮点、顾虑，并识别硬伤。支持单份评分，也支持批量评分一批候选人后按综合分排序。
- **什么时候用**：候选人数据经 `filtering-sensitive-fields` 脱敏之后。它是评分 Pipeline 三层的**第二层**。
- **调用要点**：
  - 输入必须是 `filtering-sensitive-fields` 脱敏后的 JSON，不能是含敏感字段的原始画像。
  - 单份 `node skills/scoring-candidates/scripts/score_candidate.js <脱敏json> <JD-md> [输出json]`（输出 `score-*.json`）；批量 `node skills/scoring-candidates/scripts/batch_rank.js <JD-md> scoring [输出json] clean-`（输出 `batch-score-*.json` + `ranking-*.json`，不覆盖 `score-*.json`）。默认读已有 `batch-score-*.json` 和 `score-*.json` 增量，不要无 `--force` 为「再排一次」全量打 LLM。人多或规则变更用 `--limit 3` 分多次 exec（timeout 建议 ≥600），最后 `--merge-only` 出榜。需要 `exec` 工具（`group:runtime`）。
  - 评分产出标"建议动作"不标"淘汰/录用"——AI 只评分不做淘汰决定（个保法 24 条 + Workday Mobley 判例）。
  - 评分产出的自由文本可能有数字串台风险，进 HR 决策前要过 `auditing-numbers` 回核。

### auditing-numbers — 评分产出数字回核

- **做什么**：把评分产出里所有自由文本字段（highlights、concerns、score_reasoning、各维度 dimension_reasons）里的「数字 + 单位」抽出来，逐个反查候选人**原始简历**，对不上的交大模型判定是不是虚构，是虚构就用最小替换对精确修正并留存修正前后快照。四步：抽取（正则）→ 比对（字符串匹配）→ 判定（大模型）→ 修正（最小替换对）。前两步确定性、第三步是大模型调用属非确定性。
- **什么时候用**：`scoring-candidates` 评分之后、评分结果交到 HR 手里之前。它是评分 Pipeline 三层的**第三层**。
- **调用要点**：
  - 命令 `node skills/auditing-numbers/scripts/audit_numbers.js <评分结果json> <候选人原简历md> [回核报告json]`，需要 `exec` 工具（`group:runtime`）。
  - 回核基准**只能是候选人原简历**，绝不能用 JD——JD 里的数字正是串台的来源。
  - 退出码 0 = 回核完成（未发现虚构、或发现并已修正都算完成，回核报告里列出每处修正前后快照）；1 = 回核失败（大模型判定多次重试仍不可用——绝不能把"判定没拿到"当"无虚构"放行）；2 = 文件/用法问题。
  - 它和 `auditing-extraction` 不同：`auditing-extraction` 核对的是简历解析产出，`auditing-numbers` 核对的是评分产出里的数字。

### generating-candidate-profiles — HTML 候选人画像生成

- **做什么**：把 ranking JSON 里某个候选人的解析数据 + 评分数据，渲染成一张图文并茂的单文件 HTML 候选人画像。画像七区块——基本信息卡、综合评级横幅、8 维度能力雷达图、与 JD 匹配度、工作经历时间线、技能词云、亮点·顾虑·硬伤三栏。雷达图与词云用 matplotlib 渲染、base64 内嵌进 HTML，画像是不依赖外部资源的单文件，离线可打开。
- **什么时候用**：`scoring-candidates`（必要时再经 `auditing-numbers` 回核）产出 ranking JSON 之后，需要把某个候选人变成 HR 能直接看的可视化页面时。HR 看不懂一堆 JSON，画像把字段组织成图文并茂的一页。
- **调用要点**：
  - 生成：`bash scripts/recruitment-run.sh python3 skills/generating-candidate-profiles/scripts/generate_profile.py <ranking.json或score.json> <姓名> profile/output/profile-<姓名>.html`。单份评分没有 `details` 时，脚本会自动找 `parsed/` 或 `scoring/clean-<姓名>.json`。先 `mkdir -p profile/output`（单独一条，不要 `&&`）。
  - 校验：`bash scripts/recruitment-run.sh node skills/generating-candidate-profiles/scripts/validate_profile_html.js <profile.html> <同一json> <姓名>`
  - 画像只忠实呈现 ranking JSON 已有的数据，不编造。合规红线字段（年龄/性别/婚育/政治面貌等）绝不渲染进画像——它们可存于数据资产，但不进展示给用人方看的画像。
  - 它和 `auditing-numbers` 不同：`auditing-numbers` 核对评分数字真不真，本 Skill 只负责把数据渲染成画像，不做真实性核对。

### ingesting-talent-pool — 候选人向量化入库

- **做什么**：把一批候选人简历批量向量化，建成本地人才库向量库 `talent-pool/talent-pool.json`。两阶段——parse 把简历抽成结构化 JSON（增量落盘 `parsed-all.json`、断点续跑），embed 把结构化数据按教育/经历/技能/行业分维度 + 整份摘要拼文本，送 SiliconFlow `Qwen/Qwen3-Embedding-0.6B` 转 1024 维向量（请求带 `dimensions`）。每名候选人存 1 个整体向量 + 4 个维度向量。
- **什么时候用**：HR 给一批历史候选人简历、需要建人才库时。这是人才库语义检索的第一步——没有库就没法做「再来一个像张三的」检索。
- **调用要点**：
  - 命令 `python3 skills/ingesting-talent-pool/scripts/ingest_talent_pool.py all`（parse + embed 连跑）；`parse` 只抽取（增量），`embed` 只向量化。需要 `exec` 工具（`group:runtime` 权限组）。
  - 依赖 `XIAOMI_API_KEY`（mimo 抽取）+ `SILICONFLOW_API_KEY`（embedding），运行前确认已 `source` 本机 `env.sh`。不要切 DeepSeek / DashScope embedding。
  - 产物固定落 `talent-pool/talent-pool.json`，下游检索 Skill 直接读它。
  - 它只建库，不做检索——检索是 `searching-talent-pool` 的事。

### searching-talent-pool — 人才库语义检索

- **做什么**：从人才库 `talent-pool.json` 检索出与锚点（库内某候选人，或一份 JD）最相似的 Top N 候选人，每人带教育/经历/技能/行业 4 个维度的相似度分解。相似度全程是真实的向量余弦计算，不经 LLM 排名。可选 `--compare-keyword` 同时跑朴素关键词检索做对照。
- **什么时候用**：业务部门说「再来一个像某某的人」「按这份 JD 找候选人」时。前提是人才库已用 `ingesting-talent-pool` 建好。
- **调用要点**：
  - 按候选人 `python3 skills/searching-talent-pool/scripts/search_talent_pool.py --like <姓名> --topn 5`；按 JD `--jd <JD文件> --topn 5`；加 `--compare-keyword` 跑关键词对照。需要 `exec` 工具（`group:runtime` 权限组）。
  - 检索结果落盘 `talent-pool/search-<锚点>.json`，这份 JSON 是 `explaining-similarity` 的输入。
  - 它只检索、给分数，不生成 HR 可读的解释——解释是 `explaining-similarity` 的事。

### explaining-similarity — 维度级相似度解释

- **做什么**：把 `searching-talent-pool` 的检索结果，翻译成 HR 能读懂的「为什么这个人像锚点」维度级解释。对 Top N 每人调大模型生成 2-3 句解释。维度分数由检索阶段真实算出、原样传入，大模型只组织语言、绝不重算分或编造新分数——防「数字串台」。
- **什么时候用**：`searching-talent-pool` 检索出 Top N 之后、把结果交给 HR 之前。检索结果只是「排名 + 分数」，HR 还需要知道「凭什么说像」。
- **调用要点**：
  - 命令 `python3 skills/explaining-similarity/scripts/explain_similarity.py --search talent-pool/search-<锚点>.json`，需要 `exec` 工具（`group:runtime` 权限组）。依赖 `XIAOMI_API_KEY`（mimo）。
  - 输入必须是候选人锚点的检索结果（`query_type=candidate`）；带解释的结果落盘 `talent-pool/search-<锚点>-explained.json`。
  - 它只把检索结果讲成人话——自己不做检索、不算分、不排名。算分排名是 `searching-talent-pool` 用余弦相似度做掉的确定性工作。

### transcribing-interviews — 面试录音转写 + 说话人分离

- **做什么**：把一段面试录音转成「按发言人标注的转写稿」——每个片段都标了是谁说的（`speaker_A` / `speaker_B` / 视场景更多）。**FunASR Paraformer-zh 转写 + CAM++ speaker embedding 凝聚聚类**一次推理同输出——零 token（ModelScope 国内直下载）、MIT 协议、自动决定说话人数量。生产推荐方案。
- **什么时候用**：收到一段面试录音、需要把它变成按发言人组织的文字稿时。这是面试纪要链路的**第一段**，`generating-minutes` 的上游。
- **调用要点**：
  - `bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py <音频文件> interview/<转写名>.json`。入口注入 `FUNASR_VENV` 与 `MODELSCOPE_CACHE`（本 workspace `models/`）。
  - `--device auto`：有 NVIDIA 走 `cuda:0`。OOM 再 `--device cpu`。
  - 转写后必须：`bash scripts/recruitment-run.sh node skills/transcribing-interviews/scripts/validate_transcript.js interview/<转写名>.json`。
  - **本机**：conda `funasr_me`。冒烟 `interview-yuangong1-tech2.wav`（282s）在 RTX 3050 4GB 上 `cuda:0` 约 11s wall、105 段、A/B=31/74，校验通过。
- **为什么不复用旧版 (faster-whisper + 基频聚类)**：旧版写死二分，只对一男一女双峰分得开的合成录音有效；真实面试多说话人 / 同性别相近音色直接失效。FunASR + CAM++ 一次推理自动决定说话人数、零 token、MIT 协议，三难全避开。旧版 `interview/scripts/asr-diarize.py` 仅作为"演示专用降级方案"保留，生产请用本 Skill 的 `transcribe_diarize.py`。

### generating-minutes — 结构化面试纪要 + 数字回核

- **做什么**：把 `transcribing-interviews` 产出的按发言人转写稿，交大模型整理成结构化面试纪要——关键问答（按面试官—候选人组织）、优势、待考察点、高亮时刻、评分建议。并对候选人口述的项目数字做回核：大模型只负责从转写稿里「提取」数字，「真伪」由确定性脚本对照候选人原简历判定。
- **什么时候用**：`transcribing-interviews` 产出转写稿之后，需要把它变成 HR 能直接用的结构化纪要时。这是面试纪要链路的**第二段、也是最后一段**。
- **调用要点**：
  - 命令 `python3 skills/generating-minutes/scripts/gen_minutes.py interview/<转写名>.json inbox/<候选人简历>.md interview/<纪要名>.json interview/<纪要名>.md --candidate <姓名> --position <岗位> --round <轮次> --interviewer speaker_A`，需要 `exec` 工具（`group:runtime` 权限组），依赖 `XIAOMI_API_KEY`（mimo）。
  - `--interviewer` 指定哪个说话人标签是面试官（默认 `speaker_A`）；若生成的纪要里面试官/候选人发言明显反了，换成 `speaker_B` 重跑。
  - 生成后必须用 `node skills/generating-minutes/scripts/validate_minutes.js interview/<纪要名>.json` 校验。校验项：纪要字段齐全、关键问答每组都是「面试官问题—候选人回答」两行结构、评分建议含 verdict + reason、数字回核统计自洽（回核确实逐项跑过、不是大模型编一个摘要）。退出码 0 = 通过，1 = 不通过，2 = 用法错误。
  - 数字回核的回核基准是候选人**原简历**；它有一个已知局限——回核脚本只匹配阿拉伯数字，候选人口述的中文数字表述（「千分之三」）会标「无阿拉伯数字、需人工核实」，是诚实标注、不是漏判成虚构。
  - 它和评分链路的 `auditing-numbers` 不同：`auditing-numbers` 回核的是评分产出，本 Skill 回核的是面试纪要里候选人的口述数字。

## Related

- [Agent workspace](/concepts/agent-workspace)
