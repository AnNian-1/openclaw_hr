# ingesting-talent-pool 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把候选人简历批量向量化进本地人才库 `talent-pool.json`——每人 1 个整体向量 + 教育/经历/技能/行业 4 个维度向量。

## 评测场景

### 场景 1 · 全量入库（28 份候选人）

- 输入：`inbox/` 下 28 份 `resume-*.md` 候选人简历
- query：把全部候选人简历向量化入库，建好人才库
- expected_behavior：
  - 阶段 A（parse）把每份简历抽成结构化 JSON，落盘 `talent-pool/parsed-all.json`
  - 阶段 B（embed）把结构化数据向量化，落盘 `talent-pool/talent-pool.json`
  - 人才库 `candidate_count = 28`，四类（function/operations/product/tech）各 7 份
  - 每名候选人有 1 个整体向量（`vector`，1024 维）+ 4 个维度向量（`dim_vectors`：education/experience/skills/industry）
  - `embedding_model = text-embedding-v3`、`dimension = 1024`

### 场景 2 · 断点续跑（已抽部分简历）

- 输入：`parsed-all.json` 已有部分抽取进度（如已抽 10 份）
- query：继续入库
- expected_behavior：
  - parse 阶段对已抽过的简历打印「已抽取，跳过」，不重复调 DeepSeek（不重复消耗 API）
  - 只对剩余未抽的简历调 DeepSeek 抽取
  - 这是入库脚本「每份立即落盘 + 断点续跑」稳健性设计的验收点

### 场景 3 · 只重跑向量化阶段（embed）

- 输入：`parsed-all.json` 已是完整 28 份结构化数据
- query：只重新做向量化，不重新抽取
- expected_behavior：
  - 跳过 parse 阶段，直接读 `parsed-all.json` 做 embed
  - 复用已抽好的结构化数据，不调 DeepSeek，只调通义 embedding
  - 适用于「调整了维度文本拼法、要重算向量」的场景

### 场景 4（边界）· DeepSeek / 通义 API Key 缺失

- 输入：环境变量 `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY` 未设置
- query：入库
- expected_behavior：
  - parse 阶段抽取请求失败，脚本重试 3 次后对该份打印「抽取失败，跳过」，不中断整体
  - embed 阶段批次失败重试 3 次后 `RuntimeError` 明确报错，不产出残缺的 `talent-pool.json`
  - 不产出虚假的"入库成功"

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c3b-skillified.md` CP1 · 步骤 2。
