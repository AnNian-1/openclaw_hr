#!/usr/bin/env python3
"""
gen_minutes.py — 转写稿 -> 结构化面试纪要 + 数字回核

generating-minutes Skill 的核心脚本。把 transcribing-interviews 产出的
"按发言人标注的转写稿"，交大模型整理成结构化面试纪要，并对候选人口述
数字做回核。这是面试纪要链路的第二段（也是最后一段）。

做三件事：
  1. 按说话人重组转写稿：合并连续的同说话人片段，得到对话稿。
  2. 调大模型生成结构化纪要：关键问答 / 优势 / 待考察点 / 高亮时刻 /
     评分建议 / 候选人口述数字（mentioned_numbers）。
  3. 数字回核：把纪要里候选人口述的数字逐项对照原简历核对。
     大模型只负责"提取"口述数字，真伪交给这段确定性脚本对照原简历判定。

为什么要数字回核：大模型生成自由文本时会把数字记错或张冠李戴。纪要里
引用候选人提到的项目数据（TPS、降幅、规模），必须能在原简历追溯，不能
虚构。这一步把"数字真不真"从大模型手里收回到脚本里。

转写稿里的说话人标签是 speaker_A / speaker_B / speaker_C…（CAM++ 凝聚聚类
不知道谁是面试官、谁是候选人，只知道录音里有 N 个人）。本脚本接受
--interviewer 指定哪个标签是面试官，默认 speaker_A 是面试官——按面试录音里
通常面试官先开口的惯例。

CLI：
  python3 gen_minutes.py <transcript.json> <resume.md> <out.json> <out.md> \\
      [--candidate 姓名] [--position 岗位] [--round 轮次] \\
      [--interviewer speaker_A]
退出码：0 = 纪要生成成功；1 = 大模型调用失败；2 = 用法/文件错误。

依赖环境变量 XIAOMI_API_KEY（或 LLM_API_KEY）。默认模型 mimo-v2.5-pro。
"""
import sys
import os
import json
import re
import time
import urllib.request

LLM_RETRIES = 3
# 数字回核里"中文数字 / 通用约数"无法用阿拉伯数字匹配，回核结果会标
# "无数字"——这是回核脚本的已知局限，不是 bug。


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


def die(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args(argv):
    if len(argv) < 5:
        die("用法: gen_minutes.py <transcript.json> <resume.md> "
            "<out.json> <out.md> [--candidate 姓名] [--position 岗位] "
            "[--round 轮次] [--interviewer speaker_A]")
    transcript, resume, out_json, out_md = argv[1:5]
    opts = {"candidate": "", "position": "", "round": "",
            "interviewer": "speaker_A"}
    rest = argv[5:]
    i = 0
    while i < len(rest):
        key = rest[i].lstrip("-")
        if key in opts and i + 1 < len(rest):
            opts[key] = rest[i + 1]
            i += 2
        else:
            die(f"未知参数: {rest[i]}")
    for path, label in [(transcript, "转写稿"), (resume, "简历")]:
        if not os.path.isfile(path):
            die(f"{label}文件不存在: {path}")
    if opts["interviewer"] not in ("speaker_A", "speaker_B"):
        die(f"--interviewer 只能是 speaker_A 或 speaker_B，收到: {opts['interviewer']}")
    return transcript, resume, out_json, out_md, opts


def call_deepseek(system, user, max_tokens=3500, temperature=0.2):
    model, api_url, api_key = resolve_llm()
    if not api_key:
        die("未设置 XIAOMI_API_KEY / LLM_API_KEY", 2)
    payload = {"model": model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "max_tokens": max_tokens, "temperature": temperature,
               "response_format": {"type": "json_object"}}
    data = json.dumps(payload).encode("utf-8")
    last = None
    for i in range(1, LLM_RETRIES + 1):
        try:
            req = urllib.request.Request(
                api_url, data=data,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                body = json.loads(r.read().decode())
                return body["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            if i < LLM_RETRIES:
                time.sleep(3 * i)
    # 多次重试仍失败：显式报错退出码 1，绝不返回空纪要冒充成功
    die(f"LLM 调用失败（{LLM_RETRIES} 次重试均失败）: {last}", 1)


def norm_num(s):
    """抽取字符串里的阿拉伯数字 token，用于回核匹配。"""
    return set(re.findall(r"\d+(?:\.\d+)?", s))


def main():
    transcript, resume, out_json, out_md, opts = parse_args(sys.argv)

    # ── 1. 读输入 + 按说话人重组转写稿 ──────────────────────
    try:
        tr = json.load(open(transcript, encoding="utf-8"))
    except Exception as e:
        die(f"转写稿 JSON 无法解析: {e}", 2)
    if not tr.get("segments"):
        die("转写稿 segments 为空——无法生成纪要", 2)
    resume_text = open(resume, encoding="utf-8").read()

    interviewer_tag = opts["interviewer"]

    def role_of(spk):
        if spk == interviewer_tag:
            return "面试官"
        if spk in ("speaker_A", "speaker_B"):
            return "候选人"
        return "未知发言人"

    dialog_lines = []
    cur_role, cur_txt = None, ""
    for s in tr["segments"]:
        role = role_of(s.get("speaker", ""))
        if role != cur_role:
            if cur_role:
                dialog_lines.append(f"{cur_role}: {cur_txt.strip()}")
            cur_role, cur_txt = role, s["text"]
        else:
            cur_txt += s["text"]
    if cur_role:
        dialog_lines.append(f"{cur_role}: {cur_txt.strip()}")
    transcript_by_speaker = "\n".join(dialog_lines)

    # ── 2. 大模型生成结构化纪要 ──────────────────────────────
    SYS = """你是资深技术招聘官，负责把一段技术面试的转写稿整理成结构化面试纪要。
要求：
1. 按"面试官提问 / 候选人回答"组织关键问答，提炼要点，不照抄原文。
2. 给出候选人的优势(strengths)和待考察点(concerns)。
3. 给出评分建议(recommendation)：通过/待定/不通过 之一 + 一句理由。
4. 标出高亮时刻(highlights)：面试中最能体现候选人能力的 2-3 个片段。
5. 数字回核：候选人在面试中口述的所有项目数字(如 TPS、降幅、规模)，
   提取到 mentioned_numbers 字段，每项含 {claim: 原话数字, context: 什么场景}。
   你不要判断真假，只负责提取——真伪由外部脚本对照简历核对。
6. 转写稿可能有 ASR 误识的人名/术语错字，依据上下文纠正回正确写法。
严格输出 JSON，字段：
{
  "candidate": "候选人姓名",
  "position": "面试岗位",
  "interview_round": "面试轮次",
  "qa": [{"topic":"主题","question":"面试官问题要点","answer":"候选人回答要点"}],
  "strengths": ["..."],
  "concerns": ["..."],
  "highlights": ["..."],
  "mentioned_numbers": [{"claim":"...","context":"..."}],
  "recommendation": {"verdict":"通过/待定/不通过","reason":"..."}
}"""

    meta_hint = []
    if opts["candidate"]:
        meta_hint.append(f"候选人是{opts['candidate']}")
    if opts["position"]:
        meta_hint.append(f"岗位{opts['position']}")
    if opts["round"]:
        meta_hint.append(f"本场为{opts['round']}")
    meta_line = ("。".join(meta_hint) + "。") if meta_hint else ""

    USER = f"""【面试转写稿（已按说话人分离）】
{transcript_by_speaker}

请整理成结构化面试纪要。{meta_line}"""

    MODEL, _, _ = resolve_llm()
    print(f"[1/3] 调 {MODEL} 生成结构化纪要...", flush=True)
    raw = call_deepseek(SYS, USER)
    try:
        minutes = json.loads(raw)
    except Exception as e:
        die(f"大模型返回的不是合法 JSON: {e}", 1)

    # ── 3. 数字回核：纪要里的数字能否在原简历追溯 ────────────
    print("[2/3] 数字回核：对照原简历核对候选人口述数字...", flush=True)
    resume_nums = norm_num(resume_text)
    audited = []
    for item in minutes.get("mentioned_numbers", []):
        claim = item.get("claim", "")
        nums = norm_num(claim)
        traceable = bool(nums) and nums.issubset(resume_nums)
        audited.append({
            **item, "numbers": sorted(nums), "traceable": traceable,
            "audit": ("可追溯到原简历" if traceable
                      else ("无阿拉伯数字（中文数字表述，回核脚本未覆盖）"
                            if not nums
                            else "简历中未找到，需人工核实"))})
    minutes["mentioned_numbers"] = audited
    n_trace = sum(1 for a in audited if a["traceable"])
    minutes["number_audit_summary"] = {
        "total": len(audited), "traceable": n_trace,
        "needs_review": len(audited) - n_trace}
    minutes["_source"] = {
        "transcript": os.path.abspath(transcript),
        "resume": os.path.abspath(resume),
        "asr": tr.get("model", "funasr-paraformer"),
        "llm": MODEL}

    try:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(minutes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        die(f"纪要 JSON 写入失败: {e}", 2)

    # ── 4. 渲染 Markdown 纪要 ────────────────────────────────
    print("[3/3] 渲染 Markdown 纪要...", flush=True)
    m = minutes
    md = [f"# 面试纪要 · {m.get('candidate', '候选人')}",
          "",
          f"- **应聘岗位**：{m.get('position', '')}",
          f"- **面试轮次**：{m.get('interview_round', '')}",
          f"- **生成方式**：录音 → FunASR Paraformer-zh 转写 + CAM++ 说话人分离 → {MODEL} 整理",
          "",
          "## 关键问答（按发言人组织）", ""]
    for i, qa in enumerate(m.get("qa", []), 1):
        md += [f"**{i}. {qa.get('topic', '')}**",
               f"- 面试官：{qa.get('question', '')}",
               f"- 候选人：{qa.get('answer', '')}", ""]
    md += ["## 候选人优势", ""]
    md += [f"- {x}" for x in m.get("strengths", [])]
    md += ["", "## 待考察点", ""]
    md += [f"- {x}" for x in m.get("concerns", [])]
    md += ["", "## 高亮时刻", ""]
    md += [f"- {x}" for x in m.get("highlights", [])]
    sm = m["number_audit_summary"]
    md += ["", "## 数字回核", "",
           f"候选人口述数字共 {sm['total']} 项，可追溯 {sm['traceable']} 项，"
           f"需人工核实 {sm['needs_review']} 项。", "",
           "| 候选人口述 | 场景 | 回核结果 |", "|---|---|---|"]
    for a in m["mentioned_numbers"]:
        md.append(f"| {a.get('claim', '')} | {a.get('context', '')} "
                  f"| {a['audit']} |")
    rec = m.get("recommendation", {})
    md += ["", "## 评分建议", "",
           f"**{rec.get('verdict', '')}** — {rec.get('reason', '')}", "",
           "> 合规说明：AI 仅提供评分建议，是否进入下一轮由人工面试官决定"
           "（个保法 24 条 · HiTL）。"]
    try:
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
    except Exception as e:
        die(f"纪要 Markdown 写入失败: {e}", 2)

    print("完成:")
    print(f"  纪要 JSON: {out_json}")
    print(f"  纪要 MD  : {out_md}")
    print(f"  问答 {len(m.get('qa', []))} 组  优势 {len(m.get('strengths', []))}  "
          f"待考察 {len(m.get('concerns', []))}")
    print(f"  数字回核: {sm['traceable']}/{sm['total']} 可追溯")
    sys.exit(0)


if __name__ == "__main__":
    main()
