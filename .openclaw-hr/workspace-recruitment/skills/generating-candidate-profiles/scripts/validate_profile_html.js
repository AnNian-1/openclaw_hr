#!/usr/bin/env node
/**
 * validate_profile_html.js — HTML 候选人画像校验器
 *
 * 用途：generating-candidate-profiles Skill 的校验闭环。generate_profile.py
 *       渲染出画像 HTML 后，用本脚本校验，跑通才算画像合格。把"画像七区块
 *       齐不齐、合规红线字段有没有漏进展示页、画像数字和数据源一不一致"
 *       这三件确定性的事，从"人肉打开浏览器看"收回到脚本里。
 *
 * 校验项：
 *   1. HTML 可读、非空
 *   2. 七区块齐全：基本信息卡 / 综合评级横幅 / 8 维度雷达图 / JD 匹配度 /
 *      工作经历时间线 / 技能词云 / 亮点·顾虑·硬伤
 *   3. 雷达图、技能词云为 base64 内嵌图（单文件自包含，不依赖外部资源）
 *   4. 合规红线字段零渲染（schema §9：年龄/出生/性别/婚育/政治面貌/
 *      户籍/民族/健康——可记录于数据资产，但不得进入展示性画像）
 *   5. 若给了数据源 ranking JSON，核对画像里的综合分、评级、技能数
 *      与数据源一致——确认画像是忠实呈现，不是另起炉灶编的
 *
 * CLI：node validate_profile_html.js <profile.html> [<ranking.json> <候选人姓名>]
 *   退出码 0 = 校验通过；1 = 校验失败（stderr 列出全部问题）；2 = 用法/文件错误
 */

'use strict';
const fs = require('fs');

// 画像七区块。前 6 个用 section-title 文本匹配，基本信息卡在 <div class="header">
// 里不带 section-title，单独用 class="header" 判定。
const REQUIRED_SECTIONS = [
  { name: '8 维度能力雷达图', marker: '能力雷达' },
  { name: '与 JD 匹配度对比', marker: 'JD 匹配度' },
  { name: '工作经历时间线', marker: '工作经历时间线' },
  { name: '技能词云', marker: '技能词云' },
  { name: '亮点·顾虑·硬伤', marker: '亮点' },
];

// 合规红线字段。来源：candidate-profile-schema.md §9，依据《个人信息保护法》
// 第 24 条、《就业促进法》第 26-31 条。这些字段允许存在于候选人数据资产
// （HR 做性别比例统计等需要），但绝不能出现在展示给用人方看的画像上——
// 画像里出现年龄/性别，会让看画像的人把它当筛选依据，构成就业歧视风险。
const FORBIDDEN_LABELS = [
  '出生年月', '出生日期', '年龄',
  '性别',
  '婚育', '婚姻状况',
  '政治面貌',
  '户籍', '籍贯', '出生地',
  '民族',
  '健康状况', '残疾',
];

function fail(problems) {
  console.error('❌ HTML 候选人画像校验未通过：');
  problems.forEach((p, i) => console.error(`  ${i + 1}. ${p}`));
  process.exit(1);
}

function main() {
  const htmlFile = process.argv[2];
  const rankingFile = process.argv[3]; // 可选
  const targetName = process.argv[4]; // 可选

  if (!htmlFile) {
    console.error(
      '用法: node validate_profile_html.js <profile.html> [<ranking.json> <候选人姓名>]'
    );
    process.exit(2);
  }
  if (!fs.existsSync(htmlFile)) {
    console.error(`画像 HTML 文件不存在: ${htmlFile}`);
    process.exit(2);
  }

  const html = fs.readFileSync(htmlFile, 'utf8');
  const problems = [];

  // 1. 非空
  if (html.trim().length < 200) {
    fail([`画像 HTML 内容过短（${html.length} 字节），疑似生成失败`]);
  }

  // 2. 七区块 —— 基本信息卡（header）+ 综合评级横幅（rating-badge）+ 5 个 section
  if (!/class="header"/.test(html)) {
    problems.push('缺少区块：基本信息卡（<div class="header">）');
  }
  if (!/class="rating-badge"/.test(html)) {
    problems.push('缺少区块：综合评级横幅（<div class="rating-badge">）');
  }
  for (const s of REQUIRED_SECTIONS) {
    if (!html.includes(s.marker)) {
      problems.push(`缺少区块：${s.name}（未找到标记文本「${s.marker}」）`);
    }
  }

  // 3. 图表 base64 内嵌 —— 雷达图 + 技能词云，至少 2 张内嵌图
  const embedCount = (html.match(/data:image\/png;base64,/g) || []).length;
  if (embedCount < 2) {
    problems.push(
      `画像只有 ${embedCount} 张 base64 内嵌图，应至少 2 张（雷达图 + 技能词云）。` +
        `图表必须 base64 内嵌，画像才是不依赖外部资源的单文件。`
    );
  }

  // 4. 合规红线字段零渲染 —— 扫 HTML 正文里出现的字段标签文本
  const hits = [];
  for (const label of FORBIDDEN_LABELS) {
    if (html.includes(label)) hits.push(label);
  }
  if (hits.length) {
    problems.push(
      `画像渲染了合规红线字段：${hits.join('、')}。` +
        `schema §9 规定这些字段不得进入展示性画像——会让看画像的人当筛选依据，` +
        `构成就业歧视风险。请从画像模板移除这些字段的渲染。`
    );
  }

  // 5. 与数据源一致性核对（给了 ranking JSON 才做）
  if (rankingFile && targetName) {
    if (!fs.existsSync(rankingFile)) {
      problems.push(`数据源 ranking JSON 不存在: ${rankingFile}`);
    } else {
      let ranking;
      try {
        ranking = JSON.parse(fs.readFileSync(rankingFile, 'utf8'));
      } catch (e) {
        problems.push(`数据源 ranking JSON 无法解析：${e.message}`);
      }
      if (ranking) {
        const detail = (ranking.details || []).find(
          (d) => (d.parsed || {}).name === targetName
        );
        if (!detail) {
          problems.push(
            `数据源里找不到候选人「${targetName}」，无法做一致性核对`
          );
        } else {
          // 5a. 综合分一致
          const expectScore = detail.score.jd_match_score;
          const scoreInHtml = (html.match(/class="score">(\d+)/) || [])[1];
          if (scoreInHtml === undefined) {
            problems.push('画像里找不到综合分（class="score"）');
          } else if (Number(scoreInHtml) !== Number(expectScore)) {
            problems.push(
              `画像综合分 ${scoreInHtml} 与数据源 ${expectScore} 不一致——` +
                `画像必须忠实呈现 ranking JSON 的评分，不能另行编一个分`
            );
          }
          // 5b. 技能数一致
          const expectSkills = (detail.parsed.skills || []).length;
          const skillInHtml = (html.match(/共\s*(\d+)\s*项技能/) || [])[1];
          if (
            skillInHtml !== undefined &&
            Number(skillInHtml) !== expectSkills
          ) {
            problems.push(
              `画像技能数 ${skillInHtml} 与数据源 ${expectSkills} 不一致`
            );
          }
          // 5c. 评级首字母一致
          const rawRating = String(detail.score.overall_rating || '');
          const expectRating = (rawRating.match(/[ABCD]/) || [])[0];
          const ratingInHtml = (html.match(/class="grade"[^>]*>([ABCD])\s*级/) ||
            [])[1];
          if (
            expectRating &&
            ratingInHtml &&
            ratingInHtml !== expectRating
          ) {
            problems.push(
              `画像评级 ${ratingInHtml} 级与数据源 ${expectRating} 级不一致`
            );
          }
        }
      }
    }
  }

  if (problems.length) fail(problems);

  // 通过 —— 输出体检摘要
  const nameInHtml = (html.match(/<h1>([^<]+)<\/h1>/) || [])[1] || '?';
  const scoreInHtml = (html.match(/class="score">(\d+)/) || [])[1] || '?';
  const skillInHtml = (html.match(/共\s*(\d+)\s*项技能/) || [])[1] || '?';
  console.log('✅ HTML 候选人画像校验通过');
  console.log(`   候选人: ${nameInHtml}`);
  console.log(`   综合分: ${scoreInHtml}`);
  console.log(`   七区块: 齐全（信息卡/评级横幅/雷达图/JD匹配/时间线/词云/亮点顾虑硬伤）`);
  console.log(`   base64 内嵌图: ${embedCount} 张（单文件自包含）`);
  console.log(`   技能词云: ${skillInHtml} 项`);
  console.log(`   合规红线字段: 0（未渲染敏感字段，通过）`);
  if (rankingFile && targetName) {
    console.log(`   数据源一致性: 综合分/评级/技能数 均与 ranking JSON 一致`);
  }
  process.exit(0);
}

main();
