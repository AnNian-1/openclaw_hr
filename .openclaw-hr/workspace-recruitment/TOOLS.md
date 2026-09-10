# TOOLS.md

招聘子 Agent 的业务 Skill 清单：做什么、何时用、怎么调。细节看各目录 `SKILL.md`。

## Exec

所有 shell **整条命令**必须是下面之一：

- 收邮件：`bash scripts/fetch-mail.sh`
- 其它本域 Skill：`bash scripts/recruitment-run.sh <python3|node skills/…>`
- 看 inbox：`ls inbox/`、`cat inbox/…`（不要 `2>/dev/null`、不要 `$(date)`、不要 `source &&`）
- `mkdir -p profile/output`、`mv a b` 必须**单独一条**，禁止 `mkdir … && bash …`

禁止路径里出现 `workspace-onboarding` 等其它域。禁止 `python3 -c`。yaml 没有 `tools.exec.allowlist`。闸在 `$OPENCLAW_STATE_DIR/exec-approvals.json`。凭证由 `recruitment-run.sh` 注入。

## fetching-resumes-by-mail — 企业邮箱收简历

- **做什么**：经 IMAP 拉未读邮件里的简历附件（PDF/DOCX；ZIP/RAR 解压后再提），用 LLM **只读简历文件正文**抽出姓名/岗位，落盘为 `inbox/姓名-岗位.ext`；可选 `mark_read.py` 打 `\Seen`。
- **什么时候用**：简历还在企业邮箱 / QQ 邮箱，需要自动进 `inbox/` 再交给解析流水线。
- **调用要点**：
  - 收取（整条原样）：`bash scripts/fetch-mail.sh`
  - 标已读：`bash scripts/recruitment-run.sh python3 skills/fetching-resumes-by-mail/scripts/mark_read.py --uid "<uid...>"`（UID 来自本轮 `.fetched-mail.jsonl`）。
  - 同一人覆盖后写 `needs-pipeline.jsonl`，本轮重解析+增量评分。岗位/同名说不清仍落盘走完流程，只写 `needs-hr.jsonl` 问 HR。`hr_queue.py list` / `list-pipeline`

## parsing-resumes — 简历解析

- **做什么**：把一份已转成 Markdown 的简历，抽取成对齐 `candidate-profile-schema.md` 的结构化候选人 JSON。
- **什么时候用**：收到一份简历 Markdown、需要把它变成结构化候选人数据时（评分 / 画像 / 人才库检索的上游）。
- **调用要点**：
  - 简历若是 PDF / DOCX，先用 `office-to-md` 转成 Markdown，再用本 Skill。
  - 抽取产出存到 `parsed/<简历名>.json`。
  - 抽取后必须：`bash scripts/recruitment-run.sh node skills/parsing-resumes/scripts/validate_profile.js parsed/<简历名>.json`

## auditing-extraction — 抽取结果真实性核对

- **做什么**：对 `parsing-resumes` 的产出做字段级真实性核对——硬提取字段逐字符比对原文，软推断字段核对 `_inferred` 标志。这是「内容真不真」，与 `validate_profile.js` 的「形状对不对」是两件事。
- **什么时候用**：一份候选人 JSON 抽取完、进入评分之前。
- **调用要点**：
  - `bash scripts/recruitment-run.sh node skills/auditing-extraction/scripts/audit_extraction.js parsed/<简历名>.json inbox/<简历名>.md`
  - 核对报告存到 `audited/<简历名>.audit.json`；退出码 0 = 通过，1 = 有字段对不上或漏标注。

## office-to-md — 办公文档转 Markdown

- **做什么**：把 PDF / DOC / DOCX / PPTX 转成 Markdown 文本。
- **什么时候用**：收到的简历是办公文档格式，需要先转成 Markdown 才能交给 `parsing-resumes`。
- **调用要点**：`bash scripts/recruitment-run.sh node skills/office-to-md-v2/office-to-md/openclaw-skill.js inbox/<文件>.pdf`

## filtering-sensitive-fields — 评分前合规过滤层

- **做什么**：在候选人画像 JSON 进入评分模型之前，物理删除受法律和政策约束的敏感字段——年龄/出生日期、性别、婚育、户籍籍贯、民族、健康/残疾、院校层次、政治面貌。递归扫所有层级，剥完做合规自检。
- **什么时候用**：候选人画像准备进评分之前。评分 Pipeline **第一层**，固定排在 `scoring-candidates` 之前。
- **调用要点**：
  - `bash scripts/recruitment-run.sh node skills/filtering-sensitive-fields/scripts/filter_sensitive.js profiles/<候选人>.json scoring/clean-<候选人>.json`
  - 退出码 0 = 自检剩余敏感字段 = 0；1 = 仍有残留，绝不能拿去评分；2 = 文件/用法问题。
  - 删的是画像副本——原始画像可保留敏感字段供 HR 统计（可记录、禁评分）。

## scoring-candidates — 8 维度评分 + 综合分 + 硬伤识别

- **做什么**：对一份脱敏后的候选人数据 + 岗位 JD，按 8 个固定维度（专业技能、经验匹配、逻辑能力、学习力、沟通能力、协作能力、抗压能力、价值观，各 1-5 分）打分，给出 0-100 综合匹配分、评级、理由、亮点、顾虑、硬伤。支持单份与批量排序。
- **什么时候用**：经 `filtering-sensitive-fields` 脱敏之后。评分 Pipeline **第二层**。
- **调用要点**：
  - 输入必须是脱敏后的 JSON。
  - 单份：`bash scripts/recruitment-run.sh node skills/scoring-candidates/scripts/score_candidate.js <脱敏json> <JD-md> [输出json]`
  - 批量：`bash scripts/recruitment-run.sh node skills/scoring-candidates/scripts/batch_rank.js <JD-md> scoring [输出json] clean-`
  - 默认读已有 `batch-score-*.json` 和 `score-*.json` 增量，不要无 `--force` 为「再排一次」全量打 LLM。人多用 `--limit 3` 分多次 exec，最后 `--merge-only` 出榜。
  - 标「建议动作」不标「淘汰/录用」（个保法 24 条）。交 HR 前要过 `auditing-numbers`。

## auditing-numbers — 评分产出数字回核

- **做什么**：把评分自由文本里的「数字 + 单位」抽出来，逐个反查候选人**原简历**，对不上的交大模型判定是否虚构，是则最小替换并留快照。抽取/比对确定性，判定非确定性。
- **什么时候用**：`scoring-candidates` 之后、交 HR 之前。评分 Pipeline **第三层**。每次评分都要跑。
- **调用要点**：
  - `bash scripts/recruitment-run.sh node skills/auditing-numbers/scripts/audit_numbers.js <评分结果json> <候选人原简历md> [回核报告json]`
  - 基准只能是原简历，绝不能用 JD。CLI 不留 JD 参数位。
  - 退出码 0 = 回核完成（含已修正）；1 = 判定多次失败——绝不能把「没核成」当「无虚构」；2 = 文件/用法问题。

## generating-candidate-profiles — HTML 候选人画像生成

- **做什么**：把 ranking JSON 里某个候选人的解析 + 评分数据，渲染成七区块单文件 HTML（信息卡 / 评级横幅 / 8 维雷达图 / JD 匹配 / 时间线 / 技能词云 / 亮点·顾虑·硬伤）。图 base64 内嵌。
- **什么时候用**：评分（必要时回核）之后，需要给 HR 看可视化页面时。
- **调用要点**：
  - 生成：`bash scripts/recruitment-run.sh python3 skills/generating-candidate-profiles/scripts/generate_profile.py <ranking.json或score.json> <姓名> profile/output/profile-<姓名>.html`。先单独一条 `mkdir -p profile/output`。
  - 校验：`bash scripts/recruitment-run.sh node skills/generating-candidate-profiles/scripts/validate_profile_html.js <profile.html> <同一json> <姓名>`
  - 发布：`bash scripts/recruitment-run.sh python3 skills/generating-candidate-profiles/scripts/publish_to_canvas.py <profile.html> profile-<ascii-id>`。Canvas id 必须纯 ASCII。
  - 画像只忠实呈现已有数据；合规红线字段绝不渲染。

## ingesting-talent-pool — 候选人向量化入库

- **做什么**：把一批候选人简历批量向量化，建成本地 `talent-pool/talent-pool.json`。parse（结构化抽取）+ embed（教育/经历/技能/行业 + 整份摘要 → SiliconFlow `Qwen/Qwen3-Embedding-0.6B` 1024 维）。每人 1 个整体向量 + 4 个维度向量。
- **什么时候用**：需要建人才库、才能做「再来一个像员工1的」检索时。人才库流水线第一环。
- **调用要点**：
  - `bash scripts/recruitment-run.sh python3 skills/ingesting-talent-pool/scripts/ingest_talent_pool.py all`（或 `parse` / `embed`）
  - 脚本从 `inbox/` 读 `resume-*.md`。依赖 `XIAOMI_API_KEY`（mimo 抽取）+ `SILICONFLOW_API_KEY`（embedding）。不要切 DeepSeek / DashScope embedding。
  - 只建库，不做检索。

## searching-talent-pool — 人才库语义检索

- **做什么**：从 `talent-pool.json` 检索与锚点（库内某候选人或一份 JD）最相似的 Top N，带 4 维度相似度。分数是真实余弦，不经 LLM 排名。可选 `--compare-keyword`。
- **什么时候用**：业务说「再来一个像某某的人」「按这份 JD 找候选人」，且库已建好。
- **调用要点**：
  - `bash scripts/recruitment-run.sh python3 skills/searching-talent-pool/scripts/search_talent_pool.py --like 员工1 --topn 5`
  - 按 JD：`--jd <JD文件> --topn 5`
  - 结果落盘 `talent-pool/search-<锚点>.json`。只点名 stdout 的 `POOL_NAMES`；MATCHABLE=0 时必须说无法匹配，禁止编库外姓名。
  - 只检索、给分数，不生成解释。

## explaining-similarity — 维度级相似度解释

- **做什么**：把检索结果翻译成 HR 能读的「为什么像」。维度分数由检索阶段算死、原样传入，大模型只组织语言，绝不重算分或编新分数。
- **什么时候用**：`searching-talent-pool` 出 Top N 之后、交 HR 之前。
- **调用要点**：
  - `bash scripts/recruitment-run.sh python3 skills/explaining-similarity/scripts/explain_similarity.py --search talent-pool/search-员工1.json`
  - 输入必须是候选人锚点检索结果（`query_type=candidate`）。依赖 `XIAOMI_API_KEY`（mimo）。不要切 DeepSeek。
  - 自己不做检索、不算分。

## transcribing-interviews — 面试录音转写 + 说话人分离

- **做什么**：把面试录音转成按发言人标注的转写稿。FunASR Paraformer-zh + CAM++ 一次推理同输出。不做纪要、不评分。
- **什么时候用**：有面试录音、需要按发言人组织的文字稿时。纪要链路第一段。
- **本机状态（必须诚实）**：conda `funasr_me` 与本 workspace `models/` **环境存在，换机后尚未补测通过**。禁止把课程 playground / 他机数字（如 105 段、A/B=31/74、RTX 3050 11s）说成本机已验收。未补测时如实告知，不要编转写稿，也不要为交差跑长音频。
- **调用要点**（仅当用户明确要求且接受未验收风险时）：
  - `bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py <音频文件> interview/<转写名>.json`
  - 校验：`bash scripts/recruitment-run.sh node skills/transcribing-interviews/scripts/validate_transcript.js interview/<转写名>.json`
  - `--device auto`：有 NVIDIA 走 `cuda:0`。OOM 再 `--device cpu`。
- 旧版 `interview/scripts/asr-diarize.py`（faster-whisper + 基频）仅演示降级，生产请用本 Skill。

## generating-minutes — 结构化面试纪要 + 数字回核

- **做什么**：把转写稿整理成结构化纪要（关键问答 / 优势 / 待考察 / 评分建议），并对口述数字回核：大模型只提取，真伪由脚本对照原简历判定。
- **什么时候用**：已有合格转写稿之后。没有转写稿就没有纪要。本机 ASR 未补测时，不要假装已有转写稿。
- **调用要点**：
  - `bash scripts/recruitment-run.sh python3 skills/generating-minutes/scripts/gen_minutes.py interview/<转写名>.json inbox/<候选人简历>.md interview/<纪要名>.json interview/<纪要名>.md --candidate <姓名> --position <岗位> --round <轮次> --interviewer speaker_A`
  - 校验：`bash scripts/recruitment-run.sh node skills/generating-minutes/scripts/validate_minutes.js interview/<纪要名>.json`
  - `--interviewer` 指定面试官标签（默认 `speaker_A`）；说反了换成 `speaker_B`。依赖 `XIAOMI_API_KEY`（mimo）。
  - 回核只匹配阿拉伯数字；中文数字表述标「需人工核实」。
