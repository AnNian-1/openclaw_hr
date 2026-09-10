#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADDIE 物料包驱动：每阶段一次 LLM HTTP 调用并落盘，最后打印 RESULT。

不把 8 次长文写进 OpenClaw Agent 会话（会撞 CLI 630s 超时且无结束句）。
已有且足够长的产出默认跳过（断点续跑）；--force 全量重写。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REQUIRED = [
    "01-needs-analysis.md",
    "02-course-design.md",
    "03-ppt-outline.md",
    "04-instructor-manual.md",
    "05-participant-handbook.md",
    "06-assessment.md",
    "07-delivery-guide.md",
    "08-evaluation-form.md",
]
AI_FOOTER = "\n\n---\n> AI 辅助生成、讲师审核后交付\n"
FILE_MARK = re.compile(
    r"===FILE:\s*([0-9]{2}-[a-z0-9-]+\.md)\s*===\s*\n(.*?)(?=\n===FILE:|\Z)",
    re.S,
)
SKILL_DIR = Path(__file__).resolve().parent.parent
WORKSPACE = SKILL_DIR.parent.parent

ONLY_ALIASES = {
    "01": "01-needs-analysis.md",
    "02": "02-course-design.md",
    "03": "03-ppt-outline.md",
    "04": "04-instructor-manual.md",
    "05": "05-participant-handbook.md",
    "06": "06-assessment.md",
    "07": "07-delivery-guide.md",
    "08": "08-evaluation-form.md",
    "学员手册": "05-participant-handbook.md",
    "课后测试题": "06-assessment.md",
    "测试题": "06-assessment.md",
    "讲师手册": "04-instructor-manual.md",
    "ppt": "03-ppt-outline.md",
    "PPT大纲": "03-ppt-outline.md",
    "PPT 大纲": "03-ppt-outline.md",
    "需求分析": "01-needs-analysis.md",
    "课程设计": "02-course-design.md",
    "交付指南": "07-delivery-guide.md",
    "评估反馈表": "08-evaluation-form.md",
    "评估表": "08-evaluation-form.md",
    "反馈表": "08-evaluation-form.md",
}


def parse_only(raw: str) -> set[str]:
    """把 --only 05,06 / 学员手册 解析成文件名集合。"""
    out: set[str] = set()
    for part in re.split(r"[,，、\s]+", (raw or "").strip()):
        if not part:
            continue
        if part in REQUIRED:
            out.add(part)
            continue
        if part in ONLY_ALIASES:
            out.add(ONLY_ALIASES[part])
            continue
        m = re.fullmatch(r"0?([1-8])", part)
        if m:
            out.add(REQUIRED[int(m.group(1)) - 1])
            continue
        print(f"[ERROR] 未知 --only 项: {part}", file=sys.stderr)
        sys.exit(2)
    return out


def stages_for_outputs(wanted: set[str] | None, stages: list[dict]) -> list[dict]:
    if not wanted:
        return stages
    selected = [st for st in stages if wanted & set(st["outputs"])]
    if not selected:
        print(f"[ERROR] --only 未匹配到任何阶段: {wanted}", file=sys.stderr)
        sys.exit(2)
    return selected


def resolve_llm() -> tuple[str, str, str]:
    model = os.environ.get("LLM_MODEL") or "mimo-v2.5-pro"
    is_mimo = "mimo" in model or "xiaomi" in (os.environ.get("LLM_BASE_URL") or "")
    base = os.environ.get("LLM_BASE_URL") or (
        "https://token-plan-cn.xiaomimimo.com/v1" if is_mimo else ""
    )
    if not base:
        print("[ERROR] 未设置 LLM_BASE_URL", file=sys.stderr)
        sys.exit(2)
    url = base.rstrip("/") + "/chat/completions"
    key = (
        os.environ.get("LLM_API_KEY")
        or (os.environ.get("XIAOMI_API_KEY") if is_mimo or "xiaomi" in base else "")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    )
    if not key:
        print("[ERROR] 未设置 XIAOMI_API_KEY / LLM_API_KEY", file=sys.stderr)
        sys.exit(2)
    return model, url, key


def chat(model: str, url: str, key: str, user: str, timeout: int = 180) -> str:
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是企业内部培训设计师。只根据给定素材与上一阶段文件写作，"
                        "不编造制度/数字/公司名。本公司只称「某某公司」，"
                        "产品只称「协同云」「数据洞察」，禁止写星桥或其它像真企业的名称。"
                        "讲师手册禁止逐字稿。"
                        "课后测试题每题必须写字面量【对应培训目标T1】，禁止只写【T1】。"
                        "每份文末必须有「AI 辅助生成、讲师审核后交付」。"
                    ),
                },
                {"role": "user", "content": user},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"LLM HTTP {e.code}: {err}") from e
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM 无 choices: {str(data)[:400]}")
    return (choices[0].get("message") or {}).get("content") or ""


def strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", t)
        if t.endswith("```"):
            t = t[: t.rfind("```")].rstrip()
    return t.strip()


def parse_named_files(raw: str, expected: list[str]) -> dict[str, str]:
    raw = strip_fence(raw)
    found = {name: body.strip() for name, body in FILE_MARK.findall(raw)}
    if found:
        return {k: v for k, v in found.items() if k in expected}
    if len(expected) == 1:
        return {expected[0]: raw}
    raise RuntimeError(
        "模型未按 ===FILE: 文件名=== 输出，无法拆成 "
        + ",".join(expected)
    )


def ensure_ai_mark(text: str) -> str:
    if re.search(r"AI\s*辅助生成", text):
        return text.rstrip() + "\n"
    return text.rstrip() + AI_FOOTER


FILE_BANNER = re.compile(r"^(?:===FILE:\s*[^\n=]+===\s*\n)+")
# 模型常把【对应培训目标T1】缩成【T1】，自检按字面「对应培训目标」匹配
SHORTHAND_GOAL = re.compile(
    r"【(?!对应培训目标)(T[1-5](?:\s*[&、,/]\s*T[1-5])*)】"
)


def strip_file_banner(text: str) -> str:
    """去掉误写进正文开头的 ===FILE: …=== 行。"""
    return FILE_BANNER.sub("", (text or "").lstrip())


def normalize_assessment(text: str) -> str:
    """把【T1】展开成【对应培训目标T1】；若仍无该字面量则补一行说明。"""
    text = strip_file_banner(text)
    text = SHORTHAND_GOAL.sub(r"【对应培训目标\1】", text)
    if not re.search(r"对应培训目标", text) and re.search(r"\bT[1-5]\b", text):
        text = re.sub(
            r"(^# .+?\n)",
            r"\1\n每题标注对应培训目标（T1–T5）。\n",
            text,
            count=1,
            flags=re.M,
        )
    return text


def polish_output(name: str, text: str) -> str:
    text = strip_file_banner(text)
    if name == "06-assessment.md":
        text = normalize_assessment(text)
    return ensure_ai_mark(text)


def load_source_docs(src: Path, limit: int = 60000) -> str:
    parts: list[str] = []
    n = 0
    files = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".txt"})
    if not files:
        print(f"[ERROR] 素材为空: {src}", file=sys.stderr)
        sys.exit(2)
    for p in files:
        chunk = p.read_text(encoding="utf-8", errors="replace")
        header = f"\n\n## 素材文件 {p.name}\n\n"
        take = chunk
        if n + len(header) + len(take) > limit:
            take = take[: max(0, limit - n - len(header) - 20)] + "\n…(截断)\n"
        parts.append(header + take)
        n += len(header) + len(take)
        if n >= limit:
            break
    return "".join(parts)


def read_if(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def present(path: Path) -> bool:
    return path.is_file() and path.stat().st_size >= 50


def load_template_block(md: str, heading: str) -> str:
    # ## 模板 N  … until next ## 模板 or EOF
    pat = re.compile(
        rf"^## {re.escape(heading)}\s*$",
        re.M,
    )
    m = pat.search(md)
    if not m:
        raise RuntimeError(f"stage-prompts.md 缺少 {heading}")
    rest = md[m.end() :]
    nxt = re.search(r"^## 模板 \d+", rest, re.M)
    return rest[: nxt.start() if nxt else None].strip()


def emit_result(
    outdir: Path, ok: bool, extra: str = "", wanted: set[str] | None = None
) -> int:
    """点名时只按点名文件判 success，不因未点名的 01–08 缺失而失败。"""
    scope = [n for n in REQUIRED if (wanted is None or n in wanted)]
    have = [n for n in scope if present(outdir / n)]
    miss = [n for n in scope if n not in have]
    status = "success" if ok and not miss else "failure"
    print("")
    print(f"RESULT: {status}")
    print("FILES: " + (", ".join(have) if have else "(none)"))
    print("MISSING: " + (", ".join(miss) if miss else "(none)"))
    if extra:
        print(extra)
    return 0 if status == "success" else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="信息安全意识")
    ap.add_argument("--force", action="store_true", help="忽略已有文件，全量重写")
    ap.add_argument("--outdir", default="", help="默认 training-materials/<theme>")
    ap.add_argument(
        "--only",
        default="",
        help="只生成点名文件，逗号分隔：08 / 评估反馈表 / 05,06。缺上游则停，不擅自扩成全套 8 份",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir) if args.outdir else WORKSPACE / "training-materials" / args.theme
    src = WORKSPACE / "source-docs"
    prompts_md = (SKILL_DIR / "references" / "stage-prompts.md").read_text(encoding="utf-8")
    outdir.mkdir(parents=True, exist_ok=True)

    stages: list[dict] = [
        {
            "id": "t1",
            "template": "模板 1",
            "outputs": ["01-needs-analysis.md", "02-course-design.md"],
            "inputs": [],
            "use_source": True,
        },
        {
            "id": "t2",
            "template": "模板 2",
            "outputs": ["03-ppt-outline.md"],
            "inputs": ["01-needs-analysis.md", "02-course-design.md"],
        },
        {
            "id": "t3",
            "template": "模板 3",
            "outputs": ["04-instructor-manual.md"],
            "inputs": ["03-ppt-outline.md"],
        },
        {
            "id": "t4",
            "template": "模板 4",
            "outputs": ["05-participant-handbook.md"],
            "inputs": ["03-ppt-outline.md"],
        },
        {
            "id": "t5",
            "template": "模板 5",
            "outputs": ["06-assessment.md"],
            "inputs": ["01-needs-analysis.md", "05-participant-handbook.md"],
        },
        {
            "id": "t6",
            "template": "模板 6",
            "outputs": ["07-delivery-guide.md"],
            "inputs": REQUIRED[:6],
        },
        {
            "id": "t7",
            "template": "模板 7",
            "outputs": ["08-evaluation-form.md"],
            "inputs": ["01-needs-analysis.md", "06-assessment.md"],
            "inputs_optional": True,
        },
    ]

    wanted = parse_only(args.only) if args.only else None
    stages = stages_for_outputs(wanted, stages)

    model = url = key = None
    source_blob = ""

    try:
        for st in stages:
            outs = st["outputs"]
            if not args.force and all(present(outdir / n) for n in outs):
                print(f"[skip] {st['id']} 已有 {', '.join(outs)}", flush=True)
                continue
            if model is None:
                model, url, key = resolve_llm()
            if st.get("use_source") and not source_blob:
                source_blob = load_source_docs(src)
            tpl = load_template_block(prompts_md, st["template"])
            chunks = [
                f"主题：{args.theme}",
                f"产出目录（相对工作区）：training-materials/{args.theme}/",
                "输出格式：若本步多个文件，必须用标记分隔：",
                "===FILE: 01-needs-analysis.md===",
                "（正文）",
                "===FILE: 02-course-design.md===",
                "单文件则直接输出 Markdown 正文，不要包代码围栏。",
                "",
                "【本步模板】",
                tpl,
            ]
            if st.get("use_source"):
                chunks += ["", "【source-docs 素材】", source_blob]
            for name in st["inputs"]:
                body = read_if(outdir / name)
                if not body:
                    if st.get("inputs_optional"):
                        continue
                    print(f"[ERROR] 缺输入 {name}，无法跑 {st['id']}", file=sys.stderr)
                    return emit_result(
                        outdir, False, extra=f"halted_at={st['id']}", wanted=wanted
                    )
                chunks += ["", f"【已有文件 {name}】", body[:24000]]
            print(f"[run] {st['id']} → {', '.join(outs)}", flush=True)
            raw = chat(model, url, key, "\n".join(chunks))
            files = parse_named_files(raw, outs)
            for name in outs:
                text = files.get(name)
                if not text or len(text) < 50:
                    raise RuntimeError(f"{st['id']} 未产出有效 {name}")
                (outdir / name).write_text(polish_output(name, text), encoding="utf-8")
                print(f"  wrote {outdir / name} ({(outdir / name).stat().st_size} bytes)")
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return emit_result(outdir, False, extra=f"error={e}", wanted=wanted)

    # self_check
    check = SKILL_DIR / "scripts" / "self_check.py"
    import subprocess

    cmd = [sys.executable, str(check), "--outdir", str(outdir)]
    if wanted:
        cmd.append("--partial")
    r = subprocess.run(cmd, cwd=str(WORKSPACE))
    extra = f"self_check_exit={r.returncode}"
    return emit_result(outdir, r.returncode == 0, extra=extra, wanted=wanted)


if __name__ == "__main__":
    sys.exit(main())
