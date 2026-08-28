#!/usr/local/miniconda3/envs/py312/bin/python3
# -*- coding: utf-8 -*-
"""
相似度解释生成 (openclaw-ai-hr C-3b)

输入: search.py 落盘的检索结果 + 人才库
输出: 对 Top N 每个候选人, 生成"为什么和锚点候选人相似"的 HR 可读解释

关键设计 (吸取 C-3 教训 · 防 LLM 数字串台):
  - LLM 只做"解释组织", 不重新算相似度
  - 维度相似度数字由 search.py 真实算出, 原样传给 LLM, 禁止 LLM 改动
  - 解释里引用的事实(学校/技能/经历) 必须来自结构化数据, prompt 明确约束
  - 不让 LLM 自由发挥, 给定锚点和候选人的真实字段, 只让它"对比说人话"

用法: python3 explain.py --search talent-pool/search-张磊.json
"""
import os, sys, json, argparse
import urllib.request

from pathlib import Path

WORKSPACE = str(Path(__file__).resolve().parents[3])
POOL = os.path.join(WORKSPACE, "talent-pool/talent-pool.json")

def resolve_llm():
    model = os.environ.get("LLM_MODEL") or "mimo-v2.5-pro"
    is_mimo = "mimo" in model or "xiaomi" in (os.environ.get("LLM_BASE_URL") or "")
    base = os.environ.get("LLM_BASE_URL") or (
        "https://token-plan-cn.xiaomimimo.com/v1" if is_mimo else "https://api.deepseek.com"
    )
    url = base.rstrip("/") + "/chat/completions"
    key = (
        os.environ.get("LLM_API_KEY")
        or (os.environ.get("XIAOMI_API_KEY") if is_mimo or "xiaomi" in base else "")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    )
    return model, url, key

EXPLAIN_PROMPT = """你是招聘顾问。业务部门想"再招一个像【锚点候选人】的人"。
系统已用向量检索算出一名【相似候选人】,并给出了 4 个维度的真实相似度分数。
你的任务: 用 2-3 句话向 HR 说清"这个人为什么和锚点相似"。

严格约束:
1. 维度相似度分数是系统真实算出的, 你只能引用, 不能改动、不能编造新分数。
2. 你引用的所有事实(学校、技能、公司、经历年限)必须来自下面给的结构化字段, 不得编造。
3. 重点说"哪个维度最像、为什么", 也可点出"哪个维度差异较大"。
4. 只输出解释文字, 不要 JSON, 不要分点编号, 2-3 句话。

【锚点候选人】
{anchor}

【相似候选人】
{cand}

【系统算出的维度相似度(0-1,越高越像)】
{dims}
"""

def post_json(url, payload, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def fields_brief(c):
    p = c["parsed"]
    edu = p.get("education", {}) or {}
    works = "; ".join(f"{w.get('company','')}/{w.get('position','')}/{w.get('industry','')}"
                      for w in (p.get("work_experience", []) or []))
    return (f"姓名:{p.get('name','')}; 目标岗位:{p.get('target_position','')}; "
            f"学历:{edu.get('school','')} {edu.get('major','')} {edu.get('degree','')}; "
            f"工作年限:{p.get('total_experience_years','')}年; "
            f"工作经历:{works}; "
            f"技能:{', '.join(p.get('skills',[])[:15])}")

def explain_one(anchor, cand, dim_sims):
    dim_label = {"education": "教育", "experience": "经历", "skills": "技能", "industry": "行业"}
    dims_str = "; ".join(f"{dim_label[k]}={v}" for k, v in dim_sims.items())
    prompt = EXPLAIN_PROMPT.replace("{anchor}", fields_brief(anchor)) \
                           .replace("{cand}", fields_brief(cand)) \
                           .replace("{dims}", dims_str)
    model, url, key = resolve_llm()
    if not key:
        raise RuntimeError("未设置 XIAOMI_API_KEY / LLM_API_KEY")
    payload = {"model": model,
               "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.2}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = post_json(url, payload, headers)
    return r["choices"][0]["message"]["content"].strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", required=True, help="search.py 落盘的检索结果 json")
    args = ap.parse_args()

    pool = json.load(open(POOL, encoding="utf-8"))
    cmap = {c["id"]: c for c in pool["candidates"]}
    sr = json.load(open(os.path.join(WORKSPACE, args.search) if not os.path.isabs(args.search) else args.search,
                        encoding="utf-8"))

    if sr["query_type"] != "candidate":
        print("explain.py 目前只支持候选人锚点检索结果"); sys.exit(1)

    anchor = next((c for c in pool["candidates"] if c["name"] == sr["query"] or sr["query"] in c["id"]), None)
    if not anchor:
        print(f"找不到锚点候选人 {sr['query']}"); sys.exit(1)

    print(f"=== 「再来一个像{anchor['name']}的」— 相似度解释 ===")
    print(f"锚点: {anchor['name']} / {anchor['parsed'].get('target_position','')}\n")

    explained = []
    for r in sr["results"]:
        cand = cmap.get(r["id"])
        if not cand:
            continue
        text = explain_one(anchor, cand, r["dim_similarity"])
        explained.append({**r, "explanation": text})
        print(f"#{r['rank']} {r['name']} ({r['category']}) — 综合相似度 {r['similarity']}")
        dl = {"education": "教育", "experience": "经历", "skills": "技能", "industry": "行业"}
        print("   维度: " + " ".join(f"{dl[k]}{v}" for k, v in r["dim_similarity"].items()))
        print(f"   解释: {text}\n")

    sr["results"] = explained
    outpath = (os.path.join(WORKSPACE, args.search) if not os.path.isabs(args.search) else args.search) \
        .replace(".json", "-explained.json")
    json.dump(sr, open(outpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"带解释的检索结果已落盘: {outpath}")

if __name__ == "__main__":
    main()
