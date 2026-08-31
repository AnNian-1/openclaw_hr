#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招聘子 Agent · 手写简历评分 Pipeline（含合规过滤层）
================================================================
openclaw-ai-hr 阶段 C 任务 2 · 简历评分排序

设计原则：评分必须可解释、可审计、合规、真实。
Pipeline 四阶段，合规过滤层与数字回核层都是独立的一层、不可绕过：

  阶段 1  parse          简历原文(md) --DeepSeek--> 结构化候选人 JSON
  阶段 2  compliance     结构化 JSON --剥离敏感字段--> 评分输入（脱敏）
  阶段 3  score          评分输入 --DeepSeek 8 维度评分--> 评分结果
  阶段 4  number_audit   评分产出 --数字回核--> 修正虚构数字后的评分结果

数字回核层（阶段 4）解决的问题：阶段 3 用 LLM 生成 highlights 等
自由文本字段时，LLM 会在"复述"候选人简历时把数字改写/串台。实测——
员工1原简历写"大促峰值 12.8 万 TPS"，评分 highlights 复述成了
"双十一峰值 58 万笔/秒"。回核以候选人原简历为唯一基准，把对不上的
虚构数字修正为真实值。详见 number_audit.py。

合规红线（candidate-profile-schema.md §9）：
  禁止作为评分依据的字段——年龄/出生日期、性别、婚育、户籍/籍贯、
  民族、院校排名、健康状况。
  本 Pipeline 怎么保证没用这些特征：
  阶段 2 在数据进入评分 LLM 之前，物理删除这些字段。评分 LLM 收到的
  prompt 里根本不存在敏感信息——不是"求 LLM 别用"，是"让它根本看不到"。
  阶段 3 的 prompt 再加一道声明作为兜底防线。
"""
import json
import os
import re
import sys
import time
import urllib.request

from number_audit import audit_candidate


def resolve_llm():
    model = os.environ.get("LLM_MODEL") or "mimo-v2.5-pro"
    is_mimo = "mimo" in model or "xiaomi" in (os.environ.get("LLM_BASE_URL") or "")
    base = os.environ.get("LLM_BASE_URL") or (
        "https://token-plan-cn.xiaomimimo.com/v1" if is_mimo else "https://api.deepseek.com/v1"
    )
    url = base.rstrip("/") + "/chat/completions"
    key = (
        os.environ.get("LLM_API_KEY")
        or (os.environ.get("XIAOMI_API_KEY") if is_mimo or "xiaomi" in base else "")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    )
    return model, url, key

# ── 合规红线：禁止进入评分的敏感字段（§9） ────────────────────────
# 顶层字段名（结构化数据里出现这些 key 直接删）
SENSITIVE_TOP_KEYS = {
    "age", "birth_date", "birth_year", "出生年月", "年龄",
    "gender", "性别",
    "marital_status", "marriage", "婚育", "婚姻状况",
    "hometown", "household", "domicile", "籍贯", "户籍", "出生地",
    "ethnicity", "民族",
    "school_tier", "院校层次", "院校排名",
    "health", "健康状况", "政治面貌", "political_status",
}
# 教育背景子字段里也要剥的
SENSITIVE_EDU_KEYS = {"school_tier", "院校层次", "院校排名"}


def call_deepseek(system_prompt, user_prompt, max_tokens=2000,
                  temperature=0.2, json_mode=False, retries=3):
    """调对话模型。json_mode=True 时强制 JSON。"""
    model, api_url, api_key = resolve_llm()
    if not api_key:
        raise RuntimeError("未设置 XIAOMI_API_KEY / LLM_API_KEY")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                api_url, data=data,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
        except Exception as e:  # IncompleteRead / timeout / 5xx
            last_err = e
            if attempt < retries:
                time.sleep(3 * attempt)
    raise RuntimeError(f"LLM 调用 {retries} 次均失败：{last_err}")


def extract_json(text):
    """从 LLM 回复里抽出 JSON，容忍 ```json 包裹 + LLM 常见的尾逗号瑕疵。"""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"(\{.*\})", text, re.S)
        if m:
            text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 容错：去掉对象/数组结尾多余的逗号（LLM 高频瑕疵）
        fixed = re.sub(r",(\s*[}\]])", r"\1", text)
        return json.loads(fixed)


def call_and_parse(system_prompt, user_prompt, max_tokens=2500,
                   temperature=0.2, parse_retries=3):
    """调 LLM 并解析 JSON。解析失败（LLM 漏逗号等正则补不了的瑕疵）时
    重新调用 LLM 生成——比硬修字符串可靠。"""
    last_err = None
    for attempt in range(1, parse_retries + 1):
        raw = call_deepseek(system_prompt, user_prompt,
                            max_tokens=max_tokens, temperature=temperature,
                            json_mode=True)
        try:
            return extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"LLM 返回 JSON {parse_retries} 次均无法解析：{last_err}")


# ══ 阶段 1 · 解析 ══════════════════════════════════════════════
def stage1_parse(resume_md, resume_name):
    """简历原文 → 结构化候选人 JSON。"""
    sys_p = ("你是招聘助理，把简历原文抽取成结构化 JSON——这是候选人画像，"
             "用于展示与归档。所有字段值必须严格从原文提取，原文没有的留空字符串，"
             "绝对不要编造。")
    user_p = f"""把下面这份简历抽取成结构化 JSON。字段：
- name 姓名
- target_position 求职意向岗位
- expected_salary 期望薪资
- expected_city 期望城市
- available_date 到岗时间
- education: {{school 学校, major 专业, degree 学历, graduation_year 毕业年份, school_tier 院校层次(985/211/双非本科/大专/海外)}}
- work_experience: [{{company, position, start_date, end_date, industry}}]
- total_experience_years 总工作年限(数字)
- job_count 工作段数
- skills [技能数组]
- self_evaluation 自我评价原文
（以下字段画像需要记录、原文若有就抽出来，仅用于展示统计，后续评分会剥离）
- 出生年月 原文写的出生年月/年龄，没有留空
- 性别 原文写的性别，没有留空
- 政治面貌 原文写的政治面貌，没有留空
- 婚育 原文写的婚育/婚姻状况，没有留空

简历原文：
---
{resume_md}
---
只输出 JSON，不要解释。"""
    parsed = call_and_parse(sys_p, user_p, max_tokens=2500)
    parsed["_resume_file"] = resume_name
    return parsed


# ══ 阶段 2 · 合规过滤层（关键 · 独立一层 · 不可绕过） ═══════════════
def stage2_compliance_filter(candidate):
    """
    从结构化候选人数据里物理删除 §9 敏感字段。
    返回 (脱敏后的评分输入, 被剥离的字段清单)。
    评分 LLM 只会拿到这个返回值的第一项——敏感信息根本不进 prompt。
    """
    stripped = []
    clean = {}
    for k, v in candidate.items():
        if k in SENSITIVE_TOP_KEYS:
            stripped.append(f"{k}={v}")
            continue
        clean[k] = v
    # 教育背景里也清一遍
    edu = clean.get("education")
    if isinstance(edu, dict):
        clean_edu = {}
        for k, v in edu.items():
            if k in SENSITIVE_EDU_KEYS:
                stripped.append(f"education.{k}={v}")
                continue
            clean_edu[k] = v
        clean["education"] = clean_edu
    return clean, stripped


# ══ 阶段 3 · 8 维度评分 ════════════════════════════════════════
DIMENSIONS = ["专业技能", "经验匹配", "沟通能力", "逻辑能力",
              "学习力", "抗压能力", "价值观", "协作能力"]


def stage3_score(clean_candidate, jd_text, jd_name):
    """脱敏候选人 + JD → 8 维度评分结果。"""
    sys_p = (
        "你是资深招聘评估专家，对候选人做简历初筛阶段的结构化评分。\n"
        "【合规红线 · 强制】禁止使用以下任何因素影响评分：年龄、出生日期、"
        "性别、婚育状况、户籍/籍贯/出生地、民族、院校排名/院校层次、健康状况。"
        "评分只能基于：岗位相关技能、工作经历与岗位的匹配度、项目经验、"
        "简历表述质量。如发现简历里有这些敏感信息也必须忽略。\n"
        "【可解释 · 强制】每个维度分必须给出依据，综合评分必须写清楚理由——"
        "这是个保法第 24 条的合规要求，候选人有权要求说明为什么是这个分。\n"
        "【边界 · 强制】你只产出评分与排序建议，不做录用/淘汰决定。"
        "评级里不要出现'淘汰''拒绝'等词，最终决定由人工 HR 做。"
    )
    user_p = f"""目标岗位 JD（{jd_name}）：
---
{jd_text}
---

候选人结构化数据（已做合规脱敏，敏感字段已剥离）：
---
{json.dumps(clean_candidate, ensure_ascii=False, indent=2)}
---

请按以下 8 个维度评分，每维度 1-5 分（5 最高）：
{chr(10).join(f"- {d}" for d in DIMENSIONS)}

输出 JSON：
{{
  "candidate_name": "姓名",
  "dimension_scores": {{"专业技能": 分, "经验匹配": 分, ...8 个维度...}},
  "dimension_reasons": {{"专业技能": "给这个分的依据", ...8 个维度...}},
  "jd_match_score": 0-100 综合匹配分,
  "overall_rating": "A(强烈推荐)/B(推荐)/C(待定)/D(不匹配) 之一",
  "score_reasoning": "综合评分理由，说清为什么是这个分，2-4 句",
  "highlights": ["亮点1", "亮点2", "亮点3"],
  "concerns": ["顾虑1", "顾虑2"],
  "hard_issues": ["硬伤；没有则空数组"]
}}

【concerns 与 hard_issues 的区别 · 必须严格区分】
- concerns（顾虑）：岗位匹配度相关的担忧。例如期望薪资超岗位带宽、
  期望城市与岗位不符、经验方向不对口、overqualified。这些放 concerns。
- hard_issues（硬伤）：简历本身的真实性/可信度问题。只有以下三类算硬伤：
  ① 工作经历时间矛盾（两段全职经历时间区间重叠）
  ② 学历存疑（学历与岗位硬性门槛不符，或学历信息自相矛盾）
  ③ 简历内容自相矛盾（如工作年限与经历明显对不上）
  薪资高、城市不符、岗位不匹配【不是硬伤】，不要放进 hard_issues。
只输出 JSON。"""
    return call_and_parse(sys_p, user_p, max_tokens=2500, temperature=0.2)


# ══ 阶段 4 · 数字回核（关键 · 独立一层 · 不可绕过） ═══════════════
def _replace_in(text, token, real_value, bad_span, good_span):
    """把一段文本里的虚构数字改成真实值。
    优先策略：用 LLM 给的【最小替换对】bad_span→good_span 精确替换——
    bad_span 只圈住虚构数字+错误单位，good_span 是通顺替换文本。
    替换范围最小，旧单位随虚构数字一起换掉，不残留、不重复词。
    回退策略：bad_span 在文本里逐字对不上时，退化为 token 级替换。"""
    if bad_span and good_span and bad_span in text:
        return text.replace(bad_span, good_span)
    if token and real_value and token in text:
        return text.replace(token, real_value)
    return text


def _apply_fix(score, loc, token, real_value, bad_span="", good_span=""):
    """把评分产出里某个字段的虚构数字替换成原简历真实值。
    loc 形如 'highlights[0]' / 'score_reasoning' / 'dimension_reasons.专业技能'。
    修正后的文本必须通顺可用——优先用 bad_span→good_span 最小替换对。"""
    if not real_value and not good_span:
        return False
    m = re.match(r"(\w+)\[(\d+)\]$", loc)
    if m:  # 列表字段，如 highlights[0]
        field, idx = m.group(1), int(m.group(2))
        lst = score.get(field)
        if isinstance(lst, list) and 0 <= idx < len(lst):
            new = _replace_in(lst[idx], token, real_value,
                              bad_span, good_span)
            changed = new != lst[idx]
            lst[idx] = new
            return changed
    elif loc.startswith("dimension_reasons."):
        dim = loc.split(".", 1)[1]
        dr = score.get("dimension_reasons", {})
        if dim in dr:
            new = _replace_in(dr[dim], token, real_value,
                              bad_span, good_span)
            changed = new != dr[dim]
            dr[dim] = new
            return changed
    elif loc in score and isinstance(score[loc], str):
        new = _replace_in(score[loc], token, real_value,
                          bad_span, good_span)
        changed = new != score[loc]
        score[loc] = new
        return changed
    return False


def _field_text(score, loc):
    """按 loc 取出评分产出里某个字段的当前文本，用于留存修正前后快照。"""
    m = re.match(r"(\w+)\[(\d+)\]$", loc)
    if m:
        lst = score.get(m.group(1))
        idx = int(m.group(2))
        if isinstance(lst, list) and 0 <= idx < len(lst):
            return lst[idx]
    elif loc.startswith("dimension_reasons."):
        return score.get("dimension_reasons", {}).get(loc.split(".", 1)[1], "")
    elif loc in score and isinstance(score[loc], str):
        return score[loc]
    return ""


def stage4_number_audit(score, resume_md, candidate_name, verbose=True):
    """数字回核：评分产出里引用候选人简历的数字，必须能在原简历找到。
    对不上的判为虚构，修正为原简历真实值。
    返回 (修正后的 score, 回核报告)。原简历是唯一回核基准——不用 JD。
    回核报告留存每处修正的『修正前/修正后』文本，供审计追溯。"""
    audit = audit_candidate(candidate_name, resume_md, score, verbose=verbose)
    fabricated = [v for v in audit.get("verdicts", [])
                  if v.get("verdict") == "fabricated"]
    fixes = []
    for v in fabricated:
        loc = v.get("loc", "")
        before = _field_text(score, loc)  # 修正前快照（审计证据）
        ok = _apply_fix(score, loc, v.get("token", ""),
                        v.get("real_value", ""), v.get("bad_span", ""),
                        v.get("good_span", ""))
        after = _field_text(score, loc)  # 修正后文本
        fixes.append({
            "loc": loc, "fabricated": v.get("token"),
            "real_value": v.get("real_value"),
            "bad_span": v.get("bad_span"),
            "good_span": v.get("good_span"),
            "reason": v.get("reason"),
            "applied": ok,
            "text_before": before,  # 含虚构数字的原文（审计留痕）
            "text_after": after,    # 修正后文本
        })
        if verbose:
            mark = "已修正" if ok else "需人工"
            print(f"  ✗ 数字虚构【{mark}】{v.get('loc')}："
                  f"产出「{v.get('token')}」→ 原简历「{v.get('real_value')}」",
                  flush=True)
    if verbose and not fabricated:
        print("  ✓ 数字回核通过：评分产出未发现虚构数字", flush=True)
    report = {
        "total_numbers": audit.get("total_numbers", 0),
        "suspects": len(audit.get("suspects", [])),
        "fabricated": len(fabricated),
        "fixes": fixes,
    }
    return score, report


# ══ 主流程：单份候选人完整 Pipeline ══════════════════════════════
def run_pipeline(resume_path, jd_text, jd_name, verbose=True):
    resume_name = os.path.basename(resume_path)
    with open(resume_path, encoding="utf-8") as f:
        resume_md = f.read()

    if verbose:
        print(f"\n{'='*60}\n候选人简历：{resume_name}\n{'='*60}")

    # 阶段 1
    if verbose:
        print("[阶段 1/3] 解析 → 结构化数据 ...", flush=True)
    candidate = stage1_parse(resume_md, resume_name)

    # 阶段 2 · 合规过滤层
    if verbose:
        print("[阶段 2/3] 合规过滤层 → 剥离敏感字段 ...", flush=True)
    clean, stripped = stage2_compliance_filter(candidate)
    if verbose:
        if stripped:
            print(f"  ⚠ 已剥离 {len(stripped)} 个敏感字段（不进评分）：")
            for s in stripped:
                print(f"     - {s}")
        else:
            print("  结构化数据中未出现敏感字段")
        # 自检：评分输入里绝不能再有敏感 key
        leak = [k for k in clean if k in SENSITIVE_TOP_KEYS]
        print(f"  合规自检：评分输入剩余敏感字段 = {len(leak)} 个"
              f" {'✓ 通过' if not leak else '✗ 未通过 ' + str(leak)}")

    # 阶段 3 · 评分
    if verbose:
        print("[阶段 3/4] 8 维度评分 ...", flush=True)
    score = stage3_score(clean, jd_text, jd_name)

    # 阶段 4 · 数字回核（以原简历为唯一基准，修正 LLM 复述时虚构的数字）
    if verbose:
        print("[阶段 4/4] 数字回核 → 校验评分产出引用的简历数字 ...",
              flush=True)
    cand_name = score.get("candidate_name", candidate.get("name", resume_name))
    score, audit_report = stage4_number_audit(
        score, resume_md, cand_name, verbose=verbose)

    return {
        "resume_file": resume_name,
        "parsed": candidate,
        "compliance_stripped": stripped,
        "score": score,
        "number_audit": audit_report,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：score_pipeline.py <简历md路径> <JD-md路径> [输出json路径]")
        sys.exit(1)
    resume_path, jd_path = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else None
    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()
    jd_name = os.path.basename(jd_path)
    result = run_pipeline(resume_path, jd_text, jd_name)
    s = result["score"]
    na = result.get("number_audit", {})
    print(f"\n--- 评分结果 ---")
    print(f"综合匹配分：{s['jd_match_score']}  评级：{s['overall_rating']}（建议）")
    print(f"维度分：{s['dimension_scores']}")
    print(f"理由：{s['score_reasoning']}")
    if s.get("hard_issues"):
        print(f"⚠ 硬伤：{s['hard_issues']}")
    print(f"数字回核：提取 {na.get('total_numbers',0)} 个数字，"
          f"虚构 {na.get('fabricated',0)} 处"
          f"{'（已修正）' if na.get('fabricated') else ''}")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n已保存：{out_path}")
