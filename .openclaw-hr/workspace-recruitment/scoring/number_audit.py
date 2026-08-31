#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招聘子 Agent · 评分产出「数字回核」机制
================================================================
openclaw-ai-hr 阶段 C 任务 2 修复 · 真实性回核

背景：C-2 评分用 LLM 生成 highlights（亮点摘要）等自由文本字段时，
LLM 会在"复述"候选人简历时把数字改写/串台。实测案例——
员工1原简历写"大促峰值 12.8 万 TPS"，评分 highlights 复述成了
"双十一峰值 58 万笔/秒"。追因发现：58 万笔/秒 这个数字其实出现在
【JD 的岗位职责】里（"去年双十一订单峰值 58 万笔/秒"），LLM 把
JD 的岗位场景数字张冠李戴安到了候选人经历上。这是 LLM 自由文本
生成的典型"上下文串台"风险。

数字回核做什么：评分产出里凡是引用了候选人简历的数字（TPS、金额、
增长率、年限、规模等），必须能在【该候选人的原简历】里找到对应值。
对不上的，判定为虚构，修正为原简历真实值或剔除该表述。

回核基准 = 候选人原简历，且【只能是原简历】。不能拿 JD 当基准——
JD 里的数字看起来"相关"，但它不属于候选人，正是串台的来源。

三步：
  step1  extract   从评分产出里正则提取所有「数字 + 上下文短语」
  step2  verify     每个数字在原简历里 grep / 模糊比对
  step3  adjudicate 简历里找不到的 → LLM 判定是不是真虚构
                    （排除通用表述、JD 场景数字、约数）
  → 真虚构：修正为原简历真实值，或剔除该数字表述
"""
import json
import os
import re
import sys
import time
import urllib.request


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

# 评分产出里需要回核的自由文本字段（LLM 生成、有复述漂移风险）
TEXT_FIELDS = ["highlights", "concerns", "score_reasoning"]
# dimension_reasons 是 dict，单独处理

# 数字模式：捕获 数字 + 紧跟的单位/量词。覆盖 TPS/QPS/万/亿/%/年/人/倍/ms 等
NUM_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*"
    r"(?:万|亿|千|百|个|人|年|月|天|倍|次|"
    r"TPS|QPS|tps|qps|ms|秒|笔/秒|条/秒|%|pp|K|w|元)?"
)


def call_deepseek(system_prompt, user_prompt, max_tokens=1500,
                  temperature=0.0, json_mode=False, retries=3):
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
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(3 * attempt)
    raise RuntimeError(f"LLM 调用 {retries} 次均失败：{last_err}")


def _norm(text):
    """归一化：去空格/换行——简历里数字和单位常被排版换行拆开
    （如 '12.8 万\nTPS'），归一化后才能正确匹配。"""
    return re.sub(r"\s+", "", text or "")


def extract_numbers(text):
    """从一段文本里抽出所有「数字 token」。返回 [(数字token, 该token所在短语)]。"""
    found = []
    for m in NUM_PATTERN.finditer(text):
        token = m.group().strip()
        # 跳过纯标点残留 / 空
        if not re.search(r"\d", token):
            continue
        # 取 token 前后各 12 字做上下文短语，便于人读和 LLM 判定
        s = max(0, m.start() - 12)
        e = min(len(text), m.end() + 12)
        phrase = text[s:e].replace("\n", " ")
        found.append((token, phrase))
    return found


def verify_in_resume(token, resume_norm):
    """数字 token 是否在原简历（已归一化）里出现。
    返回 True=简历里有，False=简历里没有。"""
    token_norm = _norm(token)
    if token_norm in resume_norm:
        return True
    # 数字部分单独再查一次：单位可能简历用 TPS、产出用"笔/秒"，
    # 先看纯数字在不在；纯数字都不在 → 基本确定虚构
    num_only = re.match(r"\d+(?:\.\d+)?", token_norm)
    if num_only and num_only.group() in resume_norm:
        # 纯数字命中，但带的单位/量级不同——可能是改写，标为"数字命中单位存疑"
        return None  # 三态：None = 数字在但需 LLM 看是不是改了量级
    return False


def collect_outputs(score):
    """把评分产出里所有要回核的文本片段收集出来。
    返回 [(字段定位, 文本)]。"""
    items = []
    for f in TEXT_FIELDS:
        v = score.get(f)
        if isinstance(v, list):
            for i, s in enumerate(v):
                items.append((f"{f}[{i}]", s))
        elif isinstance(v, str) and v:
            items.append((f, v))
    dr = score.get("dimension_reasons", {})
    if isinstance(dr, dict):
        for dim, reason in dr.items():
            items.append((f"dimension_reasons.{dim}", reason))
    return items


def audit_candidate(name, resume_md, score, verbose=True):
    """对一个候选人的评分产出做数字回核。
    返回 {suspects:[...], verdicts:[...]}。"""
    resume_norm = _norm(resume_md)
    outputs = collect_outputs(score)

    # step1 + step2：提取数字并在简历里比对
    suspects = []   # 简历里找不到的数字（虚构嫌疑）
    total_nums = 0
    for loc, text in outputs:
        for token, phrase in extract_numbers(text):
            total_nums += 1
            hit = verify_in_resume(token, resume_norm)
            if hit is False:
                suspects.append({"loc": loc, "token": token,
                                  "phrase": phrase, "kind": "简历无此数字"})
            elif hit is None:
                suspects.append({"loc": loc, "token": token,
                                  "phrase": phrase, "kind": "数字在但量级/单位存疑"})

    if verbose:
        print(f"  数字回核 · {name}：产出共提取 {total_nums} 个数字，"
              f"简历比对存疑 {len(suspects)} 个", flush=True)

    if not suspects:
        return {"candidate": name, "total_numbers": total_nums,
                "suspects": [], "verdicts": []}

    # step3：LLM 判定 —— 简历里对不上的，是真虚构还是合理表述
    sys_p = (
        "你是招聘评分的真实性审计员。给你一份候选人的【原简历全文】和一批"
        "从评分产出里抽出的、在简历里找不到的数字。判断每个数字是不是"
        "【虚构】——即评分文字声称这是候选人的经历/能力数据，但原简历里"
        "并没有这个数据。\n"
        "判定规则：\n"
        "1. 评分文字把某个数字当作候选人的经历事实陈述，但简历里查无此数 "
        "→ verdict=fabricated（虚构）。要找出简历里被改写的真实原值。\n"
        "2. 数字属于通用表述、约数、岗位职级代号（如 P6/P7）、年份、"
        "或明显是 JD 岗位要求而非候选人经历 → verdict=ok（不算虚构）。\n"
        "3. 数字是简历真实数据的合理换算（如年限换算）→ verdict=ok。\n"
        "对 fabricated 的，必须给出修正用的【最小替换对】：\n"
        "- real_value：原简历里对应的真实数字【最简原文】，只含数字+单位"
        "（如 '12.8 万 TPS'、'7 年'），不要带括号注释、不要带'简历原文'字样。\n"
        "- bad_span：评分文字里【需要被替换掉的那一小段连续原文】。"
        "它必须是『出现短语』里**逐字出现**的一个子串，且尽量短——"
        "只圈住虚构数字连同它紧跟的错误单位/量词。例如出现短语是"
        "'…双十一峰值58万笔/秒保障经历…'，bad_span 应为 '58万笔/秒'。\n"
        "- good_span：把 bad_span 换成真实值后的【通顺替换文本】。"
        "上面例子里 good_span 应为 '12.8 万 TPS'。\n"
        "  要求：用『good_span 原样替换 bad_span』后，整句必须读起来通顺、"
        "单位正确、不残留旧单位、不重复词语。\n"
        "- fix：一句话修正说明。"
    )
    user_p = f"""候选人「{name}」原简历全文：
---
{resume_md}
---

从该候选人评分产出里抽出的、简历里找不到的数字（逐个判定）：
{json.dumps([{"id": i, "字段": s["loc"], "数字": s["token"],
              "出现短语": s["phrase"]}
             for i, s in enumerate(suspects)], ensure_ascii=False, indent=2)}

逐个判定，输出 JSON：
{{
  "verdicts": [
    {{
      "id": 数字编号,
      "verdict": "fabricated 或 ok",
      "reason": "判定依据，1-2 句",
      "real_value": "若 fabricated，原简历真实数字的最简原文（数字+单位，无注释）；ok 则空",
      "bad_span": "若 fabricated，评分文字里要被替换的最短连续原文子串（含虚构数字+错误单位）；ok 则空",
      "good_span": "若 fabricated，bad_span 替换成真实值后的通顺文本；ok 则空",
      "fix": "若 fabricated，一句话修正说明；ok 则空"
    }}
  ]
}}
只输出 JSON。"""
    raw = call_deepseek(sys_p, user_p, max_tokens=2000, json_mode=True)
    m = re.search(r"\{.*\}", raw, re.S)
    verdicts = json.loads(m.group())["verdicts"] if m else []
    # 把 suspect 原信息并进 verdict
    for v in verdicts:
        sid = v.get("id")
        if isinstance(sid, int) and 0 <= sid < len(suspects):
            v["loc"] = suspects[sid]["loc"]
            v["token"] = suspects[sid]["token"]
            v["phrase"] = suspects[sid]["phrase"]
    return {"candidate": name, "total_numbers": total_nums,
            "suspects": suspects, "verdicts": verdicts}


if __name__ == "__main__":
    # 独立用法：number_audit.py <简历md> <评分结果json>
    if len(sys.argv) < 3:
        print("用法：number_audit.py <简历md路径> <评分结果json路径>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        resume_md = f.read()
    with open(sys.argv[2], encoding="utf-8") as f:
        scored = json.load(f)
    score = scored.get("score", scored)
    name = score.get("candidate_name", "候选人")
    print(f"\n{'='*60}\n数字回核：{name}\n{'='*60}")
    result = audit_candidate(name, resume_md, score)
    fab = [v for v in result["verdicts"] if v.get("verdict") == "fabricated"]
    print(f"\n判定结果：{len(fab)} 处虚构 / 共 {result['total_numbers']} 个数字")
    for v in fab:
        print(f"\n  ✗ 虚构 · 字段 {v['loc']}")
        print(f"     产出写的 : {v['token']}（短语：…{v['phrase']}…）")
        print(f"     原简历真实值 : {v.get('real_value','?')}")
        print(f"     判定依据 : {v.get('reason','')}")
        print(f"     修正建议 : {v.get('fix','')}")
    if not fab:
        print("  ✓ 未发现数字虚构")
