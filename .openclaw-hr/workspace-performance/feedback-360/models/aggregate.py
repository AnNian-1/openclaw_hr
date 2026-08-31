#!/usr/bin/env python3
"""360 反馈聚合脚本：按视角分组计算各维度平均分，输出 aggregated-data.json"""

import json
import os
from collections import defaultdict

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
OUT_PATH = os.path.join(os.path.dirname(__file__), "aggregated-data.json")

DIMENSIONS = ["goal_achievement", "professional_skill", "collaboration", "responsibility", "growth"]
PERSPECTIVE_LABELS = {
    "manager": "上级（直接主管）",
    "peer": "平级",
    "report": "下属",
    "self": "自评",
}

# 加载所有反馈
feedbacks = []
for fname in sorted(os.listdir(RAW_DIR)):
    if fname.startswith("_") or not fname.endswith(".json"):
        continue
    path = os.path.join(RAW_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        fb = json.load(f)
        fb["source_file"] = fname
        feedbacks.append(fb)

# 按视角分组
groups = defaultdict(list)
for fb in feedbacks:
    groups[fb["reviewer_relation"]].append(fb)

# 计算各视角各维度统计
aggregated = {
    "subject": "员工1",
    "subject_role": "支付平台研发组 后端开发工程师",
    "period": "2026-H1",
    "total_feedback_count": len(feedbacks),
    "perspectives": {},
}

for relation, fbs in sorted(groups.items()):
    label = PERSPECTIVE_LABELS.get(relation, relation)
    dim_stats = {}
    for dim in DIMENSIONS:
        scores = [fb["scores"][dim] for fb in fbs]
        avg = round(sum(scores) / len(scores), 2)
        dim_stats[dim] = {
            "scores": scores,
            "count": len(scores),
            "average": avg,
            "min": min(scores),
            "max": max(scores),
        }
    reviewers = [{"alias": fb["reviewer_alias"], "file": fb["source_file"]} for fb in fbs]
    aggregated["perspectives"][relation] = {
        "label": label,
        "count": len(fbs),
        "reviewers": reviewers,
        "dimensions": dim_stats,
    }

# 整体摘要（所有反馈平均，仅供参考）
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

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(aggregated, f, ensure_ascii=False, indent=2)

print(f"✅ 聚合完成：{len(feedbacks)} 份反馈 → {OUT_PATH}")
print(f"   视角分组：{', '.join(f'{PERSPECTIVE_LABELS.get(k, k)}({len(v)}份)' for k, v in sorted(groups.items()))}")

# 打印维度对照表
print("\n📊 四视角 × 五维度 平均分对照表：")
header = f"{'维度':<20}" + "".join(f"{PERSPECTIVE_LABELS.get(k, k):>12}" for k in sorted(groups.keys()))
print(header)
print("-" * len(header))
for dim in DIMENSIONS:
    dim_cn = {"goal_achievement": "目标达成", "professional_skill": "专业能力",
              "collaboration": "协作沟通", "responsibility": "责任心", "growth": "学习成长"}[dim]
    row = f"{dim_cn:<20}"
    for relation in sorted(groups.keys()):
        row += f"{aggregated['perspectives'][relation]['dimensions'][dim]['average']:>12.2f}"
    print(row)

print("\n📈 维度离散度（各视角平均分的 range）：")
for dim in DIMENSIONS:
    dim_cn = {"goal_achievement": "目标达成", "professional_skill": "专业能力",
              "collaboration": "协作沟通", "responsibility": "责任心", "growth": "学习成长"}[dim]
    avgs = [aggregated['perspectives'][r]['dimensions'][dim]['average'] for r in sorted(groups.keys())]
    rng = round(max(avgs) - min(avgs), 2)
    marker = "⚠️ 分歧" if rng >= 1.0 else "✅ 共识"
    print(f"  {dim_cn:<10} range={rng:.2f}  {marker}")
