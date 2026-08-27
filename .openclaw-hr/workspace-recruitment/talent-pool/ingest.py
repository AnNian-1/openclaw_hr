#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人才库入库 Pipeline (openclaw-ai-hr C-3b)
把 28 份候选人简历向量化进本地向量库。

两阶段(可分别重跑,断点续跑):
  阶段 A (parse)  : 28 份简历 -> 结构化数据, 增量落盘 parsed-all.json
                    tech 7 复用 C-2 parsed, 其余调 DeepSeek
  阶段 B (embed)  : 结构化数据 -> 维度化文本 -> 通义 embedding -> talent-pool.json

用法:
  python3 ingest.py parse   # 只做抽取(增量,已抽过的跳过)
  python3 ingest.py embed   # 只做向量化
  python3 ingest.py all     # 两阶段都做

设计要点:
  - 每抽完一份立即落盘(防进程挂死丢进度)
  - urlopen 设短超时, 失败快速跳过, 不长时间挂起
  - 维度化文本: 按 教育/经历/技能/行业 分段 -> 检索结果可拆维度解释
  - 输出实时 flush, 便于观察进度
"""
import os, sys, json, glob, time, socket
import urllib.request

socket.setdefaulttimeout(90)  # 全局 socket 超时, 防 urlopen 永久挂起

WORKSPACE = os.path.expanduser("~/.openclaw-hr/workspace-recruitment")
INBOX = os.path.join(WORKSPACE, "inbox")
POOL_DIR = os.path.join(WORKSPACE, "talent-pool")
RANKING = os.path.join(WORKSPACE, "scoring/results/ranking-后端开发.json")
PARSED_ALL = os.path.join(POOL_DIR, "parsed-all.json")
OUT = os.path.join(POOL_DIR, "talent-pool.json")

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
EMBED_API_KEY = (
    os.environ.get("SILICONFLOW_API_KEY")
    or os.environ.get("SF_API_KEY")
    or ""
)
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
EMBED_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

def log(*a):
    print(*a, flush=True)

def post_json(url, payload, headers, timeout=90):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

# ---------- 阶段 A: parse ----------
# prompt 含 JSON schema, 不用 str.format() (会把花括号当占位符报 KeyError)
PARSE_PROMPT_HEAD = """你是简历结构化抽取器。把下面这份中文简历抽成 JSON,字段如下:
name, target_position, expected_salary, expected_city, available_date,
education(对象,含 school / major / degree / graduation_year 四个键),
work_experience(数组,每项含 company / position / start_date / end_date / industry),
total_experience_years (整数), job_count (整数),
skills (数组,技能名列表),
self_evaluation (自我评价/个人优势文字, 没有则空字符串)

要求: 所有字段值严格从简历原文提取, 没有的字段留空字符串或空列表, 绝对不要编造。
industry 可从公司名/业务描述合理推断。只输出 JSON, 不要任何解释。

简历原文:
---
"""

def parse_resume_llm(resume_text):
    prompt = PARSE_PROMPT_HEAD + resume_text + "\n---"
    payload = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    r = post_json("https://api.deepseek.com/chat/completions", payload, headers, timeout=90)
    return json.loads(r["choices"][0]["message"]["content"])

def load_tech_parsed():
    out = {}
    if not os.path.exists(RANKING):
        return out
    d = json.load(open(RANKING))
    for det in d.get("details", []):
        p = det.get("parsed", {})
        rf = p.get("_resume_file", "")
        if rf:
            out[rf] = p
    return out

def stage_parse():
    os.makedirs(POOL_DIR, exist_ok=True)
    resume_files = sorted(glob.glob(os.path.join(INBOX, "resume-*.md")))
    log(f"[parse] 发现 {len(resume_files)} 份简历")

    # 断点续跑: 加载已抽好的
    parsed_all = {}
    if os.path.exists(PARSED_ALL):
        parsed_all = json.load(open(PARSED_ALL, encoding="utf-8"))
        log(f"[parse] 已有抽取进度: {len(parsed_all)} 份")

    tech_cache = load_tech_parsed()
    log(f"[parse] C-2 复用 tech: {len(tech_cache)} 份")

    for i, rf in enumerate(resume_files, 1):
        base = os.path.basename(rf)
        if base in parsed_all:
            log(f"  [{i}/{len(resume_files)}] {base} 已抽取,跳过")
            continue
        if base in tech_cache:
            parsed_all[base] = tech_cache[base]
            log(f"  [{i}/{len(resume_files)}] {base} <- C-2 复用")
        else:
            resume_text = open(rf, encoding="utf-8").read()
            ok = False
            for attempt in range(3):
                try:
                    t0 = time.time()
                    parsed_all[base] = parse_resume_llm(resume_text)
                    log(f"  [{i}/{len(resume_files)}] {base} <- DeepSeek 抽取 ({time.time()-t0:.1f}s)")
                    ok = True
                    break
                except Exception as e:
                    log(f"    [{base}] 抽取重试 {attempt+1}: {type(e).__name__} {e}")
                    time.sleep(2)
            if not ok:
                log(f"  [{i}/{len(resume_files)}] {base} 抽取失败,跳过")
                continue
        # 每份立即落盘
        json.dump(parsed_all, open(PARSED_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    log(f"[parse] 完成,共 {len(parsed_all)} 份结构化数据 -> {PARSED_ALL}")
    return parsed_all

# ---------- 阶段 B: 维度化文本 + embedding ----------
def build_dim_texts(p):
    edu = p.get("education", {}) or {}
    edu_text = f"{edu.get('school','')} {edu.get('major','')} {edu.get('degree','')} {edu.get('graduation_year','')}".strip()
    works = p.get("work_experience", []) or []
    exp_parts, industries = [], []
    for w in works:
        exp_parts.append(f"{w.get('company','')} {w.get('position','')} {w.get('start_date','')}-{w.get('end_date','')}")
        if w.get("industry"):
            industries.append(w["industry"])
    return {
        "education": edu_text,
        "experience": " | ".join(exp_parts),
        "industry": " ".join(dict.fromkeys(industries)),
        "skills": " ".join(p.get("skills", []) or []),
        "summary": f"{p.get('target_position','')} 工作年限{p.get('total_experience_years','')}年 {p.get('self_evaluation','') or ''}".strip(),
    }

def build_full_text(dims, p):
    return (f"姓名:{p.get('name','')}; 目标岗位:{p.get('target_position','')}; "
            f"教育:{dims['education']}; 工作经历:{dims['experience']}; "
            f"行业:{dims['industry']}; 技能:{dims['skills']}; "
            f"自我评价:{p.get('self_evaluation','') or ''}")

EMBED_BASE = os.environ.get(
    "EMBEDDING_BASE_URL",
    "https://api.siliconflow.cn/v1",
)

def embed(texts):
    payload = {"model": EMBED_MODEL, "input": texts}
    headers = {"Authorization": f"Bearer {EMBED_API_KEY}", "Content-Type": "application/json"}
    url = f"{EMBED_BASE.rstrip('/')}/embeddings"
    r = post_json(url, payload, headers, timeout=60)
    embs = sorted(r["data"], key=lambda x: x.get("index", 0))
    return [e["embedding"] for e in embs]

def batch_embed(texts):
    out = []
    for j in range(0, len(texts), 10):
        for attempt in range(3):
            try:
                out.extend(embed(texts[j:j+10]))
                break
            except Exception as e:
                log(f"    embedding 批 {j} 重试 {attempt+1}: {e}")
                time.sleep(2)
        else:
            raise RuntimeError(f"embedding 批 {j} 失败")
        time.sleep(0.4)
    return out

def stage_embed():
    parsed_all = json.load(open(PARSED_ALL, encoding="utf-8"))
    log(f"[embed] 加载 {len(parsed_all)} 份结构化数据")
    records = []
    for base, parsed in sorted(parsed_all.items()):
        category = base.split("-")[1]
        dims = build_dim_texts(parsed)
        records.append({
            "id": base.replace(".md", ""),
            "resume_file": base,
            "category": category,
            "name": parsed.get("name", ""),
            "parsed": parsed,
            "dim_texts": dims,
            "full_text": build_full_text(dims, parsed),
        })

    log(f"[embed] 向量化 {len(records)} 名候选人(整份)...")
    for r, v in zip(records, batch_embed([r["full_text"] for r in records])):
        r["vector"] = v
    for dim in ["education", "experience", "skills", "industry"]:
        log(f"[embed] 向量化维度: {dim}")
        vecs = batch_embed([r["dim_texts"][dim] or "无" for r in records])
        for r, v in zip(records, vecs):
            r.setdefault("dim_vectors", {})[dim] = v

    pool = {
        "embedding_model": EMBED_MODEL,
        "dimension": EMBED_DIM,
        "candidate_count": len(records),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "candidates": records,
    }
    json.dump(pool, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    cats = {}
    for r in records:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    log(f"[embed] 人才库已落盘: {OUT}")
    log(f"[embed] {len(records)} 名候选人, 每人 1 整体向量 + 4 维度向量, 维度 1024")
    log(f"[embed] 分类: {', '.join(f'{k}={v}' for k,v in sorted(cats.items()))}")

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("parse", "all"):
        stage_parse()
    if stage in ("embed", "all"):
        stage_embed()
