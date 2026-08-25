#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H-1 场景1端到端验证：打印批量评分排序结果（只读，不重新评分）。
用法：python3 show_ranking.py <ranking.json>
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "scoring/results/ranking-后端开发.json"
d = json.load(open(path, encoding="utf-8"))

print(f"JD: {d['jd']}")
print(f"候选人池: {d['candidate_count']} 份    评分失败: {len(d['failed_candidates'])} 份")
print()
print(f"{'排名':<5}{'候选人':<9}{'JD匹配分':<10}{'评级':<9}{'数字回核':<18}建议动作")
print("-" * 78)
for r in d["ranking"]:
    na = r.get("number_audit", {})
    audit = f"{na.get('total_numbers')}抽/{na.get('suspects')}存疑/{na.get('fabricated')}虚构"
    print(f"{r['rank']:<6}{r['name']:<8}{r['jd_match_score']:<12}"
          f"{r['overall_rating']:<10}{audit:<19}{r['suggested_action']}")
