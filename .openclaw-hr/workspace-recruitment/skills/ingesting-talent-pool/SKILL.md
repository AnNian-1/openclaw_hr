---
name: ingesting-talent-pool
description: Vectorize candidate resumes into a local talent-pool vector store so they become semantically searchable. Use this skill when a batch of candidate resumes needs to be turned into a talent pool, before any "find someone similar to X" search can run. Each candidate is stored as one overall vector plus four dimension vectors (education, experience, skills, industry) using SiliconFlow embeddings (default Qwen/Qwen3-Embedding-0.6B, 1024-d). This is the first step of the talent-pool pipeline; searching the pool is a separate skill (searching-talent-pool).
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# ingesting-talent-pool

把候选人简历批量向量化，建成一个本地人才库向量库 `talent-pool.json`——让躺在简历里的候选人变成可按语义相似度检索的「活数据」。

## 何时用这个 Skill

收到一批候选人简历、需要建人才库时用。典型场景：业务部门以后会问「再来一个像员工1的」，但要回答这个问题，得先有一个「库」。这个 Skill 就是建库的第一步。只点名库内已有姓名。

它是人才库流水线的第一环。建好库之后：
- 检索「像某人的人」是另一个 Skill `searching-talent-pool` 的事。
- 解释「为什么像」是另一个 Skill `explaining-similarity` 的事。

这个 Skill 只管「入库」——把简历变成向量库。

## 工作流程

入库分两个阶段，可以一把跑完，也可以分别重跑。

### 一把跑完（常规）

```bash
bash scripts/recruitment-run.sh python3 skills/ingesting-talent-pool/scripts/ingest_talent_pool.py all
```

`all` = 先 parse（结构化抽取）再 embed（向量化），两阶段连跑。脚本从 `inbox/` 读 `resume-*.md`（当前库约 8 人：员工1–7、面试者1），落盘 `talent-pool/talent-pool.json`。邮件落盘名（如 `员工1-后端开发.md`）不在此 glob 内，需先有 `resume-*.md` 或改名后再入库。

### 分阶段重跑

- `bash scripts/recruitment-run.sh python3 …ingest_talent_pool.py parse` —— 只做结构化抽取（增量，已抽过的跳过，不重复调抽取 LLM）。
- `bash scripts/recruitment-run.sh python3 …ingest_talent_pool.py embed` —— 只做向量化（读已抽好的 `parsed-all.json`，重算向量）。

什么时候分阶段：parse 中途挂了 → 重跑 `parse` 从断点续；只调整了向量化逻辑、结构化数据没变 → 只重跑 `embed`，省掉抽取的 API 开销。

两阶段、维度化文本、5 个向量的设计细则见 → `references/ingest-pipeline.md`

## 入库成功的判断

脚本跑完会打印三行关键信息，对照确认入库成功：

- `人才库已落盘: .../talent-pool.json` —— 向量库文件生成。
- `N 名候选人, 每人 1 整体向量 + 4 维度向量, 维度 1024` —— 份数对、每人 5 个向量。当前夹具不是课程 28 份四类各 7。

## 关键规则

- 入库产物固定落 `talent-pool/talent-pool.json`，下游检索 Skill 直接读它。
- parse 阶段每抽完一份立即落盘，进程挂了重跑会自动续——不要因为「上次没跑完」就从头重抽。
- 这个 Skill 依赖抽取用的 LLM（`XIAOMI_API_KEY`，mimo；脚本可回退 `DEEPSEEK_API_KEY`）和 `SILICONFLOW_API_KEY`（embedding，默认 `Qwen/Qwen3-Embedding-0.6B`，1024 维）。凭证由 `recruitment-run.sh` 注入，不要在 exec 里 `source`。不要切 DashScope embedding。
- 入库只是建库。检索和解释是 `searching-talent-pool`、`explaining-similarity` 两个独立 Skill。
