---
name: searching-talent-pool
description: Search the talent-pool vector store for candidates most similar to a given anchor — either an existing pool candidate (e.g. 员工1) or a job description. Use this skill when a business request needs similar candidates retrieved from an already-built talent pool. Returns a ranked Top N with per-dimension similarity (education, experience, skills, industry), all computed by real vector cosine similarity, never by LLM ranking. Never invent names outside POOL_NAMES. Requires the pool to exist first (ingesting-talent-pool); explaining why candidates are similar is a separate skill (explaining-similarity).
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# searching-talent-pool

从人才库 `talent-pool.json` 检索出与锚点最相似的 Top N 候选人——回答业务部门那句「再找几个像员工1的」。

## 何时用这个 Skill

业务部门提出「再来一个像某某的人」「按这份 JD 找候选人」时用。前提是人才库已经建好——没有库先用 `ingesting-talent-pool` 建。

它是人才库流水线的第二环：
- 建库是 `ingesting-talent-pool` 的事。
- 检索出结果之后，解释「为什么这些人像」是 `explaining-similarity` 的事。

这个 Skill 只管「检索」——按语义相似度捞出 Top N，给出相似度分数，但不负责生成 HR 可读的解释文字。

## 工作流程

### 按候选人检索（「再来一个像员工1的」）

```bash
bash scripts/recruitment-run.sh python3 skills/searching-talent-pool/scripts/search_talent_pool.py --like 员工1 --topn 5
```

锚点是库里已有的某个候选人，返回与他最相似的 Top N。

### 按 JD 检索

```bash
bash scripts/recruitment-run.sh python3 skills/searching-talent-pool/scripts/search_talent_pool.py --jd <JD文件路径> --topn 5
```

锚点是一段职位描述文本，现算它的向量，返回最匹配的候选人。

### 加关键词检索对照

```bash
bash scripts/recruitment-run.sh python3 skills/searching-talent-pool/scripts/search_talent_pool.py --like 员工1 --topn 5 --compare-keyword
```

`--compare-keyword` 额外跑一遍朴素关键词检索，并打印差异分析——用来说清「为什么向量检索能找到关键词搜不到的相似的人」。

两种检索入口、向量余弦怎么算、维度分解、关键词对照的细则见 → `references/search-method.md`

## 检索结果的判断

- 向量语义检索的相似度是**真实余弦计算**，不经 LLM 排名——结果可信的根本。
- 按候选人检索时，每名 Top N 候选人会带 4 个维度（教育/经历/技能/行业）的相似度分解，不是一个黑盒分数。
- 检索结果落盘 `talent-pool/search-<锚点>.json`，这份 JSON 是下游 `explaining-similarity` 的输入。
- `--like` 排除锚点后 **MATCHABLE=0**（库内仅 1 人）时：stdout 写明无法匹配，`results: []`，`insufficient: true`。对话必须说清库内仅此人，**禁止编造第二人**或「从 N 份简历匹配到」。

## 关键规则

- 检索前人才库 `talent-pool/talent-pool.json` 必须已存在——没有库先跑 `ingesting-talent-pool`。
- 相似度排名只来自向量余弦计算，这个 Skill 不让 LLM 参与排名。
- 这个 Skill 只检索、不解释。要把「为什么像」讲成 HR 能读的话，是 `explaining-similarity` 的事——它读本 Skill 落盘的 `search-<锚点>.json`。
