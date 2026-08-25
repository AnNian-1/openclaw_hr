#!/usr/bin/env node
/**
 * filter_sensitive.js — 评分前合规过滤层
 *
 * 用途：filtering-sensitive-fields Skill 的核心脚本。评分 Pipeline 第一层。
 *       在候选人画像 JSON 进入评分模型之前，物理删除 candidate-profile-schema.md
 *       §9 的敏感字段，产出脱敏评分输入。
 *
 *       合规过滤"做对"靠的不是叮嘱 LLM 别用敏感字段，是让评分模型根本
 *       看不到——把"剥哪些字段、扫哪几层、剥完自检"这件确定性的事从 LLM
 *       手里收回到脚本里。这是法律风险最高的一层，绝不能靠 LLM 临场判断。
 *
 * 处理：
 *   1. 物理删除黑名单字段——递归扫所有层级（顶层 + education 等子层）
 *   2. 合规自检——剥完后递归重扫，残留任何敏感 key 即抛错、退出码非 0
 *   3. 产出脱敏 JSON + 剥离清单（结构化、可留存的合规日志）
 *
 * CLI：node filter_sensitive.js <profile.json> [脱敏输出.json]
 *   不给输出路径时打印脱敏 JSON 到 stdout，不写文件。
 *   退出码 0 = 过滤通过（自检剩余敏感字段=0）；
 *           1 = 合规自检未通过（剥完仍有残留——绝不放行）；
 *           2 = 用法错误 / 文件问题。
 */

'use strict';
const fs = require('fs');

// ── 合规红线黑名单 ───────────────────────────────────────────────
// 来源：candidate-profile-schema.md §9。
// 法律依据分两类（强度不同，但都必须物理删除）：
//   法定受保护特征——年龄/出生日期、性别、民族、户籍籍贯、婚育、健康/残疾。
//     《就业促进法》第 26 条一般性禁止 + 第 27-30 条专条（性别/民族/残疾/
//     传染病病原携带），《个人信息保护法》第 28 条敏感个人信息。
//   政策强烈反对、非法定受保护特征——院校层次（"第一学历""985/211 门槛"）。
//     教育部、人社部多次发文不鼓励校招设院校门槛。定性是"避免间接歧视"。
//   政治面貌——§28 对敏感个人信息用"等"字非穷尽列举，从严保护，一并剥离。
// 中英文键名都列入——评分模型看到英文键 age 一样会用，不能因键名语言放过。
const FORBIDDEN_KEYS = [
  // 年龄 / 出生日期
  'age', 'birth_date', 'birth_year', 'birthdate', 'birthday',
  'date_of_birth', 'birthyear',
  '出生年月', '出生日期', '年龄', '生日',
  // 性别
  'gender', 'sex', '性别',
  // 婚育
  'marital_status', 'marriage', 'marital', 'children',
  '婚育', '婚姻状况', '婚姻', '生育',
  // 户籍 / 籍贯 / 出生地
  'hometown', 'household', 'domicile', 'native_place', 'birthplace',
  'origin', 'hukou',
  '籍贯', '户籍', '出生地', '户口',
  // 民族
  'ethnicity', 'nation', 'race', '民族',
  // 健康 / 残疾
  'health', 'disability', 'health_status',
  '健康状况', '健康', '残疾',
  // 院校层次（政策约束）
  'school_tier', 'school_rank', 'school_ranking',
  '院校层次', '院校排名', '第一学历',
  // 政治面貌
  'political_status', 'political', '政治面貌',
];

// 自检阶段用：判断一个 key 是否疑似敏感。
// normalizedMatch：把 key 转小写 + 去下划线/连字符后做包含匹配——
// 能兜住 birthYear 这类驼峰变体（黑名单逐字列不全所有写法时的兜底）。
const FORBIDDEN_STEMS = [
  'age', 'birth', 'gender', 'sex', 'marital', 'marriage',
  'ethnic', 'nation', 'race', 'health', 'disab', 'hukou',
  'household', 'domicile', 'nativeplace', 'birthplace',
  'schooltier', 'schoolrank', 'political',
  '出生', '年龄', '性别', '婚', '籍贯', '户籍', '户口', '民族',
  '健康', '残疾', '院校层次', '院校排名', '第一学历', '政治面貌',
];

function usageExit(msg) {
  console.error(msg);
  process.exit(2);
}

/** 一个 key 是否在精确黑名单里（大小写不敏感）。 */
function isForbiddenExact(key) {
  const lower = String(key).toLowerCase();
  return FORBIDDEN_KEYS.some((bad) => lower === bad.toLowerCase());
}

/**
 * 一个 key 是否疑似敏感——用于剥离后的自检兜底。
 * 归一化：小写 + 去 _ - 空格，再做词干包含匹配。
 * 这样 birthYear / birth_year / BirthDate 都能被自检兜住。
 */
function looksSensitive(key) {
  const norm = String(key).toLowerCase().replace(/[_\-\s]/g, '');
  return FORBIDDEN_STEMS.some((stem) => norm.includes(stem));
}

/**
 * 递归剥离敏感字段。
 * 敏感字段不只在数据顶层——院校层次嵌在 education 子层里，
 * 所以必须递归扫所有层级，不能只扫顶层（这正是基线漏 school_tier 的原因）。
 * 返回剥离清单 [{path, key, value}]。原对象被就地修改。
 */
function stripRecursive(obj, path, stripped) {
  if (obj === null || typeof obj !== 'object') return;
  if (Array.isArray(obj)) {
    obj.forEach((item, i) => stripRecursive(item, `${path}[${i}]`, stripped));
    return;
  }
  for (const key of Object.keys(obj)) {
    const here = path ? `${path}.${key}` : key;
    if (isForbiddenExact(key)) {
      stripped.push({ path: here, key, value: obj[key] });
      delete obj[key]; // 物理删除——评分模型根本拿不到
      continue;
    }
    stripRecursive(obj[key], here, stripped);
  }
}

/**
 * 合规自检：剥离后递归重扫，找出任何残留的疑似敏感 key。
 * 返回残留 path 列表。空列表 = 自检通过。
 */
function selfCheck(obj, path, leaks) {
  if (obj === null || typeof obj !== 'object') return leaks;
  if (Array.isArray(obj)) {
    obj.forEach((item, i) => selfCheck(item, `${path}[${i}]`, leaks));
    return leaks;
  }
  for (const key of Object.keys(obj)) {
    const here = path ? `${path}.${key}` : key;
    if (looksSensitive(key)) leaks.push(here);
    selfCheck(obj[key], here, leaks);
  }
  return leaks;
}

function main() {
  const file = process.argv[2];
  const outPath = process.argv[3];
  if (!file) {
    usageExit('用法: node filter_sensitive.js <profile.json> [脱敏输出.json]');
  }
  if (!fs.existsSync(file)) usageExit(`文件不存在: ${file}`);

  let data;
  try {
    data = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (e) {
    usageExit(`JSON 无法解析: ${e.message}`);
  }

  // 1. 物理删除——递归剥离敏感字段
  const stripped = [];
  stripRecursive(data, '', stripped);

  // 2. 合规自检——剥完后重扫，残留任何疑似敏感 key 即不通过
  const leaks = selfCheck(data, '', []);

  // 3. 输出剥离日志（结构化、可审计的合规证据）
  console.log('🔒 合规过滤层 · filtering-sensitive-fields');
  if (stripped.length) {
    console.log(`   已物理删除 ${stripped.length} 个敏感字段（不进评分）：`);
    stripped.forEach((s) => {
      const v = s.value === '' ? '(空值)' : s.value;
      console.log(`     - ${s.path} = ${v}`);
    });
  } else {
    console.log('   画像数据中未出现敏感字段，无需剥离');
  }
  console.log(
    `   合规自检：评分输入剩余敏感字段 = ${leaks.length} 个 ` +
      `${leaks.length === 0 ? '✓ 通过' : '✗ 未通过'}`
  );

  if (leaks.length) {
    // 合规过滤层是不可绕过的关卡——自检不过绝不放行。
    console.error(
      `❌ 合规自检未通过：脱敏后仍残留疑似敏感字段 ${leaks.join(', ')}。` +
        `这些字段不能带进评分模型。请把它们加进 FORBIDDEN_KEYS 黑名单后重跑。`
    );
    process.exit(1);
  }

  // 自检通过——产出脱敏评分输入
  if (outPath) {
    fs.writeFileSync(outPath, JSON.stringify(data, null, 2), 'utf8');
    console.log(`   脱敏评分输入已写出：${outPath}`);
  } else {
    console.log('--- 脱敏评分输入 JSON ---');
    console.log(JSON.stringify(data, null, 2));
  }
  process.exit(0);
}

main();
