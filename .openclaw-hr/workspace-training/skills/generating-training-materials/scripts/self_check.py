#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_check.py —— generating-training-materials 交付前结构自检

对照 evals/eval-cases.md 场景 1/2 的可机器化部分：
  8 份文件齐全、T1-T5、对应矩阵、测试题覆盖、AI 辅助标注等。
讲师手册若出现禁止的「逐字稿」正文会 WARN；「而非逐字稿 / 禁止逐字稿」这类否定表述不算。
判断类条款（是否真读了上一阶段文件）仍需 Agent 按 eval-cases 人工核。

用法：
  python3 skills/generating-training-materials/scripts/self_check.py
  python3 skills/generating-training-materials/scripts/self_check.py --outdir training-materials/AI大模型应用开发

退出码：
  0 = 结构自检通过
  1 = 未通过（stderr 列问题）
  2 = 用法 / 目录问题
"""
from __future__ import annotations

import argparse
import re
import sys
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

AI_MARK = re.compile(r"AI\s*辅助生成")
T_GOAL = re.compile(r"\bT([1-5])\b")
MATRIX = re.compile(r"对应矩阵|模块与培训目标")
ASSESS_TAG = re.compile(r"对应培训目标")
VERBATIM = re.compile(r"逐字稿")
TALKING_POINTS = re.compile(r"讲解要点")
# 否定/说明性提及：不是在写逐字稿
VERBATIM_MENTION = re.compile(
    r"(?:非|而非|不是|禁止(?:写)?|勿(?:再)?写|不要写|无|旧版)逐字稿(?:手册)?"
)


def forbidden_verbatim(text: str) -> bool:
    stripped = VERBATIM_MENTION.sub("", text or "")
    return bool(VERBATIM.search(stripped))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def check(outdir: Path, partial: bool = False) -> tuple[list[str], list[str]]:
    """返回 (problems, warnings)。problems 非空则 FAIL；warnings 仅提示。"""
    problems: list[str] = []
    warnings: list[str] = []
    if not outdir.is_dir():
        return [f"产出目录不存在: {outdir}"], warnings

    texts: dict[str, str] = {}
    for name in REQUIRED:
        p = outdir / name
        if not p.is_file() or p.stat().st_size < 50:
            if not partial:
                problems.append(f"[场景1] 缺失或过短: {name}")
            continue
        texts[name] = _read(p)

    for name, text in texts.items():
        if not AI_MARK.search(text):
            problems.append(f"[合规] {name} 未见「AI 辅助生成」标注")

    needs = texts.get("01-needs-analysis.md", "")
    if needs:
        found = set(T_GOAL.findall(needs))
        missing = {str(i) for i in range(1, 6)} - found
        if missing:
            problems.append(
                f"[场景1/2] 01-needs-analysis.md 培训目标不全，缺 T"
                + ",".join(sorted(missing))
            )

    course = texts.get("02-course-design.md", "")
    if course and not MATRIX.search(course):
        problems.append("[场景2] 02-course-design.md 未见「模块与培训目标对应矩阵」类章节")

    instructor = texts.get("04-instructor-manual.md", "")
    if instructor:
        if forbidden_verbatim(instructor) and not TALKING_POINTS.search(instructor):
            warnings.append(
                "[场景2] 04-instructor-manual.md 仍含逐字稿正文且未见「讲解要点」——"
                "现行流程已取消逐字稿；新生成请按模板 3 只写讲解要点"
            )
        elif forbidden_verbatim(instructor):
            warnings.append(
                "[场景2] 04-instructor-manual.md 仍含逐字稿正文；"
                "新生成勿再产出可照念话术"
            )

    assess = texts.get("06-assessment.md", "")
    if assess:
        if not ASSESS_TAG.search(assess):
            problems.append("[场景2] 06-assessment.md 未见「对应培训目标」题目标注")
        found = set(T_GOAL.findall(assess))
        missing = {str(i) for i in range(1, 6)} - found
        if missing:
            problems.append(
                f"[场景2] 06-assessment.md 未覆盖全部目标，缺 T"
                + ",".join(sorted(missing))
            )

    return problems, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="ADDIE 物料结构自检（对照 eval-cases）")
    ap.add_argument(
        "--outdir",
        default="",
        help="物料目录，默认 <workspace>/training-materials",
    )
    ap.add_argument(
        "--partial",
        action="store_true",
        help="只检查已存在的文件，不要求 8 份齐全（配合 generate --only）",
    )
    args = ap.parse_args()

    script = Path(__file__).resolve()
    workspace = script.parents[3]
    outdir = Path(args.outdir) if args.outdir else workspace / "training-materials"
    if not outdir.is_absolute():
        outdir = (Path.cwd() / outdir).resolve()

    if not outdir.exists():
        print(f"[self_check] 目录不存在: {outdir}", file=sys.stderr)
        return 2

    problems, warnings = check(outdir, partial=args.partial)
    print(f"[self_check] outdir={outdir}")
    for w in warnings:
        print(f"[self_check] WARN · {w}", file=sys.stderr)
    if problems:
        print(f"[self_check] FAIL · {len(problems)} 项未通过", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "[self_check] 请对照 evals/eval-cases.md 的 expected_behavior 修补后重跑。",
            file=sys.stderr,
        )
        return 1

    print("[self_check] OK · 结构项通过（场景1/2 可机器化部分）")
    print(
        "[self_check] 提醒：阶段承接是否「真读了上一文件」等判断项，"
        "仍须按 evals/eval-cases.md 人工核验；讲师手册勿再写逐字稿。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
