---
name: explaining-similarity
description: Turn a talent-pool search result into HR-readable explanations of why each retrieved candidate is similar to the anchor. Use this skill right after searching-talent-pool produces a ranked result, when a recruiter needs to understand "why is this person like Zhang Lei" rather than just see a number. The dimension similarity scores are computed upstream and passed through verbatim — the LLM only organizes wording, it never re-ranks or invents scores, which prevents number drift. Reads the search-result JSON that searching-talent-pool writes; it does not perform retrieval itself.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# explaining-similarity

把 `searching-talent-pool` 的检索结果，翻译成 HR 能读懂的「为什么这个人像锚点」维度级解释。

## 何时用这个 Skill

`searching-talent-pool` 检索出 Top N 之后、要把结果交给 HR 之前用。检索结果只是「排名 + 分数」——候选人D综合相似度 0.6761、经历 0.772——HR 还是不知道「凭什么说像」。这个 Skill 把分数翻译成人话：「两人都在互联网核心业务线长期深耕，技能栈高度重叠……教育背景差异略大」。

它是人才库流水线的第三环、也是最后一环：
- 建库是 `ingesting-talent-pool` 的事。
- 检索、算相似度分数是 `searching-talent-pool` 的事。
- 这个 Skill 只把检索结果**讲成人话**——它自己不做检索、不算分。

## 工作流程

```bash
python3 skills/explaining-similarity/scripts/explain_similarity.py --search talent-pool/search-员工1.json
```

`--search` 指向 `searching-talent-pool` 落盘的检索结果 JSON。脚本对 Top N 每个候选人调 LLM 生成 2-3 句解释，带解释的结果落盘 `talent-pool/search-员工1-explained.json`，同时在终端打印。

输入输出、防数字串台的设计、解释质量标准的细则见 → `references/explain-method.md`

## 解释质量的判断

- 解释里引用的维度分数，必须与检索结果 JSON 里的**完全一致**——LLM 只能引用，不能改、不能编造新分数。
- 解释引用的事实（学校、技能、公司、经历）都来自候选人结构化字段，不是 LLM 编的。
- 解释诚实——相似度低的维度要被点出「差异较大」，不一味夸「都很像」。

## 关键规则

- 这个 Skill 必然调 LLM，但 LLM 只做「解释组织」——**算分、排名是上游 `searching-talent-pool` 用余弦相似度做掉的，这个 Skill 绝不让 LLM 重算分数或重排名次。** 这是防「数字串台」的根本。
- 输入必须是 `searching-talent-pool` 产出的候选人锚点检索结果（`query_type = candidate`）。JD 检索结果没有候选人锚点，不支持。
- 它依赖 `XIAOMI_API_KEY`（mimo）。运行前确认已 `source` 本机 `env.sh`。不要切 DeepSeek。
- 这个 Skill 是流水线最后一环——它读 `searching-talent-pool` 的产物，不读简历、不读人才库原始向量。
