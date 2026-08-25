#!/usr/bin/env node
/**
 * batch_rank.js — 批量评分一批候选人 + 按综合分排序
 *
 * 用途：scoring-candidates Skill 的批量入口。对一个 JD，批量评分一个目录
 *       下的多份脱敏候选人 JSON，全部评完按综合匹配分降序排序，产出
 *       初筛排序结果。对应场景 1「上午集中筛简历」——HR 把一批简历丢进来，
 *       拿到排序好的候选人。
 *
 * 关键纪律（移植自 batch_score.py 踩过的坑）：
 *   LLM 输出非确定性，批量任务偶发失败是常态。每份候选人最多评 3 次，
 *   3 次全失败则【显式标记为待人工处理】，绝不静默丢弃——招聘场景
 *   漏掉一个候选人是事故。宁可重试、不可漏人。
 *
 * 合规边界：只产出评分与排序【建议】，每个候选人标"建议动作"而非
 *   "淘汰/通过"——最终录用/淘汰决定由人工 HR 做（个保法 24 条 +
 *   Workday Mobley 判例）。
 *
 * 输入候选人 JSON 必须是【脱敏后】的（经 filtering-sensitive-fields 处理）。
 *
 * CLI：node batch_rank.js <JD-md> <脱敏候选人json目录> [输出json] [文件名前缀]
 *   文件名前缀可选——只评目录里匹配该前缀的 json（默认评全部 .json）。
 *   退出码 0 = 批量完成（即使有个别候选人失败也算完成，失败已标记）；
 *           2 = 文件/用法问题。
 */

'use strict';
const fs = require('fs');
const path = require('path');
const { scoreCandidate } = require('./score_candidate.js');

/** 按综合分给一个候选人定建议动作。只给建议，不做淘汰决定。 */
function suggestedAction(score) {
  if (score.hard_issues && score.hard_issues.length) {
    return '建议人工复核简历硬伤后再定';
  }
  const s = Number(score.jd_match_score);
  if (s >= 80) return '建议优先安排面试';
  if (s >= 60) return '建议进入面试候选名单';
  return '建议人工复核是否纳入';
}

async function main() {
  const [, , jdFile, candDir, outPath, prefix] = process.argv;
  if (!jdFile || !candDir) {
    console.error(
      '用法: node batch_rank.js <JD-md> <脱敏候选人json目录> [输出json] [文件名前缀]'
    );
    process.exit(2);
  }
  if (!fs.existsSync(jdFile)) {
    console.error(`JD 文件不存在: ${jdFile}`);
    process.exit(2);
  }
  if (!fs.existsSync(candDir) || !fs.statSync(candDir).isDirectory()) {
    console.error(`候选人目录不存在: ${candDir}`);
    process.exit(2);
  }
  if (!process.env.DEEPSEEK_API_KEY) {
    console.error('环境变量 DEEPSEEK_API_KEY 未设置');
    process.exit(2);
  }

  const jdText = fs.readFileSync(jdFile, 'utf8');
  const jdName = path.basename(jdFile);
  const files = fs
    .readdirSync(candDir)
    .filter((f) => f.endsWith('.json') && (!prefix || f.startsWith(prefix)))
    .sort();

  console.log(`📊 批量评分 · scoring-candidates`);
  console.log(`   JD：${jdName}`);
  console.log(`   候选人池：${files.length} 份${prefix ? `（前缀 ${prefix}）` : ''}\n`);

  const results = [];
  const failed = [];

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const full = path.join(candDir, f);
    console.log(`--- [${i + 1}/${files.length}] ${f} ---`);
    let candidate;
    try {
      candidate = JSON.parse(fs.readFileSync(full, 'utf8'));
    } catch (e) {
      console.log(`  ✗ JSON 无法解析，标记待人工处理：${e.message}`);
      failed.push(f);
      continue;
    }
    // 每份最多评 3 次——批量初筛不能因偶发故障漏掉候选人
    let score = null;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        score = await scoreCandidate(candidate, jdText, jdName);
        break;
      } catch (e) {
        console.log(`  第 ${attempt} 次评分失败：${e.message}`);
        if (attempt < 3) console.log('  重试中 ...');
      }
    }
    if (!score) {
      console.log('  ✗ 3 次均失败，标记为待人工处理（不静默丢弃）');
      failed.push(f);
      continue;
    }
    const action = suggestedAction(score);
    console.log(
      `  综合分 ${score.jd_match_score} | 评级 ${score.overall_rating}` +
        `${score.hard_issues && score.hard_issues.length ? ' | ⚠硬伤 ' + JSON.stringify(score.hard_issues) : ''}` +
        ` | ${action}`
    );
    results.push({
      resume_json: f,
      name: score.candidate_name || candidate.name || f,
      score,
      suggested_action: action,
    });
  }

  // ── 按综合匹配分降序排序 ────────────────────────────────────
  results.sort((a, b) => b.score.jd_match_score - a.score.jd_match_score);

  console.log(`\n${'='.repeat(60)}`);
  console.log(`初筛排序结果（按综合匹配分降序）—— ${jdName}`);
  console.log('='.repeat(60));
  const ranking = results.map((r, idx) => {
    const s = r.score;
    const hard = s.hard_issues && s.hard_issues.length ? '有' : '—';
    console.log(
      `  ${idx + 1}. ${r.name}  综合分 ${s.jd_match_score}  ` +
        `评级 ${s.overall_rating.split('(')[0]}  硬伤 ${hard}  ${r.suggested_action}`
    );
    return {
      rank: idx + 1,
      name: r.name,
      resume_json: r.resume_json,
      jd_match_score: s.jd_match_score,
      overall_rating: s.overall_rating,
      hard_issues: s.hard_issues || [],
      suggested_action: r.suggested_action,
      score_reasoning: s.score_reasoning,
    };
  });
  console.log('='.repeat(60));
  if (failed.length) {
    console.log(
      `⚠ ${failed.length} 份评分未成功，已标记待人工处理（不静默丢弃）：`
    );
    failed.forEach((f) => console.log(`   - ${f}`));
  }
  console.log(
    '说明：以上为 AI 评分与排序【建议】，最终淘汰/录用决定由人工 HR 做。'
  );
  console.log('      依据：个人信息保护法第 24 条 / Workday Mobley 判例。');

  if (outPath) {
    const payload = {
      jd: jdName,
      candidate_count: results.length,
      failed_candidates: failed,
      ranking,
      details: results,
    };
    fs.writeFileSync(outPath, JSON.stringify(payload, null, 2), 'utf8');
    console.log(`\n完整结果已保存：${outPath}`);
  }
  process.exit(0);
}

if (require.main === module) main();
