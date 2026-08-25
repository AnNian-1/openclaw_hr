#!/usr/bin/env python3
"""check_feedback.py — 360 反馈数据前置校验器

用途：aggregating-360-feedback Skill 的质检闭环。在跑聚合之前，先把
      JSON 目录（通常由 ingest_archive.py 从 zip/rar 解压 DOCX 后生成，
      如 source_feedback/zhanglei/）下的反馈表逐份校验——结构合法、
      5 个维度齐全、评分在 1-5 区间。
      聚合脚本默认每份反馈结构都对，所以这一关必须先过：脏数据进了聚合，
      算出来的平均分和极差就不可信。把"数据合不合法"这件确定性的事
      从 LLM 的眼睛收回到脚本里。

校验项：
  1. 每个 JSON 文件可解析
  2. 必需字段齐全：reviewer_relation / scores / comments
  3. reviewer_relation 取值合法（manager / peer / report / self 之一）
  4. scores 含 5 个维度且每个维度评分为 1-5 整数
  5. 至少有 1 份 manager + 1 份 self（360 反馈的视角完整性下限）

CLI：python3 check_feedback.py <json_dir>
  退出码 0 = 全部合法；1 = 校验失败（列出全部问题）；2 = 用法错误
"""

import json
import glob
import os
import sys

# 非单份反馈表（与原料同目录的聚合产物），校验时跳过
SKIP_JSON_NAMES = {"aggregated-data.json"}

# 5 个评估维度，源自星桥科技绩效制度第四条（业绩结果 + 行为价值观）。
DIMENSIONS = ["goal_achievement", "professional_skill",
              "collaboration", "responsibility", "growth"]
# 360 反馈的四类视角。少一类都构不成"360"（全方位）。
VALID_RELATIONS = {"manager", "peer", "report", "self"}


def fail(problems):
    print("❌ 360 反馈数据校验未通过：", file=sys.stderr)
    for i, p in enumerate(problems, 1):
        print(f"  {i}. {p}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 check_feedback.py <json_dir>", file=sys.stderr)
        sys.exit(2)

    raw_dir = sys.argv[1]
    if not os.path.isdir(raw_dir):
        print(f"目录不存在: {raw_dir}", file=sys.stderr)
        sys.exit(2)

    problems = []
    rows = []
    relation_count = {}

    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not files:
        fail([f"{raw_dir} 下没有任何 .json 反馈文件"])

    for path in files:
        fname = os.path.basename(path)
        # _ 开头的是 schema 等说明文件，跳过
        if fname.startswith("_"):
            continue
        # 同目录下的聚合产物，不是单份反馈表
        if fname in SKIP_JSON_NAMES or fname.startswith("aggregated-"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                fb = json.load(f)
        except json.JSONDecodeError as e:
            problems.append(f"{fname} JSON 无法解析：{e}")
            continue

        # 必需字段
        for key in ("reviewer_relation", "scores", "comments"):
            if key not in fb:
                problems.append(f"{fname} 缺少必需字段 {key}")
        if "reviewer_relation" not in fb or "scores" not in fb:
            continue

        rel = fb["reviewer_relation"]
        if rel not in VALID_RELATIONS:
            problems.append(
                f"{fname} 的 reviewer_relation=\"{rel}\" 非法，"
                f"必须是 manager/peer/report/self 之一")
        relation_count[rel] = relation_count.get(rel, 0) + 1

        s = fb["scores"]
        for dim in DIMENSIONS:
            if dim not in s:
                problems.append(f"{fname} 的 scores 缺维度 {dim}")
                continue
            v = s[dim]
            if not isinstance(v, int) or not (1 <= v <= 5):
                problems.append(
                    f"{fname} 的 {dim} 评分非法：{v!r}（须为 1-5 的整数）")

        if all(d in s for d in DIMENSIONS):
            rows.append((fname, rel, [s[d] for d in DIMENSIONS]))

    # 视角完整性下限：360 反馈至少要有上级和自评
    if relation_count.get("manager", 0) < 1:
        problems.append("缺少上级（manager）反馈——360 反馈必须含直接主管视角")
    if relation_count.get("self", 0) < 1:
        problems.append("缺少自评（self）反馈——360 反馈必须含本人自我认知视角")

    if problems:
        fail(problems)

    # 通过——打印评分总览
    print(f"{'文件':<16}{'关系':<9}{'目标':>6}{'专业':>6}{'协作':>6}{'责任':>6}{'成长':>6}")
    print("-" * 61)
    for fname, rel, scores in rows:
        print(f"{fname:<16}{rel:<9}" + "".join(f"{v:>6}" for v in scores))

    summary = ", ".join(
        f"{r}({relation_count[r]})" for r in sorted(relation_count))
    print(f"\n✅ {len(rows)} 份反馈 JSON 全部校验合法（5 维度齐全、评分 1-5）")
    print(f"   视角分布：{summary}")
    sys.exit(0)


if __name__ == "__main__":
    main()
