# 人才库入库 Pipeline 细则

> ingesting-talent-pool Skill 的入库流程细则。SKILL.md 在需要时引用本文件。

## 目录

- 1. 入库要解决什么问题
- 2. 两阶段设计：parse 与 embed
- 3. 为什么每人存 5 个向量
- 4. 维度化文本怎么拼
- 5. 稳健性设计：增量落盘与断点续跑
- 6. 入库产物结构

## 1. 入库要解决什么问题

HR 手里的历史候选人通常躺在 Excel 或 ATS 里，是「死数据」——只能按列做关键词筛选，没法回答「再找几个像张磊的人」。人才库语义检索要把这批候选人变成「可按语义相似度检索的活数据」。第一步就是入库：把每份简历变成向量，存进一个本地向量库文件 `talent-pool.json`。

## 2. 两阶段设计：parse 与 embed

入库脚本 `ingest_talent_pool.py` 分两个阶段，可以分别重跑：

- **阶段 A · parse（结构化抽取）**：把每份 markdown 简历交给 DeepSeek，抽成统一的 JSON 结构——姓名、目标岗位、教育（学校/专业/学历/毕业年份）、工作经历（公司/职位/起止时间/行业）、工作年限、技能列表、自我评价。其中 tech 类 7 份直接复用 C-2 评分阶段已抽好的 `scoring/results/ranking-后端开发.json`（同一份数据不重复花 API 调用），其余 21 份调 DeepSeek。每抽完一份立即落盘 `parsed-all.json`。
- **阶段 B · embed（向量化）**：把结构化数据按「教育 / 经历 / 技能 / 行业」分段拼成维度化文本，外加一段整份摘要文本，全部送通义 `text-embedding-v3` 转成 1024 维向量，落盘 `talent-pool.json`。

CLI：`python3 ingest_talent_pool.py parse|embed|all` —— `parse` 只抽取、`embed` 只向量化、`all` 两阶段都做。

## 3. 为什么每人存 5 个向量

每名候选人入库时存 **1 个整体向量 + 4 个维度向量**（教育/经历/技能/行业），共 5 个。

如果整份简历只拍一个向量，检索结果只能给一个黑盒分数「相似度 0.67」——HR 没法知道是教育像还是经历像。分维度各做一个向量，检索时 4 个维度分别算余弦相似度，才能告诉 HR「这个人主要是经历和技能像，教育差一些」。「每人存 5 个向量」是后面 `searching-talent-pool` 维度分解、`explaining-similarity` 维度级解释能成立的根。

## 4. 维度化文本怎么拼

`build_dim_texts()` 把结构化数据拆成 5 段文本：

- `education`：学校 + 专业 + 学历 + 毕业年份
- `experience`：每段工作经历的「公司 + 职位 + 起止时间」拼接
- `industry`：各段工作经历的行业去重拼接
- `skills`：技能名列表拼接
- `summary`：目标岗位 + 工作年限 + 自我评价

整体向量来自 `build_full_text()` —— 把姓名、目标岗位、教育、经历、行业、技能、自我评价拼成一段完整文本。4 个维度向量分别来自 4 段维度文本。

## 5. 稳健性设计：增量落盘与断点续跑

入库要真把几十份数据跑通，必须处理两个稳健性细节：

- **每抽一份立即落盘**：28 份简历调 DeepSeek 抽取，每份耗时几十秒到上百秒。`stage_parse()` 每抽完一份就 `json.dump` 写一次 `parsed-all.json`——进程中途挂了，下次 `ingest_talent_pool.py parse` 直接从断点续跑，已抽过的「跳过」，不重复消耗 API。
- **prompt 里的 JSON schema 不用 `str.format()`**：`PARSE_PROMPT_HEAD` 含大量 `{` `}`（JSON 字段说明），脚本用字符串拼接而非 `.format()`——`.format()` 会把花括号当占位符报 `KeyError`。这是「prompt 含结构化示例」时的通用坑。

## 6. 入库产物结构

`talent-pool.json` 顶层字段：

- `embedding_model`：`text-embedding-v3`
- `dimension`：1024
- `candidate_count`：候选人份数
- `built_at`：构建时间
- `candidates`：候选人数组，每项含 `id` / `resume_file` / `category` / `name` / `parsed`（结构化数据）/ `dim_texts`（5 段维度文本）/ `full_text` / `vector`（整体向量）/ `dim_vectors`（4 个维度向量）

`candidates[].category` 由简历文件名第二段（如 `resume-tech-01-...` → `tech`）得出。
