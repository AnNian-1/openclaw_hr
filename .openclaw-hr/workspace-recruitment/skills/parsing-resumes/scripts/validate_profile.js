#!/usr/bin/env node
/**
 * validate_profile.js — 候选人结构化 JSON 校验器
 *
 * 用途：parsing-resumes Skill 的校验闭环。Agent 抽取出候选人 JSON 后，
 *       用本脚本校验，跑通才算解析合格。把"对齐 schema"这件确定性的事
 *       从 LLM 手里收回到脚本里——LLM 负责抽取，脚本负责把关。
 *
 * 校验项（对齐 candidate-profile-schema.md）：
 *   1. JSON 可解析
 *   2. 必需字段组齐全：基础信息 / education / work_experience / skills
 *   3. 合规红线字段零出现（schema §9：年龄/出生日期/性别/婚育/户籍/民族/健康）
 *   4. 派生字段 total_experience_years / job_count 与 work_experience 自洽
 *   5. work_experience 每段含 company/position/start_date/end_date
 *
 * CLI：node validate_profile.js <profile.json>
 *   退出码 0 = 校验通过；1 = 校验失败（stderr 列出全部问题）；2 = 用法错误
 */

'use strict';
const fs = require('fs');

// 合规红线字段黑名单。来源：candidate-profile-schema.md §9，
// 依据《个人信息保护法》第 24 条、《就业促进法》第 26-31 条。
// 这些字段可记录于画像，但绝不能进入结构化解析产出的核心字段。
const FORBIDDEN_KEYS = [
  'age', 'birth', 'birthday', 'birthdate', 'date_of_birth',
  'gender', 'sex',
  'marriage', 'marital', 'marital_status', 'children',
  'hukou', 'household', 'native_place', 'birthplace', 'origin',
  'ethnicity', 'nation', 'race',
  'health', 'disability',
  // 中文键名也一并拦截
  '年龄', '出生', '性别', '婚育', '婚姻', '户籍', '籍贯', '民族', '健康',
];

// schema 要求的字段组。基础信息字段平铺在顶层，其余为对象/数组。
const REQUIRED_TOP_FIELDS = ['name', 'target_position'];
const REQUIRED_GROUPS = ['education', 'work_experience', 'skills'];

function fail(problems) {
  console.error('❌ 候选人 JSON 校验未通过：');
  problems.forEach((p, i) => console.error(`  ${i + 1}. ${p}`));
  process.exit(1);
}

/**
 * 按一段工作经历的起止时间算月数。
 * start/end 形如 "2022-10" / "2021.07"；end 为 "至今" 用当前年月。
 * 返回月数；无法解析返回 null。
 */
function monthsOf(start, end) {
  const parse = (s) => {
    if (!s) return null;
    if (/^(至今|今|present|now)/i.test(String(s))) {
      const d = new Date();
      return [d.getFullYear(), d.getMonth() + 1];
    }
    const m = String(s).match(/(\d{4})[.\-/年]?\s*(\d{1,2})?/);
    if (!m) return null;
    return [parseInt(m[1], 10), m[2] ? parseInt(m[2], 10) : 1];
  };
  const s = parse(start);
  const e = parse(end);
  if (!s || !e) return null;
  return (e[0] - s[0]) * 12 + (e[1] - s[1]);
}

function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('用法: node validate_profile.js <profile.json>');
    process.exit(2);
  }
  if (!fs.existsSync(file)) {
    console.error(`文件不存在: ${file}`);
    process.exit(2);
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (e) {
    fail([`JSON 无法解析：${e.message}`]);
  }

  const problems = [];

  // 1. 必需顶层字段
  for (const k of REQUIRED_TOP_FIELDS) {
    if (!data[k]) problems.push(`缺少必需字段 ${k}`);
  }
  // 2. 必需字段组
  for (const g of REQUIRED_GROUPS) {
    if (!(g in data)) problems.push(`缺少必需字段组 ${g}`);
  }

  // 3. 合规红线字段扫描——递归扫所有层级的 key
  const hits = [];
  (function scan(obj, path) {
    if (obj === null || typeof obj !== 'object') return;
    if (Array.isArray(obj)) {
      obj.forEach((v, i) => scan(v, `${path}[${i}]`));
      return;
    }
    for (const key of Object.keys(obj)) {
      const lower = key.toLowerCase();
      if (FORBIDDEN_KEYS.some((bad) => lower === bad || lower.includes(bad))) {
        hits.push(`${path}${path ? '.' : ''}${key}`);
      }
      scan(obj[key], `${path}${path ? '.' : ''}${key}`);
    }
  })(data, '');
  if (hits.length) {
    problems.push(
      `出现合规红线字段（schema §9 禁止）：${hits.join(', ')}。` +
        `年龄/性别/婚育/户籍/民族/健康属个保法敏感信息，不得进入结构化解析产出。`
    );
  }

  // 4. 派生字段与 work_experience 自洽
  if (Array.isArray(data.work_experience)) {
    const we = data.work_experience;
    if ('job_count' in data && data.job_count !== we.length) {
      problems.push(
        `job_count=${data.job_count} 与 work_experience 实际段数 ${we.length} 不一致`
      );
    }

    // 4b. total_experience_years 必须按起止时间客观算出，不能取简历自述值。
    //     脚本自己按各段起止时间累加月数，和 JSON 里的值比对——
    //     这是把"派生字段以客观数据为准"从规则升级成脚本裁判（schema §6）。
    //     allowedDiff=1：留 1 年容差吸收"段间空窗/重叠""按年取整"的正常误差。
    if ('total_experience_years' in data && we.length > 0) {
      let totalMonths = 0;
      let computable = true;
      for (const job of we) {
        const m = monthsOf(job.start_date, job.end_date);
        if (m === null) {
          computable = false;
          break;
        }
        totalMonths += Math.max(0, m);
      }
      if (computable) {
        const computedYears = totalMonths / 12;
        const claimed = Number(data.total_experience_years);
        const allowedDiff = 1;
        if (Math.abs(computedYears - claimed) > allowedDiff) {
          problems.push(
            `total_experience_years=${claimed} 与按起止时间累加算出的 ` +
              `${computedYears.toFixed(1)} 年偏差过大（>${allowedDiff} 年）。` +
              `派生字段须以起止时间为准，不能取简历自述值——求职者自述年限可能笔误或写长。`
          );
        }
      }
    }
    // 5. 每段经历字段完整性
    we.forEach((job, i) => {
      ['company', 'position', 'start_date', 'end_date'].forEach((f) => {
        if (!job[f]) {
          problems.push(`work_experience[${i}] 缺少字段 ${f}`);
        }
      });
      // 6. 软推断字段必须显式标注。industry 是从公司名推断的软推断字段，
      //    产出了 industry 就必须同时带 industry_inferred 标志，否则下游
      //    分不清这是简历事实还是 AI 判断（schema §7 提取 vs 推断）。
      if ('industry' in job && job.industry) {
        if (job.industry_inferred !== true) {
          problems.push(
            `work_experience[${i}] 产出了 industry="${job.industry}" ` +
              `但缺少 "industry_inferred": true 标志。` +
              `industry 是软推断字段，必须显式标注，不能与简历事实混为一谈。`
          );
        }
      }
    });
  }

  if (problems.length) fail(problems);

  // 通过——输出体检摘要
  const we = Array.isArray(data.work_experience) ? data.work_experience : [];
  console.log('✅ 候选人 JSON 校验通过');
  console.log(`   姓名: ${data.name}`);
  console.log(`   目标岗位: ${data.target_position}`);
  console.log(`   工作经历: ${we.length} 段`);
  console.log(`   技能: ${Array.isArray(data.skills) ? data.skills.length : 0} 项`);
  console.log(`   合规红线字段: 0（通过）`);
  process.exit(0);
}

main();
