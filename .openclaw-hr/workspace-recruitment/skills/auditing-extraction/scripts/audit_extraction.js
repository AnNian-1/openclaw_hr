#!/usr/bin/env node
/**
 * audit_extraction.js — 简历解析产出的「真实性核对」核对器
 *
 * 用途：auditing-extraction Skill 的核对闭环。把 parsing-resumes 抽出的候选人 JSON
 *       逐字段回溯到简历原文——这是「内容真不真」的核对，与 validate_profile.js
 *       的「形状对不对」（schema/合规结构校验）是两件不同的事。
 *
 *   validate_profile.js  →  字段组齐不齐、红线字段在不在、派生字段自不自洽
 *   audit_extraction.js  →  每个抽取值能不能逐字回溯到简历原文（本脚本）
 *
 * 核对方法（对齐 L2-1 §2.4「13 字段抽样可追溯」）：
 *   1. 硬提取字段——值必须能在简历原文里逐字符找到出处（normalize 后子串匹配）。
 *      对不上 = 疑似 LLM 补全 / 笔误 / 张冠李戴，必须人工核实。
 *   2. 软推断字段——原文没有直接出处（如 industry 从公司名推断）。核对标准不是
 *      「找出处」，而是：① 必须带 `_inferred` 标志显式标注；② 推断依据（公司名）
 *      本身要能在原文找到。漏标注 = 把 AI 判断混成简历事实，必须报。
 *   3. 派生字段——total_experience_years / job_count 不回溯原文，确认其计算依据
 *      （work_experience 各段）在原文成立即可。
 *
 * 产出：逐字段核对表 + 可追溯率，写到 audited/<简历名>.audit.json，并打印摘要。
 *
 * CLI：node audit_extraction.js <parsed.json> <resume.md>
 *   退出码 0 = 全部字段可追溯 / 推断字段已合规标注；
 *           1 = 存在对不上原文的硬字段，或软推断字段漏标注（stderr 列出）；
 *           2 = 用法错误 / 文件不存在。
 */

'use strict';
const fs = require('fs');
const path = require('path');

// ── 字段分类。来源：candidate-profile-schema.md §7（硬提取 vs 软推断）。
//    硬提取字段——值在简历原文有明确出处，核对标准是逐字符比对。
const HARD_TOP_FIELDS = [
  'name', 'phone', 'email', 'target_position',
  'expected_salary', 'expected_city', 'available_date',
];
const HARD_EDU_FIELDS = ['school', 'major', 'degree'];
const HARD_WORK_FIELDS = ['company', 'position'];
// 软推断字段——原文无直接出处，靠上下文推导，必须带 <字段>_inferred 标志。
const SOFT_WORK_FIELDS = ['industry'];
// 派生字段——按 work_experience 计算，不回溯原文出处。
const DERIVED_FIELDS = ['total_experience_years', 'job_count'];

/**
 * 文本归一化：去掉空白、全角/半角差异、常见标点，统一小写。
 * 简历原文常有换行截断（一句话被拆成两行）、全角括号——归一化后再做子串匹配，
 * 避免「值确实来自原文、只是排版不同」被误判成对不上。
 */
function norm(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/\s+/g, '')
    .replace(/[（）]/g, (c) => (c === '（' ? '(' : ')'))
    .replace(/[—–~～－]/g, '-')
    .replace(/[：]/g, ':')
    .toLowerCase();
}

/**
 * 抽取值能否逐字回溯到原文。
 *
 * 核对一个硬提取字段，先看整串是否原文出现；不出现，再看「主体部分」——
 * 即去掉括号补充说明后的核心值——是否出现。原因：target_position
 * "算法工程师（推荐 / NLP / 大模型应用方向）" 整串未必在原文同一处连续出现，
 * 但主体 "算法工程师" 一定要能找到，找不到这个字段就不可信。
 *
 * 关键点：**括号里的补充项不能单独让整个值通过核对**。
 * 比如 expected_salary 被改成 "30K-40K（月薪）"，「月薪」二字确实在原文里，
 * 但核心值 "30K-40K" 是编造的——只要核心值对不上，整个字段就判不可追溯。
 * 这正是「真实性核对」要抓的编造，不能被括号里的通用词放水。
 */
function traceable(value, normSource) {
  const raw = String(value).trim();
  // 整串命中——最强证据
  if (normSource.includes(norm(raw))) return true;
  // 否则核对「主体部分」：去掉所有括号补充说明后的核心值
  const primary = raw.replace(/[（(][^）)]*[）)]/g, '').trim();
  if (primary && primary !== raw) {
    return normSource.includes(norm(primary));
  }
  return false;
}

/** 起止时间专门核对：2021-07 在原文可能写成 2021.07 / 2021/07 / 2021年7月。 */
function traceableDate(value, normSource) {
  const m = String(value).match(/(\d{4})\D*(\d{1,2})?/);
  if (!m) return traceable(value, normSource);
  const y = m[1];
  if (/至今|今|present|now/i.test(String(value))) {
    return normSource.includes('至今') || normSource.includes(norm(value));
  }
  // 年份必须出现；有月份则月份也要出现（容忍 07 / 7 两种写法）
  if (!normSource.includes(y)) return false;
  if (m[2]) {
    const mm = String(parseInt(m[2], 10));
    const mm2 = mm.padStart(2, '0');
    return normSource.includes(mm) || normSource.includes(mm2);
  }
  return true;
}

function main() {
  const parsedFile = process.argv[2];
  const resumeFile = process.argv[3];
  if (!parsedFile || !resumeFile) {
    console.error('用法: node audit_extraction.js <parsed.json> <resume.md>');
    process.exit(2);
  }
  for (const f of [parsedFile, resumeFile]) {
    if (!fs.existsSync(f)) {
      console.error(`文件不存在: ${f}`);
      process.exit(2);
    }
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(parsedFile, 'utf8'));
  } catch (e) {
    console.error(`parsed JSON 无法解析：${e.message}`);
    process.exit(2);
  }
  const source = fs.readFileSync(resumeFile, 'utf8');
  const normSource = norm(source);

  // checks: 每项 { field, type: hard|soft|derived, value, ok, note }
  const checks = [];
  const push = (field, type, value, ok, note) =>
    checks.push({ field, type, value: String(value), ok, note });

  // ── 1. 硬提取顶层字段
  for (const k of HARD_TOP_FIELDS) {
    if (!(k in data) || data[k] === null || data[k] === '') continue;
    const ok = traceable(data[k], normSource);
    push(k, 'hard', data[k], ok,
      ok ? '逐字回溯到原文' : '在简历原文找不到出处，疑似编造/笔误，需人工核实');
  }

  // ── 1b. 硬提取教育字段
  if (data.education && typeof data.education === 'object') {
    for (const k of HARD_EDU_FIELDS) {
      const v = data.education[k];
      if (!v) continue;
      const ok = traceable(v, normSource);
      push(`education.${k}`, 'hard', v, ok,
        ok ? '逐字回溯到原文' : '在简历原文找不到出处，需人工核实');
    }
  }

  // ── 1c/2/3. 工作经历：硬字段回溯 + 软推断字段标注核对 + 起止时间
  if (Array.isArray(data.work_experience)) {
    data.work_experience.forEach((job, i) => {
      for (const k of HARD_WORK_FIELDS) {
        if (!job[k]) continue;
        const ok = traceable(job[k], normSource);
        push(`work_experience[${i}].${k}`, 'hard', job[k], ok,
          ok ? '逐字回溯到原文' : '在简历原文找不到出处，需人工核实');
      }
      for (const k of ['start_date', 'end_date']) {
        if (!job[k]) continue;
        const ok = traceableDate(job[k], normSource);
        push(`work_experience[${i}].${k}`, 'hard', job[k], ok,
          ok ? '起止时间回溯到原文' : '起止时间在原文找不到，需人工核实');
      }
      // 软推断字段：① 必须带 _inferred 标志；② 推断依据（公司名）要能回溯
      for (const k of SOFT_WORK_FIELDS) {
        if (!(k in job) || !job[k]) continue;
        const flagKey = `${k}_inferred`;
        const flagged = job[flagKey] === true;
        const basisOk = job.company ? traceable(job.company, normSource) : false;
        const ok = flagged && basisOk;
        let note;
        if (!flagged) {
          note = `软推断字段缺 "${flagKey}": true 标志——未标注就分不清这是 AI 判断还是简历事实`;
        } else if (!basisOk) {
          note = `已标注推断，但推断依据（公司名）在原文找不到，推断依据不成立`;
        } else {
          note = `已标注 ${flagKey}，推断依据（公司名）成立`;
        }
        push(`work_experience[${i}].${k}`, 'soft', job[k], ok, note);
      }
    });
  }

  // ── 3b. 派生字段：确认计算依据成立（work_experience 在场即可）
  for (const k of DERIVED_FIELDS) {
    if (!(k in data)) continue;
    const we = Array.isArray(data.work_experience) ? data.work_experience : [];
    const ok = we.length > 0;
    push(k, 'derived', data[k], ok,
      ok ? `派生字段，计算依据为 ${we.length} 段 work_experience，依据成立`
         : '派生字段但缺 work_experience，计算依据不成立');
  }

  // ── 统计
  const hard = checks.filter((c) => c.type === 'hard');
  const soft = checks.filter((c) => c.type === 'soft');
  const derived = checks.filter((c) => c.type === 'derived');
  const hardOk = hard.filter((c) => c.ok).length;
  const softOk = soft.filter((c) => c.ok).length;
  const derivedOk = derived.filter((c) => c.ok).length;
  const failed = checks.filter((c) => !c.ok);
  const traceRate = hard.length ? ((hardOk / hard.length) * 100).toFixed(1) : '100.0';

  // ── 写核对报告
  const report = {
    parsed_file: path.basename(parsedFile),
    resume_file: path.basename(resumeFile),
    candidate: data.name || '(未知)',
    audited_at: new Date().toISOString(),
    summary: {
      hard_fields: `${hardOk}/${hard.length}`,
      soft_fields: `${softOk}/${soft.length}`,
      derived_fields: `${derivedOk}/${derived.length}`,
      hard_traceability_rate: `${traceRate}%`,
      passed: failed.length === 0,
    },
    checks,
  };
  // 核对报告写到 workspace 的 audited/ 目录。简历在 inbox/<name>.md，
  // 其上两级就是 workspace 根——以此定位，不依赖 parsed 文件的目录深度。
  const outDir = path.resolve(path.dirname(resumeFile), '..', 'audited');
  let outPath = null;
  try {
    fs.mkdirSync(outDir, { recursive: true });
    outPath = path.join(outDir, path.basename(parsedFile).replace(/\.json$/, '.audit.json'));
    fs.writeFileSync(outPath, JSON.stringify(report, null, 2), 'utf8');
  } catch (e) {
    // 写报告失败不阻塞核对结论，仅提示
    outPath = `(报告写入失败: ${e.message})`;
  }

  // ── 打印摘要
  console.log(`📋 真实性核对 · ${report.candidate}（${report.parsed_file}）`);
  console.log(`   硬提取字段: ${hardOk}/${hard.length} 可逐字回溯  追溯率 ${traceRate}%`);
  console.log(`   软推断字段: ${softOk}/${soft.length} 已合规标注且依据成立`);
  console.log(`   派生字段:   ${derivedOk}/${derived.length} 计算依据成立`);
  console.log(`   核对报告:   ${outPath}`);

  if (failed.length) {
    console.error('');
    console.error(`❌ 真实性核对未通过——${failed.length} 处字段有问题：`);
    failed.forEach((c, i) => {
      console.error(`  ${i + 1}. [${c.type}] ${c.field} = "${c.value}"`);
      console.error(`     ${c.note}`);
    });
    process.exit(1);
  }

  console.log('');
  console.log('✅ 真实性核对通过——所有硬提取字段可逐字回溯，软推断字段已合规标注。');
  process.exit(0);
}

main();
