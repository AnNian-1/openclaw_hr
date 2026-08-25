#!/usr/bin/env python3
"""360 反馈数据校验脚本：读 raw/ 下 7 份反馈 JSON，校验结构合法，打印评分总览"""

import json
import glob
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
DIMENSIONS = ["goal_achievement", "professional_skill", "collaboration", "responsibility", "growth"]

rows = []
for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.json"))):
    fname = os.path.basename(path)
    if fname.startswith("_"):  # 跳过 _schema.md 之外的下划线文件
        continue
    with open(path, "r", encoding="utf-8") as f:
        fb = json.load(f)  # JSON 不合法会在这里抛错
    s = fb["scores"]
    # 校验 5 个维度齐全、评分在 1-5 之间
    for dim in DIMENSIONS:
        assert dim in s, f"{fname} 缺维度 {dim}"
        assert 1 <= s[dim] <= 5, f"{fname} 的 {dim} 评分越界：{s[dim]}"
    rows.append((fname, fb["reviewer_relation"],
                 s["goal_achievement"], s["professional_skill"],
                 s["collaboration"], s["responsibility"], s["growth"]))

print(f"{'文件':<16}{'关系':<9}{'目标':>6}{'专业':>6}{'协作':>6}{'责任':>6}{'成长':>6}")
print("-" * 61)
for r in rows:
    print(f"{r[0]:<16}{r[1]:<9}{r[2]:>6}{r[3]:>6}{r[4]:>6}{r[5]:>6}{r[6]:>6}")

print(f"\n✅ {len(rows)} 份反馈 JSON 全部校验合法、结构统一（5 维度齐全、评分 1-5 合法）")
