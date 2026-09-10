# ingesting-talent-pool 评测场景

> 评测对象：把 `inbox/resume-*.md` 向量化进本地 `talent-pool.json`。
> 本仓不是课程 28 份四类各 7；抽取走 mimo（`XIAOMI_API_KEY`），embedding 走 SiliconFlow，不是通义/DashScope。

## 评测场景

### 场景 1 · 全量入库（当前 inbox 的 resume-*.md）

- 输入：`inbox/` 下 `resume-*.md`（现行约 7–8 份：员工1–7、面试者1）
- query：把这些简历向量化入库
- expected_behavior：
  - parse 抽成结构化 JSON，落盘 `talent-pool/parsed-all.json`
  - embed 落盘 `talent-pool/talent-pool.json`
  - 每人 1 个整体向量 + 4 个维度向量，`embedding_model = Qwen/Qwen3-Embedding-0.6B`、`dimension = 1024`
  - 不要用「四类各 7 / candidate_count=28」当本仓验收标准

### 场景 2 · 断点续跑

- 输入：`parsed-all.json` 已有部分抽取进度
- expected_behavior：已抽过的打印「已抽取，跳过」，不重复调抽取 LLM；只对剩余未抽的调 mimo

### 场景 3 · 只重跑 embed

- 输入：`parsed-all.json` 已完整
- expected_behavior：不调抽取 LLM，只调 SiliconFlow embedding

### 场景 4（边界）· API Key 缺失

- 输入：未设置 `XIAOMI_API_KEY` / `LLM_API_KEY` 或 `SILICONFLOW_API_KEY`
- expected_behavior：明确报错，不产出虚假「入库成功」；embed 失败不写残缺 `talent-pool.json` 冒充成功
