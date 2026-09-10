# searching-talent-pool 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：从人才库 `talent-pool.json` 检索与给定锚点（候选人或 JD）最相似的 Top N 候选人，每人带 4 维度（教育/经历/技能/行业）相似度分解。

## 评测场景

### 场景 1 · 按候选人检索「再来一个像员工1的」

- 输入：人才库 `talent-pool.json`（现行约 8 人：员工1–7、面试者1），锚点「员工1」
- query：从人才库找出与员工1最相似的 Top 5 候选人
- expected_behavior：
  - 返回 Top N，每人有综合相似度 + 4 维度相似度
  - 相似度是真实向量余弦，不经 LLM 排名
  - 只出现 `POOL_NAMES` 里的人，禁止编徐昊/周敏/张磊
  - 检索结果落盘 `talent-pool/search-员工1.json`

### 场景 2 · 向量检索 vs 关键词检索对照

- 输入：同场景 1，加 `--compare-keyword`
- query：检索像员工1的人，并和关键词检索做对照
- expected_behavior：
  - 同时输出向量语义检索 Top 5 和关键词检索（词重叠率）Top 5
  - 打印差异分析：只有向量召回的人、只有关键词召回的人
  - 体现关键词检索的硬伤——把语义不相关但词面重叠的候选人（如财务经理、运营总监）误排进「像后端架构师」的结果

### 场景 3 · 按 JD 文本检索候选人

- 输入：人才库 + 一份 JD（职位描述）文本文件
- query：按这份 JD 找最匹配的候选人
- expected_behavior：
  - 现算 JD 文本的向量，与库内每人整体向量算余弦相似度排 Top N
  - JD 检索没有锚点候选人的维度向量，维度分解可为空，但综合相似度排序正常
  - 检索结果落盘

### 场景 4（边界）· 锚点候选人不在库 / 人才库不存在

- 输入：`--like` 一个库里没有的姓名，或 `talent-pool.json` 尚未建立
- query：检索
- expected_behavior：
  - 锚点找不到 → 打印「库内找不到候选人: X」，退出码 1
  - 人才库文件不存在 → 报错，不返回虚假检索结果
  - 提示先用 ingesting-talent-pool 建库

### 场景 5（边界）· MATCHABLE=0（库内仅 1 人）

- 输入：过滤后库内只剩锚点自己（或仅员工1）
- expected_behavior：
  - stdout 写明无法匹配，`results: []`，`insufficient: true`
  - 对话必须说清库内仅此人，**禁止编造第二人**


## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c3b-skillified.md` CP2 · 步骤 2。
