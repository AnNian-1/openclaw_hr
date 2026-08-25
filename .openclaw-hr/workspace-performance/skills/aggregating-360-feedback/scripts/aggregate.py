#!/usr/bin/env python3
"""aggregate.py — 360 反馈机械聚合器

用途：aggregating-360-feedback Skill 的核心脚本。读 JSON 目录（通常由
      ingest_archive.py 从 zip/rar 的 DOCX 解析得到，如
      source_feedback/zhanglei/）下的多份 360 反馈 JSON，按视角
      （上级/平级/下属/自评）分组，逐维度算平均分、极差，
      产出 aggregated-data.json 并打印四视角对照表 + 离散度判定。

为什么聚合用脚本不用 LLM：
  算平均分、算极差是确定性计算。LLM 算分会漂移（同一份数据多次算结果
  ±3-5 抖动），而绩效数据是法律敏感数据，分数必须可复现、可审计。
  所以聚合层一律脚本算——aggregated-data.json 是唯一数据基准
  （single source of truth），下游报告、看板都从它取数，不重新算。
  评语对照、分歧归因这类语言理解任务才交给 LLM。

判定口径：某维度上"各视角平均分的极差 >= 1.0"标记为疑似分歧（⚠️），
  否则标共识（✅）。极差 1.0 这个阈值是机械信号——它只负责"触发关注"，
  最终共识/分歧结论交给第二层 LLM 综合分析读评语后定。

CLI：python3 aggregate.py <json_dir> [out_json_path]
  json_dir      —— 某位被评估人的反馈 JSON 目录（如 source_feedback/zhanglei/）
  out_json_path —— 可选；缺省为 <json_dir>/aggregated-data.json
                   （与该人原料同目录：source_feedback/<slug>/）
  退出码 0 = 成功；1 = 数据问题；2 = 用法错误
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# 非反馈表 JSON（与原料同目录，加载时需跳过）
SKIP_JSON_NAMES = {"aggregated-data.json"}

# 5 个评估维度，源自星桥科技绩效制度第四条。
DIMENSIONS = ["goal_achievement", "professional_skill",
              "collaboration", "responsibility", "growth"]
DIM_CN = {
    "goal_achievement": "目标达成", "professional_skill": "专业能力",
    "collaboration": "协作沟通", "responsibility": "责任心", "growth": "学习成长",
}
PERSPECTIVE_LABELS = {
    "manager": "上级（直接主管）",
    "peer": "平级",
    "report": "下属",
    "self": "自评",
}
# 疑似分歧的机械阈值：视角平均分极差 >= 1.0 即触发关注。
SPLIT_THRESHOLD = 1.0


def die(msg, code=1):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def default_aggregate_out(json_dir: str) -> str:
    """一次聚合一个人：产出写到该人目录 source_feedback/<slug>/aggregated-data.json。"""
    return str(Path(json_dir).resolve() / "aggregated-data.json")


def default_report_out(json_dir: str) -> str:
    """第二层综合分析报告约定路径：同目录 aggregated-report.md。"""
    return str(Path(json_dir).resolve() / "aggregated-report.md")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 aggregate.py <json_dir> [out_json_path]",
              file=sys.stderr)
        sys.exit(2)

    raw_dir = sys.argv[1]
    if not os.path.isdir(raw_dir):
        die(f"JSON 目录不存在: {raw_dir}", 2)

    out_path = (sys.argv[2] if len(sys.argv) > 2
                else default_aggregate_out(raw_dir))
    report_path = default_report_out(raw_dir)

    # ---- 1. 加载所有反馈（_ 开头 / 聚合产物 跳过）----
    feedbacks = []
    for fname in sorted(os.listdir(raw_dir)):
        if fname.startswith("_") or not fname.endswith(".json"):
            continue
        if fname in SKIP_JSON_NAMES or fname.startswith("aggregated-"):
            continue
        path = os.path.join(raw_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            fb = json.load(f)
            fb["source_file"] = fname
            feedbacks.append(fb)

    if not feedbacks:
        die(f"{raw_dir} 下没有任何反馈 JSON")

    # ---- 2. 按视角分组 ----
    groups = defaultdict(list)
    for fb in feedbacks:
        groups[fb["reviewer_relation"]].append(fb)

    subject = feedbacks[0].get("subject", "")
    aggregated = {
        "subject": subject,
        "subject_role": feedbacks[0].get("subject_role", ""),
        "period": feedbacks[0].get("period", ""),
        "total_feedback_count": len(feedbacks),
        "perspectives": {},
    }

    # ---- 3. 逐视角逐维度算 average / min / max ----
    for relation, fbs in sorted(groups.items()):
        label = PERSPECTIVE_LABELS.get(relation, relation)
        dim_stats = {}
        for dim in DIMENSIONS:
            scores = [fb["scores"][dim] for fb in fbs]
            dim_stats[dim] = {
                "scores": scores,
                "count": len(scores),
                "average": round(sum(scores) / len(scores), 2),
                "min": min(scores),
                "max": max(scores),
            }
        reviewers = [{"alias": fb["reviewer_alias"], "file": fb["source_file"]}
                     for fb in fbs]
        aggregated["perspectives"][relation] = {
            "label": label,
            "count": len(fbs),
            "reviewers": reviewers,
            "dimensions": dim_stats,
        }

    # ---- 4. overall 段：所有反馈在每维度的总平均 + range ----
    overall = {}
    for dim in DIMENSIONS:
        all_scores = [fb["scores"][dim] for fb in feedbacks]
        overall[dim] = {
            "average": round(sum(all_scores) / len(all_scores), 2),
            "min": min(all_scores),
            "max": max(all_scores),
            "range": max(all_scores) - min(all_scores),
        }
    aggregated["overall"] = overall

    # ---- 5. divergence 段：逐维度算"视角平均分极差"+ 疑似分歧标记 ----
    # 这是聚合的核心产出之一——把"哪些维度各视角说法打架"机械地标出来。
    # 注意分析单位是"视角平均分"不是"单份反馈"：360 反馈要看的是
    # "下属群体 vs 上级"的系统性差异，不是某一个人打分偏低的个体噪声。
    divergence = {}
    relations_present = sorted(groups.keys())
    for dim in DIMENSIONS:
        persp_avgs = [aggregated["perspectives"][r]["dimensions"][dim]["average"]
                      for r in relations_present]
        rng = round(max(persp_avgs) - min(persp_avgs), 2)
        divergence[dim] = {
            "perspective_range": rng,
            "suspected_split": rng >= SPLIT_THRESHOLD,
        }
    aggregated["divergence"] = divergence
    aggregated["split_threshold"] = SPLIT_THRESHOLD

    # ---- 6. 落盘 ----
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)

    # ---- 7. 终端打印对照表 ----
    print(f"✅ 聚合完成：{len(feedbacks)} 份反馈 → {out_path}")
    print(f"   评估对象：{subject}")
    print("   视角分组：" + ", ".join(
        f"{PERSPECTIVE_LABELS.get(k, k)}({len(v)}份)"
        for k, v in sorted(groups.items())))

    print("\n📊 四视角 × 五维度 平均分对照表：")
    header = f"{'维度':<20}" + "".join(
        f"{PERSPECTIVE_LABELS.get(k, k):>12}" for k in relations_present)
    print(header)
    print("-" * len(header))
    for dim in DIMENSIONS:
        row = f"{DIM_CN[dim]:<20}"
        for relation in relations_present:
            row += (f"{aggregated['perspectives'][relation]['dimensions'][dim]['average']:>12.2f}")
        print(row)

    print(f"\n📈 维度离散度（各视角平均分的极差，阈值 {SPLIT_THRESHOLD}）：")
    for dim in DIMENSIONS:
        d = divergence[dim]
        marker = "⚠️ 疑似分歧" if d["suspected_split"] else "✅ 共识"
        print(f"  {DIM_CN[dim]:<10} 极差={d['perspective_range']:.2f}  {marker}")

    splits = [DIM_CN[d] for d in DIMENSIONS
              if divergence[d]["suspected_split"]]
    print(f"\n   疑似分歧维度 {len(splits)} 个："
          f"{', '.join(splits) if splits else '无'}")
    print("   极差是机械信号，只触发关注；最终共识/分歧结论交给 LLM 综合分析层读评语后定。")
    print(f"   第二层综合分析报告请写到：{report_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
