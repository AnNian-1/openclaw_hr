#!/usr/local/miniconda3/envs/py312/bin/python3
# -*- coding: utf-8 -*-
"""
人才库语义检索 (openclaw-ai-hr C-3b)

两种检索入口:
  - 按候选人:   python3 search.py --like 张磊        -> "再来一个像张三的"
  - 按 JD 文本: python3 search.py --jd <jd文件路径>   -> 按职位描述找相似候选人

检索逻辑:
  1. 取 query 向量(候选人: 库内已有整体向量; JD: 现算)
  2. 与库内每名候选人算余弦相似度 -> Top N
  3. 维度级分解: 用 教育/经历/技能/行业 4 个维度向量分别算相似度
     -> 检索结果不是一个黑盒分数, 能说清"哪个维度像"
  4. (可选) 对比关键词检索 (BM25 式词重叠), 体现向量 vs 关键词差异

真实性: 相似度全部基于真实 embedding 余弦计算, 不经 LLM 排名。
"""
import os, sys, json, math, argparse, re
import urllib.request

WORKSPACE = os.path.expanduser("~/.openclaw-hr/workspace-recruitment")
POOL = os.path.join(WORKSPACE, "talent-pool/talent-pool.json")
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

def cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot/(na*nb) if na and nb else 0.0

EMBED_BASE = os.environ.get(
    "DASHSCOPE_COMPAT_BASE_URL",
    "https://llm-5ipvwnjovosmatzx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)

def embed(texts):
    # compatible-mode: POST /embeddings （OpenAI 协议）
    payload = {"model": "text-embedding-v3", "input": texts, "dimensions": 1024}
    headers = {"Authorization": f"Bearer {DASHSCOPE_KEY}", "Content-Type": "application/json"}
    url = f"{EMBED_BASE.rstrip('/')}/embeddings"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    embs = sorted(d["data"], key=lambda x: x.get("index", 0))
    return [e["embedding"] for e in embs]

# ---------- 关键词检索(对照组) ----------
def tokenize(text):
    # 简单中英混合分词: 英文按词, 中文按 2-gram
    text = text.lower()
    en = re.findall(r"[a-z0-9\+\#]+", text)
    zh = re.findall(r"[一-鿿]", text)
    bigrams = ["".join(zh[i:i+2]) for i in range(len(zh)-1)]
    return set(en) | set(bigrams)

def keyword_score(q_text, c_text):
    qt, ct = tokenize(q_text), tokenize(c_text)
    if not qt:
        return 0.0
    return len(qt & ct) / len(qt)  # query 词命中比例

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--like", help="按候选人姓名找相似")
    ap.add_argument("--jd", help="按 JD 文件找相似候选人")
    ap.add_argument("--topn", type=int, default=5)
    ap.add_argument("--compare-keyword", action="store_true", help="同时跑关键词检索做对照")
    args = ap.parse_args()

    pool = json.load(open(POOL, encoding="utf-8"))
    cands = pool["candidates"]
    print(f"人才库: {pool['candidate_count']} 名候选人 | embedding={pool['embedding_model']} | 建于 {pool['built_at']}\n")

    # ---- 确定 query ----
    if args.like:
        q = next((c for c in cands if c["name"] == args.like or args.like in c["id"]), None)
        if not q:
            print(f"库内找不到候选人: {args.like}"); sys.exit(1)
        q_vec = q["vector"]
        q_dim_vecs = q["dim_vectors"]
        q_text = q["full_text"]
        pool_list = [c for c in cands if c["id"] != q["id"]]  # 排除自己
        print(f"=== 查询: 找出和【{q['name']}】({q['parsed'].get('target_position','')}) 相似的候选人 ===")
        print(f"    锚点候选人画像: {q['dim_texts']['summary'][:80]}")
        print(f"    技能: {q['dim_texts']['skills'][:100]}\n")
    elif args.jd:
        jd_text = open(args.jd, encoding="utf-8").read()
        q_vec = embed([jd_text])[0]
        q_dim_vecs = None
        q_text = jd_text
        pool_list = cands
        print(f"=== 查询: 按 JD 找相似候选人 ({os.path.basename(args.jd)}) ===\n")
    else:
        print("需要 --like <姓名> 或 --jd <文件>"); sys.exit(1)

    # ---- 向量检索 ----
    results = []
    for c in pool_list:
        sim = cos(q_vec, c["vector"])
        dim_sims = {}
        if q_dim_vecs:
            for dim in ["education", "experience", "skills", "industry"]:
                dim_sims[dim] = cos(q_dim_vecs[dim], c["dim_vectors"][dim])
        kw = keyword_score(q_text, c["full_text"]) if args.compare_keyword else None
        results.append({"cand": c, "sim": sim, "dim_sims": dim_sims, "kw": kw})

    results.sort(key=lambda x: -x["sim"])

    # ---- 输出向量检索 Top N ----
    print(f"--- 向量语义检索 Top {args.topn} ---")
    dim_label = {"education": "教育", "experience": "经历", "skills": "技能", "industry": "行业"}
    for i, r in enumerate(results[:args.topn], 1):
        c = r["cand"]
        line = f"{i}. {c['name']:<6} [{c['category']}] {c['parsed'].get('target_position','')[:24]:<24} 综合相似度={r['sim']:.4f}"
        print(line)
        if r["dim_sims"]:
            dims = sorted(r["dim_sims"].items(), key=lambda x: -x[1])
            dim_str = "   维度: " + " | ".join(f"{dim_label[d]}={s:.3f}" for d, s in dims)
            print(dim_str)

    # ---- 关键词检索对照 ----
    if args.compare_keyword:
        kw_sorted = sorted(results, key=lambda x: -x["kw"])
        print(f"\n--- 关键词检索 Top {args.topn} (词重叠率,对照组) ---")
        for i, r in enumerate(kw_sorted[:args.topn], 1):
            c = r["cand"]
            print(f"{i}. {c['name']:<6} [{c['category']}] {c['parsed'].get('target_position','')[:24]:<24} 词重叠率={r['kw']:.4f}")

        # 差异分析
        vec_ids = [r["cand"]["id"] for r in results[:args.topn]]
        kw_ids = [r["cand"]["id"] for r in kw_sorted[:args.topn]]
        only_vec = [r["cand"]["name"] for r in results[:args.topn] if r["cand"]["id"] not in kw_ids]
        only_kw = [r["cand"]["name"] for r in kw_sorted[:args.topn] if r["cand"]["id"] not in vec_ids]
        print(f"\n--- 差异 ---")
        print(f"只有向量检索召回(语义相似但用词不同): {only_vec or '无'}")
        print(f"只有关键词检索召回(用词重叠但语义偏): {only_kw or '无'}")

    # 落盘检索结果
    out = {
        "query": args.like or args.jd,
        "query_type": "candidate" if args.like else "jd",
        "topn": args.topn,
        "results": [{
            "rank": i, "id": r["cand"]["id"], "name": r["cand"]["name"],
            "category": r["cand"]["category"],
            "target_position": r["cand"]["parsed"].get("target_position", ""),
            "similarity": round(r["sim"], 4),
            "dim_similarity": {k: round(v, 4) for k, v in r["dim_sims"].items()},
        } for i, r in enumerate(results[:args.topn], 1)],
    }
    tag = (args.like or "jd").replace("/", "_")
    outpath = os.path.join(WORKSPACE, f"talent-pool/search-{tag}.json")
    json.dump(out, open(outpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n检索结果已落盘: {outpath}")

if __name__ == "__main__":
    main()
