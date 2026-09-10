#!/usr/local/miniconda3/envs/py312/bin python3
"""Parse the new 360 feedback DOCX into individual JSON files for yuangong1."""
import json, re, os, glob
from docx import Document

DOCX_PATH = "/opt/openclaw-hr/.openclaw-hr/media/inbound/新建_Microsoft_Word_文档---ad8ff307-5089-4d94-aac9-d57050233b05.docx"
OUT_DIR = "/opt/openclaw-hr/.openclaw-hr/workspace-performance/feedback-360/source_feedback/yuangong1"

doc = Document(DOCX_PATH)
all_text = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

# Split into samples by "样本 N" pattern
samples, current = [], []
for line in all_text:
    if re.match(r'^样本\s*\d+', line):
        if current:
            samples.append(current)
        current = [line]
    else:
        current.append(line)
if current:
    samples.append(current)

print(f"Found {len(samples)} samples")

DIMENSIONS = ['goal_achievement', 'professional_skill', 'collaboration', 'responsibility', 'growth']
DIM_CN = ['目标达成', '专业能力', '协作沟通', '责任心', '学习成长']
RELATION_MAP = {'上级': 'manager', '平级同事': 'peer', '平级': 'peer', '下属': 'report', '本人自评': 'self', '自评': 'self'}

FW_PIPE = '｜'  # U+FF5C
FW_COLON = '：'  # U+FF1A

def parse_sample(lines):
    header = lines[0]
    # Use fullwidth separators
    parts = re.split(r'｜', header)
    # parts: ['样本 N', '被评估人：员工 1', '评估人：领导 1', '关系：上级', '考核周期：2026H1']
    field = {}
    for part in parts:
        m = re.match(r'(.+?)：(.+)', part)
        if m:
            field[m.group(1).strip()] = m.group(2).strip()

    subject = field.get('被评估人', '员工1').replace(' ', '')
    reviewer = field.get('评估人', '未知').replace(' ', '')
    relation_raw = field.get('关系', '未知')
    period = field.get('考核周期', '2026-H1').replace(' ', '')
    relation = RELATION_MAP.get(relation_raw, 'peer')

    scores = {}
    comments = {}
    strengths = ""
    improvements = ""

    i = 1
    while i < len(lines):
        line = lines[i]
        # Score line: "1. 目标达成｜评分：4（超出预期）"
        m_score = re.match(r'^\d+\.\s*(.+?)｜评分：(\d+)', line)
        if m_score:
            dim_cn = m_score.group(1).strip()
            score = int(m_score.group(2))
            dim_key = None
            for j, d in enumerate(DIM_CN):
                if d in dim_cn:
                    dim_key = DIMENSIONS[j]
                    break
            if dim_key:
                scores[dim_key] = score
            # Collect comment lines until next score or 总体印象
            comment_lines = []
            i += 1
            while i < len(lines) and not re.match(r'^\d+\.', lines[i]) and not lines[i].startswith('总体印象') and not lines[i].startswith('主要亮点'):
                comment_lines.append(lines[i])
                i += 1
            if dim_key:
                comments[dim_key] = ' '.join(comment_lines).strip()
            continue

        # Overall section
        if line.startswith('总体印象') or line.startswith('主要亮点'):
            overall_lines = []
            if line.startswith('主要亮点'):
                overall_lines.append(line)
            j = i + 1
            while j < len(lines) and not re.match(r'^样本\s*\d+', lines[j]):
                overall_lines.append(lines[j])
                j += 1
            overall_block = ' '.join(overall_lines)
            m_overall = re.search(r'主要亮点：\s*(.+?)(?=\s*改进建议)', overall_block)
            m_improve = re.search(r'改进建议：\s*(.+?)$', overall_block)
            if m_overall:
                strengths = m_overall.group(1).strip().rstrip('。')
            if m_improve:
                improvements = m_improve.group(1).strip().rstrip('。')
            i = j
            continue
        i += 1

    data = {
        "subject": subject,
        "subject_role": "支付平台研发组 后端开发工程师",
        "period": period,
        "reviewer_relation": relation,
        "reviewer_alias": reviewer,
        "submitted_at": "2026-06-28",
        "scores": scores,
        "comments": comments,
        "strengths": strengths,
        "improvements": improvements,
        "feedback_id": f"fb-360-yuangong1-2026h1-{relation}"
    }
    return data

# Parse all
parsed = [parse_sample(s) for s in samples]
for d in parsed:
    print(f"  {d['reviewer_alias']} ({d['reviewer_relation']}): scores={d['scores']}")

# Clear old files
for f in glob.glob(os.path.join(OUT_DIR, '*.json')):
    os.remove(f)
for f in ['aggregated-data.json', 'aggregated-report.md', 'report.html']:
    fp = os.path.join(OUT_DIR, f)
    if os.path.exists(fp):
        os.remove(fp)

# Write files with correct names
name_counters = {}
for data in parsed:
    rel = data['reviewer_relation']
    if rel == 'manager':
        fname = 'manager.json'
    elif rel == 'self':
        fname = 'self.json'
    elif rel == 'peer':
        name_counters['peer'] = name_counters.get('peer', 0) + 1
        fname = f"peer-{name_counters['peer']:02d}.json"
    elif rel == 'report':
        name_counters['report'] = name_counters.get('report', 0) + 1
        fname = f"report-{name_counters['report']:02d}.json"
    else:
        fname = f"{rel}-01.json"
    outpath = os.path.join(OUT_DIR, fname)
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Written: {fname}")

print(f"\nDone. {len(parsed)} files written to {OUT_DIR}")
