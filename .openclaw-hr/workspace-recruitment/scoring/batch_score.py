#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招聘子 Agent · 批量评分 + 排序
================================================================
对一个 JD，批量评分一批候选人，按综合匹配分排序，产出初筛排序结果。
对应场景 1「上午集中筛简历」——HR 把一批简历丢给小慧，拿到排序好的候选人。

合规边界（candidate-profile-schema.md §9 铁律）：
  本脚本只产出【评分与排序建议】，不做录用/淘汰决定。
  排序结果里每个候选人标"建议动作"而非"淘汰/通过"——
  最终决定由人工 HR 做（个保法 24 条 + Workday Mobley 判例）。

用法：batch_score.py <JD-md路径> <简历目录> <简历名匹配前缀> [输出json]
"""
import glob
import json
import os
import sys

from score_pipeline import run_pipeline


def main():
    if len(sys.argv) < 4:
        print("用法：batch_score.py <JD-md> <简历目录> <简历名前缀> [输出json]")
        sys.exit(1)
    jd_path, resume_dir, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = sys.argv[4] if len(sys.argv) > 4 else None

    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()
    jd_name = os.path.basename(jd_path)

    resumes = sorted(glob.glob(os.path.join(resume_dir, f"{prefix}*.md")))
    print(f"JD：{jd_name}")
    print(f"候选人池：{len(resumes)} 份（匹配前缀 {prefix}）\n")

    results = []
    failed = []
    for i, rp in enumerate(resumes, 1):
        name = os.path.basename(rp)
        print(f"--- [{i}/{len(resumes)}] {name} ---", flush=True)
        # 每份候选人最多尝试 3 次——批量初筛不能因偶发故障漏掉候选人
        r = None
        for attempt in range(1, 4):
            try:
                r = run_pipeline(rp, jd_text, jd_name, verbose=False)
                break
            except Exception as e:
                print(f"  第 {attempt} 次失败：{e}", flush=True)
                if attempt < 3:
                    print(f"  重试中 ...", flush=True)
        if r is None:
            print(f"  ✗ 3 次均失败，标记为待人工处理", flush=True)
            failed.append(name)
            continue
        s = r["score"]
        stripped_n = len(r["compliance_stripped"])
        na = r.get("number_audit", {})
        fab_n = na.get("fabricated", 0)
        audit_tag = (f" | ✗数字虚构 {fab_n} 处(已修正)" if fab_n
                     else f" | ✓数字回核通过")
        print(f"  合规过滤：剥离 {stripped_n} 个敏感字段 | "
              f"综合分 {s['jd_match_score']} | 评级 {s['overall_rating']}"
              f"{' | ⚠硬伤 ' + str(s['hard_issues']) if s.get('hard_issues') else ''}"
              f"{audit_tag}",
              flush=True)
        results.append(r)

    # ── 按综合匹配分排序 ──────────────────────────────────────
    results.sort(key=lambda r: r["score"]["jd_match_score"], reverse=True)

    print(f"\n{'='*64}")
    print(f"初筛排序结果（按综合匹配分降序）—— {jd_name}")
    print(f"{'='*64}")
    print(f"{'排名':<4}{'候选人':<10}{'综合分':<7}{'评级':<6}{'硬伤':<5}建议动作")
    print("-" * 64)
    ranking = []
    for rank, r in enumerate(results, 1):
        s = r["score"]
        name = s.get("candidate_name", r["parsed"].get("name", "?"))
        score = s["jd_match_score"]
        rating = s["overall_rating"].split("(")[0]
        has_hard = "有" if s.get("hard_issues") else "—"
        # 建议动作——只给建议，不做淘汰决定
        if s.get("hard_issues"):
            action = "建议人工复核简历硬伤后再定"
        elif score >= 80:
            action = "建议优先安排面试"
        elif score >= 60:
            action = "建议进入面试候选名单"
        else:
            action = "建议人工复核是否纳入"
        print(f"{rank:<5}{name:<11}{score:<8}{rating:<7}{has_hard:<6}{action}")
        ranking.append({
            "rank": rank, "name": name, "resume_file": r["resume_file"],
            "jd_match_score": score, "overall_rating": s["overall_rating"],
            "hard_issues": s.get("hard_issues", []),
            "suggested_action": action,
            "score_reasoning": s["score_reasoning"],
            "number_audit": r.get("number_audit", {}),
        })
    print("-" * 64)

    # ── 数字回核汇总（真实性证据，可审计） ──────────────────────
    total_nums = sum(r.get("number_audit", {}).get("total_numbers", 0)
                     for r in results)
    fab_items = []
    for r in results:
        nm = r["score"].get("candidate_name", r["parsed"].get("name", "?"))
        for fix in r.get("number_audit", {}).get("fixes", []):
            fab_items.append((nm, fix))
    print(f"数字回核汇总：{len(results)} 份候选人共提取 {total_nums} 个数字，"
          f"发现 {len(fab_items)} 处虚构")
    if fab_items:
        for nm, fix in fab_items:
            mark = "已修正" if fix.get("applied") else "需人工"
            print(f"  ✗ [{nm}] 字段 {fix.get('loc')}：")
            print(f"     产出虚构值「{fix.get('fabricated')}」"
                  f"→ 原简历真实值「{fix.get('real_value')}」（{mark}）")
            print(f"     判定：{fix.get('reason','')}")
    else:
        print("  ✓ 全部候选人评分产出未发现数字虚构")
    print("-" * 64)
    if failed:
        print(f"⚠ 以下 {len(failed)} 份评分未成功，已标记待人工处理（不静默丢弃）：")
        for f in failed:
            print(f"   - {f}")
        print("-" * 64)
    print("说明：以上为 AI 评分与排序【建议】，最终淘汰/录用决定由人工 HR 做。")
    print("      依据：个人信息保护法第 24 条 / Workday Mobley 判例。")

    if out_path:
        payload = {"jd": jd_name, "candidate_count": len(results),
                   "failed_candidates": failed,
                   "ranking": ranking, "details": results}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n完整结果已保存：{out_path}")


if __name__ == "__main__":
    main()
