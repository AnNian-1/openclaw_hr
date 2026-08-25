#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本周（2026-05-11 ~ 2026-05-16）简历筛选与评分排序
===========================================================
独立于 LLM API 的启发式评分，基于结构化数据（parsed-all.json），
多维度评估候选人质量，按职能分类排序。
"""
import json
import os
import math
from datetime import datetime, date

WORKSPACE = os.path.expanduser("~/.openclaw-hr/workspace-recruitment")
PARSED_ALL = os.path.join(WORKSPACE, "talent-pool/parsed-all.json")
INBOX = os.path.join(WORKSPACE, "inbox")

# 本周日期范围
WEEK_START = date(2026, 5, 11)
WEEK_END = date(2026, 5, 16)

# ── 职能分类 ──────────────────────────────────────────
CATEGORY_LABELS = {
    "tech": "🖥️ 技术",
    "product": "📦 产品/项目",
    "operations": "📊 运营",
    "function": "🏢 职能",
}

# 各职能的角色薪资基准（月薪 K），用于评估期望是否合理
SALARY_BANDS = {
    "tech": {"junior": (8, 18), "mid": (15, 30), "senior": (25, 55), "lead": (40, 80)},
    "product": {"junior": (7, 15), "mid": (12, 25), "senior": (20, 40), "lead": (35, 60)},
    "operations": {"junior": (6, 12), "mid": (10, 22), "senior": (18, 35), "lead": (30, 50)},
    "function": {"junior": (5, 10), "mid": (8, 20), "senior": (15, 35), "lead": (28, 50)},
}

# 学历赋分
DEGREE_SCORE = {"博士": 100, "硕士": 85, "本科": 70, "大专": 50, "高中": 30, "": 40}

def load_parsed():
    with open(PARSED_ALL, encoding="utf-8") as f:
        return json.load(f)

def classify_category(filename):
    """从文件名推断职能类别"""
    if "-tech-" in filename:
        return "tech"
    elif "-product-" in filename:
        return "product"
    elif "-operations-" in filename:
        return "operations"
    elif "-function-" in filename:
        return "function"
    return "unknown"

def parse_salary_range(salary_str):
    """解析期望薪资，返回 (min_k, max_k) 或 None"""
    if not salary_str:
        return None
    import re
    # 匹配如 "60K–75K"、"18K–22K"、"18K base + 提成（年综合期望 45–60W）"等
    # 先尝试月薪
    m = re.findall(r'(\d+(?:\.\d+)?)\s*[Kk]', salary_str)
    if m:
        ks = [float(x) for x in m]
        return (min(ks), max(ks))
    # 年薪
    m = re.findall(r'(\d+(?:\.\d+)?)\s*[Ww万]', salary_str)
    if m:
        ws = [float(x) for x in m]
        return (min(ws) / 12, max(ws) / 12)
    return None

def score_education(edu):
    """教育背景评分 0-100"""
    if not edu:
        return 50
    score = DEGREE_SCORE.get(edu.get("degree", ""), 40)
    # 学校知名度加分（简单规则：985/211/海外名校）
    school = edu.get("school", "")
    if any(k in school for k in ["北京", "清华", "上海交通", "复旦", "浙江", "南京", "武汉", "中山",
                                 "中国科学技术", "哈尔滨工业", "西安交通", "香港", "QS", "双一流"]):
        score += 10
    if "硕士" in edu.get("degree", "") and "博士" not in edu.get("degree", ""):
        score += min(5, score * 0.05)  # 硕士小幅加分
    return min(100, score)

def safe_years(val):
    """安全转数字"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def score_experience(parsed):
    """经验评分 0-100，综合年限、稳定性、职业成长"""
    years = safe_years(parsed.get("total_experience_years"))
    if years is None:
        # 从工作经历推算
        exp = parsed.get("work_experience", [])
        if exp:
            try:
                start_dates = [e.get("start_date", "") for e in exp if e.get("start_date")]
                end_dates = [e.get("end_date", "") for e in exp if e.get("end_date")]
                if start_dates:
                    earliest = min(start_dates)
                    latest = max([d for d in end_dates if d != "至今"] + [d for d in start_dates])
                    # 简单计算
                    y1 = float(earliest.split(".")[0]) if "." in earliest else float(earliest[:4])
                    y2 = float(latest.split(".")[0]) if "." in latest else float(latest[:4])
                    years = max(0, y2 - y1)
            except:
                years = 0
        else:
            years = 0
    
    # 年限分：0-5年线性增长，5-12年高分，>12年高位
    if years <= 0:
        year_score = 15
    elif years <= 1:
        year_score = 25
    elif years <= 3:
        year_score = 40 + (years - 1) * 15
    elif years <= 8:
        year_score = 55 + (years - 3) * 8
    elif years <= 15:
        year_score = 95
    else:
        year_score = min(100, 95 + (years - 15) * 0.5)
    
    # 稳定性：平均每段工作经历年限
    job_count = len(parsed.get("work_experience", [])) or 1
    avg_tenure = years / job_count if years > 0 else 0
    if avg_tenure >= 3:
        stability = 100
    elif avg_tenure >= 2:
        stability = 80
    elif avg_tenure >= 1.5:
        stability = 65
    elif avg_tenure >= 1:
        stability = 50
    else:
        stability = 30
    
    # 职位成长性：看职位是否有递进
    positions = [e.get("position", "") for e in parsed.get("work_experience", [])]
    growth_score = 60  # 基线
    if any("经理" in p or "主管" in p or "负责人" in p or "总监" in p for p in positions):
        growth_score = 85
    if any("总监" in p or "负责人" in p or "lead" in p.lower() or "architect" in p.lower() for p in positions):
        growth_score = 95
    
    return round(year_score * 0.5 + stability * 0.25 + growth_score * 0.25)

def score_skills(parsed):
    """技能评分 0-100：数量、专业度"""
    skills = parsed.get("skills", [])
    if not skills:
        return 30
    
    # 技能数量
    count = len(skills)
    count_score = min(100, count * 10)
    
    # 硬技能权重（有认证/专业工具/编程语言的得高分）
    hard_skill_keywords = [
        "CPA", "CFA", "PMP", "认证", "Python", "Java", "Go", "SQL", "Spark",
        "Hadoop", "K8s", "Docker", "React", "Vue", "AWS", "OCI", "阿里云",
        "SAP", "Oracle", "TensorFlow", "PyTorch", "大模型", "LLM", "NLP",
        "注册会计师", "律师", "税务师", "法考", "FRM", "CISSP", "CCIE"
    ]
    hard_count = sum(1 for s in skills if any(kw.lower() in s.lower() for kw in hard_skill_keywords))
    hard_score = min(100, hard_count * 15 + 30)
    
    return round(count_score * 0.4 + hard_score * 0.6)

def score_self_eval(parsed):
    """自我评价质量 0-100"""
    text = parsed.get("self_evaluation", "")
    if not text:
        return 40
    length = len(text)
    # 长度分
    if length >= 300:
        len_score = 95
    elif length >= 200:
        len_score = 80
    elif length >= 100:
        len_score = 60
    else:
        len_score = 40
    
    # 内容质量：包含成就/数据/愿景等
    quality_keywords = ["成就", "提升", "优化", "增长", "%", "倍", "排名", "获奖",
                        "目标", "规划", "方向", "深耕", "负责"]
    quality_hits = sum(1 for kw in quality_keywords if kw in text)
    quality_score = min(100, quality_hits * 10 + 40)
    
    # 避免空话
    fluff_keywords = ["性格开朗", "认真负责", "努力", "吃苦耐劳", "服从安排"]
    fluff_count = sum(1 for kw in fluff_keywords if kw in text)
    fluff_penalty = min(20, fluff_count * 5)
    
    return max(20, round(len_score * 0.3 + quality_score * 0.7 - fluff_penalty))

def score_salary_fit(parsed, category):
    """薪资期望合理性 0-100"""
    sal = parse_salary_range(parsed.get("expected_salary", ""))
    if not sal:
        return 60  # 未知，居中
    
    exp_years = safe_years(parsed.get("total_experience_years")) or 0
    # 判断级别
    if exp_years <= 1:
        level = "junior"
    elif exp_years <= 4:
        level = "mid"
    elif exp_years <= 8:
        level = "senior"
    else:
        level = "lead"
    
    band = SALARY_BANDS.get(category, {}).get(level, (5, 80))
    mid_sal = (sal[0] + sal[1]) / 2
    
    # 在带宽范围内的得分高
    if band[0] <= mid_sal <= band[1]:
        return 90
    elif mid_sal < band[0]:
        # 低于市场，可能低估自己
        return 70
    elif mid_sal <= band[1] * 1.3:
        # 略高
        return 65
    else:
        return max(20, 60 - (mid_sal - band[1]) / band[1] * 40)

def compute_overall(scores):
    """综合评分"""
    weights = {
        "experience": 0.30,
        "education": 0.15,
        "skills": 0.25,
        "self_eval": 0.10,
        "salary_fit": 0.20,
    }
    return round(sum(scores[k] * weights[k] for k in weights))

def get_rating(score):
    if score >= 85:
        return "S（重点关注）"
    elif score >= 75:
        return "A（建议面试）"
    elif score >= 65:
        return "B（进入候选）"
    elif score >= 55:
        return "C（可观察）"
    else:
        return "D（暂不优先）"

def get_highlights(parsed, category):
    """提取亮点和注意事项"""
    highlights = []
    concerns = []
    exp_years = safe_years(parsed.get("total_experience_years")) or 0
    
    # 经验亮点
    if exp_years >= 10:
        highlights.append(f"资深：{exp_years}年经验")
    elif exp_years >= 5:
        highlights.append(f"成熟：{exp_years}年经验")
    
    # 学历亮点
    edu = parsed.get("education", {})
    degree = edu.get("degree", "")
    school = edu.get("school", "")
    if "硕士" in degree:
        highlights.append(f"硕士学历")
    if any(k in school for k in ["北京", "清华", "复旦", "上海交通", "浙江", "南京", "香港"]):
        highlights.append(f"名校背景")
    
    # 技能亮点
    skills = parsed.get("skills", [])
    premium_skills = ["CPA", "PMP", "律师", "大模型", "LLM", "K8s", "高并发", "Spark", "Hadoop"]
    matched_premium = [s for s in skills if any(ps in s for ps in premium_skills)]
    if matched_premium:
        highlights.append(f"稀缺技能：{', '.join(matched_premium[:3])}")
    
    # 职位亮点
    positions = [e.get("position", "") for e in parsed.get("work_experience", [])]
    if any("总监" in p or "负责人" in p or "架构师" in p for p in positions):
        highlights.append("有管理/架构经验")
    
    # 关注事项
    job_count = len(parsed.get("work_experience", [])) or 1
    if job_count >= 4:
        avg_tenure = exp_years / job_count if exp_years > 0 else 0
        if avg_tenure < 1.5:
            concerns.append(f"跳槽频繁（均{avg_tenure:.1f}年/段）")
    
    salary_str = parsed.get("expected_salary", "")
    if salary_str:
        sal = parse_salary_range(salary_str)
        if sal:
            cat_sal = SALARY_BANDS.get(category, {}).get("senior", (20, 40))
            if sal[1] > cat_sal[1] * 1.5:
                concerns.append(f"期望薪资偏高（{sal[0]:.0f}K-{sal[1]:.0f}K）")
    
    # 工作年限异常
    if exp_years <= 0:
        concerns.append("应届/实习经验")
    
    return highlights, concerns

def main():
    all_data = load_parsed()
    
    # 判断本周收到的简历（从 inbox 文件时间判断）
    # 所有 inbox 文件修改时间都在 5/15-5/16，均为本周收到
    week_files = []
    for fname in all_data.keys():
        fpath = os.path.join(INBOX, fname)
        if os.path.exists(fpath):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).date()
            if WEEK_START <= mtime <= WEEK_END:
                week_files.append(fname)
        else:
            # 如果原始文件（可能是 .pdf/.docx）存在也算
            base = fname.replace(".md", "")
            for ext in [".pdf", ".docx"]:
                alt = os.path.join(INBOX, base.rsplit(".md", 1)[0] + ext)
                if os.path.exists(alt):
                    mtime = datetime.fromtimestamp(os.path.getmtime(alt)).date()
                    if WEEK_START <= mtime <= WEEK_END:
                        week_files.append(fname)
                        break
    
    # 过滤：只保留本周的
    if week_files:
        candidates = {k: all_data[k] for k in week_files if k in all_data}
    else:
        candidates = all_data  # fallback
    
    print(f"{'='*72}")
    print(f"📋 本周（{WEEK_START} ~ {WEEK_END}）简历筛选报告")
    print(f"{'='*72}")
    print(f"共收到简历：{len(candidates)} 份")
    print(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # 按职能分组统计
    by_category = {}
    for fname, data in candidates.items():
        cat = classify_category(fname)
        by_category.setdefault(cat, []).append((fname, data))
    
    # 统计概览
    print("📊 职能分布：")
    for cat in ["tech", "product", "operations", "function"]:
        items = by_category.get(cat, [])
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"  {label}: {len(items)} 份")
    print()
    
    # ── 逐类评分排序 ──
    all_scored = []
    
    for cat in ["tech", "product", "operations", "function"]:
        items = by_category.get(cat, [])
        if not items:
            continue
        
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"{'─'*64}")
        print(f"\n{label} 类候选人评分排序")
        print(f"{'─'*64}")
        print(f"{'排名':<4}{'姓名':<10}{'综合分':<7}{'评级':<16}{'经验':<5}{'学历':<5}{'技能':<5}{'亮点与关注'}")
        print(f"{'-'*64}")
        
        scored = []
        for fname, data in items:
            scores = {
                "experience": score_experience(data),
                "education": score_education(data.get("education", {})),
                "skills": score_skills(data),
                "self_eval": score_self_eval(data),
                "salary_fit": score_salary_fit(data, cat),
            }
            overall = compute_overall(scores)
            highlights, concerns = get_highlights(data, cat)
            
            scored.append({
                "fname": fname,
                "name": data.get("name", "?"),
                "target_position": data.get("target_position", ""),
                "overall": overall,
                "scores": scores,
                "rating": get_rating(overall),
                "highlights": highlights,
                "concerns": concerns,
                "data": data,
            })
        
        # 排序
        scored.sort(key=lambda x: x["overall"], reverse=True)
        
        for rank, s in enumerate(scored, 1):
            name = s["name"]
            score = s["overall"]
            rating = s["rating"].split("（")[0] if "（" in s["rating"] else s["rating"]
            exp = s["scores"]["experience"]
            edu = s["scores"]["education"]
            skill = s["scores"]["skills"]
            highlights_str = "；".join(s["highlights"][:2]) if s["highlights"] else ""
            concerns_str = "；".join(s["concerns"][:2]) if s["concerns"] else ""
            
            extras = []
            if s["highlights"]:
                extras.append(f"✨{highlights_str}")
            if s["concerns"]:
                extras.append(f"⚠️{concerns_str}")
            extra_str = " | ".join(extras)
            
            print(f"{rank:<4}{name:<10}{score:<7}{rating:<16}{exp:<5}{edu:<5}{skill:<5}{extra_str}")
        
        print(f"{'-'*64}")
        print(f"该类共 {len(scored)} 人")
        
        all_scored.extend(scored)
    
    # ── 总体排名 ──
    print(f"\n{'='*72}")
    print(f"🏆 全职能 Top 15（综合评分降序）")
    print(f"{'='*72}")
    print(f"{'排名':<4}{'姓名':<12}{'综合分':<6}{'分类':<12}{'期望职位':<25}{'评级'}")
    print(f"{'-'*72}")
    
    all_scored.sort(key=lambda x: x["overall"], reverse=True)
    for rank, s in enumerate(all_scored[:15], 1):
        fname = s["fname"]
        cat = classify_category(fname)
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"{rank:<4}{s['name']:<12}{s['overall']:<6}{label:<12}{s['target_position']:<25}{s['rating']}")
    print(f"{'-'*72}")
    
    # ── 重点关注候选人 ──
    print(f"\n{'='*72}")
    print(f"⭐ 重点关注候选人（S 级 & A 级）")
    print(f"{'='*72}")
    
    premium = [s for s in all_scored if s["overall"] >= 75]
    if premium:
        for s in sorted(premium, key=lambda x: x["overall"], reverse=True):
            d = s["data"]
            print(f"\n{'─'*48}")
            print(f"  【{s['name']}】 综合分 {s['overall']} | {s['rating']}")
            print(f"  期望职位：{d.get('target_position', '?')}")
            print(f"  期望薪资：{d.get('expected_salary', '?')}")
            print(f"  期望城市：{d.get('expected_city', '?')}")
            exp = d.get("total_experience_years")
            print(f"  工作经验：{exp}年" if exp else "  工作经验：应届/实习")
            edu = d.get("education", {})
            print(f"  教育背景：{edu.get('school','?')} / {edu.get('major','?')} / {edu.get('degree','?')}")
            print(f"  技能标签：{', '.join(d.get('skills', [])[:8])}")
            print(f"  自我评价：{d.get('self_evaluation', '')[:150]}...")
            if s["highlights"]:
                print(f"  亮点：{'；'.join(s['highlights'])}")
            if s["concerns"]:
                print(f"  ⚠️ 关注：{'；'.join(s['concerns'])}")
    else:
        print("  （无 S/A 级候选人）")
    
    # ── 需人工复核的候选人 ──
    print(f"\n{'='*72}")
    print(f"🔍 建议人工复核（存在关注事项）")
    print(f"{'='*72}")
    flagged = [s for s in all_scored if s["concerns"] and s["overall"] >= 50]
    if flagged:
        for s in flagged[:10]:
            fname = s["fname"]
            cat = classify_category(fname)
            label = CATEGORY_LABELS.get(cat, cat)
            print(f"  [{label}] {s['name']} ({s['overall']}分) — {s['target_position']}")
            for c in s["concerns"]:
                print(f"    ⚠️ {c}")
    else:
        print("  （无特殊关注事项）")
    
    # ── 合规声明 ──
    print(f"\n{'─'*64}")
    print("📜 合规声明：")
    print("  • 以上为 AI 辅助评分排序建议，最终录用/淘汰决定由人工 HR 做出。")
    print("  • 评分过程未使用年龄、性别、婚育、籍贯、民族等敏感个人信息。")
    print("  • 依据：个人信息保护法第 24 条 / Workday Mobley 判例。")
    print(f"{'─'*64}")
    
    # ── 保存结果 ──
    out_path = os.path.join(WORKSPACE, "scoring/results/screening-week-2026-05-16.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    output = {
        "report_date": str(date.today()),
        "week_range": [str(WEEK_START), str(WEEK_END)],
        "total_received": len(candidates),
        "by_category": {
            cat: {"count": len(items), "label": CATEGORY_LABELS.get(cat, cat)}
            for cat, items in by_category.items()
        },
        "top_overall": [
            {
                "rank": i + 1,
                "name": s["name"],
                "overall_score": s["overall"],
                "category": classify_category(s["fname"]),
                "target_position": s["target_position"],
                "rating": s["rating"],
                "highlights": s["highlights"],
                "concerns": s["concerns"],
                "detail_scores": s["scores"],
            }
            for i, s in enumerate(all_scored[:15])
        ],
        "full_ranking": [
            {
                "name": s["name"],
                "category": classify_category(s["fname"]),
                "overall_score": s["overall"],
                "rating": s["rating"],
                "detail_scores": s["scores"],
                "highlights": s["highlights"],
                "concerns": s["concerns"],
                "target_position": s["target_position"],
                "expected_salary": s["data"].get("expected_salary", ""),
                "expected_city": s["data"].get("expected_city", ""),
                "total_experience_years": s["data"].get("total_experience_years"),
            }
            for s in all_scored
        ],
        "compliance_note": "以上为 AI 辅助评分排序建议。评分未使用年龄、性别、婚育、籍贯等敏感信息（个保法24条/Workday Mobley判例）。"
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 完整结果已保存至: scoring/results/screening-week-2026-05-16.json")

if __name__ == "__main__":
    main()
