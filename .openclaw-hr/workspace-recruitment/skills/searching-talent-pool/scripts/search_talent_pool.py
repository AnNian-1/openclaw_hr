#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人才库语义检索 (openclaw-ai-hr C-3b)

两种检索入口:
  - 按候选人:   python3 search.py --like 员工1        -> "再来一个像张三的"
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
import urllib.error
import urllib.request
from pathlib import Path

# scripts/ → skill → skills → workspace-recruitment；可用 RECRUITMENT_WORKSPACE 覆盖
_SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = os.path.expanduser(
    os.environ.get(
        "RECRUITMENT_WORKSPACE",
        str(_SCRIPT_DIR.parents[2]),  # scripts → skill → skills → workspace-recruitment
    )
)
POOL = os.path.join(WORKSPACE, "talent-pool/talent-pool.json")
EMBED_API_KEY = (
    os.environ.get("SILICONFLOW_API_KEY")
    or os.environ.get("SF_API_KEY")
    or os.environ.get("DASHSCOPE_API_KEY")
    or ""
)
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
EMBED_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


def embed_wants_dimensions(model):
    m = (model or "").lower()
    return "qwen3-embedding" in m or "text-embedding-v3" in m

def cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot/(na*nb) if na and nb else 0.0

EMBED_BASE = os.environ.get(
    "EMBEDDING_BASE_URL",
    "https://api.siliconflow.cn/v1",
)

def jd_embed_max_chars():
    """SiliconFlow 单条 ≤512 token，Qwen3 / bge 默认截 480 字。
    仅 DashScope text-embedding-v3 才走超长分支，不要用在 Qwen3 上。"""
    if "text-embedding-v3" in EMBED_MODEL and "qwen" not in EMBED_MODEL.lower():
        return int(os.environ.get("JD_EMBED_MAX_CHARS", "6000"))
    return int(os.environ.get("JD_EMBED_MAX_CHARS", "480"))


def prepare_jd_text(text):
    text = (text or "").strip()
    limit = jd_embed_max_chars()
    if len(text) > limit:
        print(
            f"[search] JD 过长（{len(text)} 字），截到 {limit} 字再 embed（可用 JD_EMBED_MAX_CHARS 覆盖）",
            file=sys.stderr,
        )
        text = text[:limit]
    return text


def is_fixture_candidate(c):
    """测试夹具：姓名含「夹具」，或自评/摘要标明非真实候选人。"""
    name = str(c.get("name") or "")
    if "夹具" in name:
        return True
    parsed = c.get("parsed") or {}
    blob = " ".join(
        str(x) for x in (
            parsed.get("self_evaluation"),
            (c.get("dim_texts") or {}).get("summary"),
            c.get("full_text"),
        ) if x
    )
    return "测试夹具" in blob or "非真实候选人" in blob


def embed(texts, _retried=False):
    if not EMBED_API_KEY:
        print(
            "[search] 缺少 SILICONFLOW_API_KEY / DASHSCOPE_API_KEY，无法按 JD 实时 embed",
            file=sys.stderr,
        )
        sys.exit(2)
    payload = {"model": EMBED_MODEL, "input": texts}
    if embed_wants_dimensions(EMBED_MODEL):
        payload["dimensions"] = EMBED_DIM
    headers = {"Authorization": f"Bearer {EMBED_API_KEY}", "Content-Type": "application/json"}
    url = f"{EMBED_BASE.rstrip('/')}/embeddings"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[search] embedding HTTP {e.code}: {body[:800]}", file=sys.stderr)
        if e.code == 400 and not _retried and texts:
            shorter = prepare_jd_text(texts[0][: max(200, len(texts[0]) // 2)])
            if shorter and shorter != texts[0]:
                print("[search] 400 后缩短 JD 再试一次", file=sys.stderr)
                return embed([shorter], _retried=True)
        sys.exit(1)
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
    ap.add_argument(
        "--include-fixtures",
        action="store_true",
        help="检索结果包含测试夹具（默认过滤姓名含「夹具」或标明非真实候选人）",
    )
    args = ap.parse_args()

    pool = json.load(open(POOL, encoding="utf-8"))
    cands = pool["candidates"]
    if not args.include_fixtures:
        dropped = [c.get("name") for c in cands if is_fixture_candidate(c)]
        cands = [c for c in cands if not is_fixture_candidate(c)]
        if dropped:
            print(
                f"[search] 已过滤测试夹具 {len(dropped)} 人：{', '.join(dropped)} "
                f"（需要夹具时加 --include-fixtures）",
                file=sys.stderr,
            )
    pool_names = [c.get("name") for c in cands if c.get("name")]
    print(f"人才库: {pool.get('candidate_count', len(cands))} 名候选人 | embedding={pool.get('embedding_model')} | 建于 {pool.get('built_at')}\n")
    print(f"POOL_NAMES: {', '.join(pool_names) if pool_names else '(空)'}")
    print("硬规则: 对话回复禁止出现 POOL_NAMES 以外的姓名；禁止声称从库外 N 份简历匹配到。\n")

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
        print(f"MATCHABLE: {len(pool_list)}")
        if not pool_list:
            print("库内仅锚点本人，无法匹配相似候选人。禁止编造第二人。")
            out = {
                "query": args.like,
                "query_type": "candidate",
                "topn": args.topn,
                "insufficient": True,
                "matchable": 0,
                "pool_names": pool_names,
                "results": [],
            }
            tag = args.like.replace("/", "_")
            outpath = os.path.join(WORKSPACE, f"talent-pool/search-{tag}.json")
            json.dump(out, open(outpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"\n检索结果已落盘: {outpath}")
            sys.exit(0)
    elif args.jd:
        jd_text = prepare_jd_text(open(args.jd, encoding="utf-8").read())
        if not jd_text:
            print("JD 文件为空", file=sys.stderr)
            sys.exit(2)
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
        "insufficient": False,
        "matchable": len(results),
        "pool_names": pool_names,
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
