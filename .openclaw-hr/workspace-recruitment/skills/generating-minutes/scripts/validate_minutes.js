#!/usr/bin/env node
/**
 * validate_minutes.js — 结构化面试纪要校验器
 *
 * 用途：generating-minutes Skill 的校验闭环。gen_minutes.py 产出纪要
 *       JSON 后，用本脚本校验，跑通才算纪要合格。把"纪要结构齐不齐、
 *       数字回核有没有真做"这件确定性的事从 LLM 手里收回到脚本里。
 *
 * 为什么需要这一道闸：面试纪要是 HR 做面试决策的依据。一份缺了评分
 * 建议、或关键问答不是"面试官—候选人"两行结构、或数字回核根本没跑的
 * 纪要，交到 HR 手里就是误导。LLM 自己"读一遍觉得完整"判断不了这些
 * 结构性缺失——校验器把标准固定下来。
 *
 * 校验项：
 *   1. JSON 可解析
 *   2. 必需字段齐全：candidate / position / qa / strengths /
 *      concerns / recommendation / mentioned_numbers / number_audit_summary
 *   3. qa 非空，每组含 topic / question / answer —— 这是"按发言人组织"
 *      的结构保证：每组关键问答都要有面试官问题 + 候选人回答两条
 *   4. recommendation 含 verdict（取值在 通过/待定/不通过 内）+ reason
 *   5. 数字回核闭环：number_audit_summary 的 total 等于 mentioned_numbers
 *      条数，traceable + needs_review 等于 total —— 回核统计自洽，
 *      证明回核脚本真的逐项跑过，不是 LLM 编一个摘要
 *   6. 每个 mentioned_numbers 条目带 audit 字段（回核结论）
 *
 * CLI：node validate_minutes.js <minutes.json>
 *   退出码 0 = 校验通过；1 = 校验失败（stderr 列出全部问题）；2 = 用法错误
 */

'use strict';
const fs = require('fs');

const VALID_VERDICTS = ['通过', '待定', '不通过'];

function fail(problems) {
  console.error('❌ 面试纪要校验未通过：');
  problems.forEach((p, i) => console.error(`  ${i + 1}. ${p}`));
  process.exit(1);
}

function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('用法: node validate_minutes.js <minutes.json>');
    process.exit(2);
  }
  if (!fs.existsSync(file)) {
    console.error(`ERROR: 文件不存在: ${file}`);
    process.exit(2);
  }

  let m;
  try {
    m = JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (e) {
    fail([`JSON 无法解析: ${e.message}`]);
  }

  const problems = [];

  // 2. 必需字段
  const required = ['candidate', 'position', 'qa', 'strengths', 'concerns',
    'recommendation', 'mentioned_numbers', 'number_audit_summary'];
  required.forEach((k) => {
    if (!(k in m)) problems.push(`缺少必需字段: ${k}`);
  });
  if (problems.length > 0) fail(problems);

  // 3. qa 结构：每组要有 topic/question/answer（按发言人组织的保证）
  if (!Array.isArray(m.qa) || m.qa.length === 0) {
    problems.push('qa 为空——纪要没有关键问答');
  } else {
    m.qa.forEach((qa, idx) => {
      ['topic', 'question', 'answer'].forEach((k) => {
        if (!qa[k] || String(qa[k]).trim() === '') {
          problems.push(`qa[${idx}] 缺少或留空字段: ${k}`
            + `（关键问答必须是"面试官问题—候选人回答"两行结构）`);
        }
      });
    });
  }

  // 4. recommendation
  const rec = m.recommendation || {};
  if (!VALID_VERDICTS.includes(rec.verdict)) {
    problems.push(
      `recommendation.verdict 取值非法: "${rec.verdict}"`
      + `（必须是 ${VALID_VERDICTS.join(' / ')} 之一）`);
  }
  if (!rec.reason || String(rec.reason).trim() === '') {
    problems.push('recommendation.reason 缺失——评分建议必须附理由');
  }

  // 5-6. 数字回核闭环自洽
  const nums = m.mentioned_numbers;
  const sm = m.number_audit_summary || {};
  if (!Array.isArray(nums)) {
    problems.push('mentioned_numbers 不是数组');
  } else {
    if (sm.total !== nums.length) {
      problems.push(
        `number_audit_summary.total (${sm.total}) 与 mentioned_numbers `
        + `条数 (${nums.length}) 不一致——数字回核统计与实际不符，`
        + `回核可能没真跑`);
    }
    if (typeof sm.traceable === 'number'
        && typeof sm.needs_review === 'number'
        && sm.traceable + sm.needs_review !== sm.total) {
      problems.push(
        `number_audit_summary 不自洽: traceable(${sm.traceable}) `
        + `+ needs_review(${sm.needs_review}) ≠ total(${sm.total})`);
    }
    nums.forEach((n, idx) => {
      if (!('audit' in n)) {
        problems.push(`mentioned_numbers[${idx}] 缺 audit 字段`
          + `——该口述数字没有回核结论`);
      }
    });
  }

  if (problems.length > 0) fail(problems);

  console.log('✅ 面试纪要校验通过');
  console.log(`   候选人: ${m.candidate}  岗位: ${m.position}`);
  console.log(`   关键问答: ${m.qa.length} 组（均含面试官问题+候选人回答）`);
  console.log(`   优势 ${m.strengths.length}  待考察 ${m.concerns.length}`
    + `  高亮 ${(m.highlights || []).length}`);
  console.log(`   数字回核: ${sm.traceable}/${sm.total} 可追溯，`
    + `${sm.needs_review} 需人工核实`);
  console.log(`   评分建议: ${rec.verdict}`);
  process.exit(0);
}

main();
