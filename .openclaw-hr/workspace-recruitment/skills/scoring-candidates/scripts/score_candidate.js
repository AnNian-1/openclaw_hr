#!/usr/bin/env node
/**
 * score_candidate.js — 单份候选人 8 维度评分
 *
 * 用途：scoring-candidates Skill 的核心脚本。评分 Pipeline 第二层。
 *       对一份【脱敏后】的候选人数据 + 岗位 JD，调 DeepSeek 按 8 个固定
 *       维度打分，产出综合匹配分 + 评级 + 评分理由 + 亮点 + 顾虑 + 硬伤。
 *
 *       为什么用脚本而不是让 Agent 自由发挥：8 维度清单、各维度权重、
 *       评级切分、产出字段命名、concerns/hard_issues 的边界——这些是
 *       "必须每次一致"的约定。靠 LLM 临场记会漂（实测基线把字段命名
 *       从 dimension_scores 漂成 dimensions、把 65 分评成 B 而非 C）。
 *       脚本把固定 prompt 和字段约定钉死，LLM 只负责"打分"这件判断题。
 *
 * 输入必须是脱敏后的 JSON（经 filtering-sensitive-fields 处理）——
 * 本脚本不做合规过滤，评分前合规是 filtering-sensitive-fields 的职责。
 *
 * CLI：node score_candidate.js <脱敏候选人json> <JD-md> [输出json]
 *   退出码 0 = 评分成功；1 = 评分失败（LLM 多次重试仍不可用）；
 *           2 = 文件/用法问题。
 *
 * 可被 batch_rank.js require：module.exports.scoreCandidate
 */

'use strict';
const fs = require('fs');
const https = require('https');

function resolveLlm() {
  const model = process.env.LLM_MODEL || 'mimo-v2.5-pro';
  const isMimo =
    String(model).includes('mimo') ||
    String(process.env.LLM_BASE_URL || '').includes('xiaomi');
  const base =
    process.env.LLM_BASE_URL ||
    (isMimo ? 'https://token-plan-cn.xiaomimimo.com/v1' : '');
  let host = isMimo ? 'token-plan-cn.xiaomimimo.com' : 'api.deepseek.com';
  let path = '/v1/chat/completions';
  if (base) {
    const u = new URL(base.includes('://') ? base : `https://${base}`);
    host = u.hostname;
    const prefix = (u.pathname || '/').replace(/\/+$/, '') || '/v1';
    path = `${prefix}/chat/completions`;
  }
  const key =
    process.env.LLM_API_KEY ||
    (isMimo || host.includes('xiaomi')
      ? (process.env.XIAOMI_API_KEY || '')
      : '') ||
    process.env.DEEPSEEK_API_KEY ||
    '';
  return { model, host, path, key };
}
const { model: MODEL, host: API_HOST, path: API_PATH, key: API_KEY } = resolveLlm();

// ── 8 个固定评分维度 ──────────────────────────────────────────────
// 来源：candidate-profile-schema.md §8——基于 HR 业界面试评估标准、
// 且能从简历判断的维度。维度清单固定、不靠 LLM 临场记，是评分可复现的前提。
const DIMENSIONS = [
  '专业技能', '经验匹配', '逻辑能力', '学习力',
  '沟通能力', '协作能力', '抗压能力', '价值观',
];

/** 改 8 维定义、权重 prompt 或评级切分时 +1，令 batch_rank 缓存失效。 */
const SCORER_VERSION = 1;

/**
 * 评级切分。综合匹配分 → A/B/C/D 评级。
 * 切分点来源：score_pipeline.py 的评级口径——岗位初筛基线 60 分，
 * 65 分仅略高于基线属"待定"。固定切分避免 LLM 临场判（实测基线把
 * 65 分评成 B，与课程口径 C 不符）。注意：评级大类才是决策依据，
 * 1-2 分之差不抠——综合分本身有非确定性波动。
 */
function ratingOf(score) {
  if (score >= 85) return 'A(强烈推荐)';
  if (score >= 75) return 'B(推荐)';
  if (score >= 60) return 'C(待定)';
  return 'D(不匹配)';
}

/** 调 DeepSeek。json_mode 强制返回合法 JSON。retries 兜偶发网络故障。 */
function callDeepseek(systemPrompt, userPrompt, opts = {}) {
  const { maxTokens = 2500, temperature = 0.2, retries = 3 } = opts;
  const payload = JSON.stringify({
    model: MODEL,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    max_tokens: maxTokens,
    temperature,
    response_format: { type: 'json_object' },
  });

  function once() {
    return new Promise((resolve, reject) => {
      const req = https.request(
        {
          host: API_HOST, path: API_PATH, method: 'POST',
          headers: {
            Authorization: `Bearer ${API_KEY}`,
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload),
          },
          timeout: 120000,
        },
        (res) => {
          let body = '';
          res.on('data', (c) => (body += c));
          res.on('end', () => {
            try {
              const j = JSON.parse(body);
              if (j.error) return reject(new Error(j.error.message || body));
              resolve(j.choices[0].message.content);
            } catch (e) {
              reject(new Error(`响应解析失败: ${e.message}`));
            }
          });
        }
      );
      req.on('error', reject);
      req.on('timeout', () => req.destroy(new Error('请求超时')));
      req.write(payload);
      req.end();
    });
  }

  return (async () => {
    let lastErr;
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        return await once();
      } catch (e) {
        lastErr = e;
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, 3000 * attempt)); // 指数退避
        }
      }
    }
    throw new Error(`${MODEL} 调用 ${retries} 次均失败：${lastErr.message}`);
  })();
}

/** 从 LLM 回复抽 JSON，容忍 ```json 包裹 + 尾逗号瑕疵（LLM 高频瑕疵）。 */
function extractJson(text) {
  let t = text;
  const fenced = t.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/);
  if (fenced) t = fenced[1];
  else {
    const obj = t.match(/\{[\s\S]*\}/);
    if (obj) t = obj[0];
  }
  try {
    return JSON.parse(t);
  } catch (e) {
    // 去掉对象/数组结尾多余逗号后再试
    return JSON.parse(t.replace(/,(\s*[}\]])/g, '$1'));
  }
}

/**
 * 对一份脱敏候选人 JSON + JD 文本做 8 维度评分。
 * 返回评分结果对象。LLM 返回非法 JSON 时重新调用（比硬修字符串可靠）。
 */
async function scoreCandidate(cleanCandidate, jdText, jdName) {
  // ── 固定评分 prompt ──────────────────────────────────────────
  // 三段强制约束写死进 system prompt，不靠 LLM 临场记：
  //   合规红线——评分不得使用敏感特征（第二道防线，filtering-sensitive-fields
  //     已物理删除是第一道；万一敏感信息藏在 self_evaluation 自由文本里兜底）
  //   可解释——每维度分必须给依据（个保法 24 条对自动化决策的要求）
  //   边界——只产出评分建议，不做录用/淘汰决定
  const sysP =
    '你是资深招聘评估专家，对候选人做简历初筛阶段的结构化评分。\n' +
    '【合规红线 · 强制】禁止使用以下任何因素影响评分：年龄、出生日期、' +
    '性别、婚育状况、户籍/籍贯/出生地、民族、院校排名/院校层次、健康状况、' +
    '政治面貌。评分只能基于：岗位相关技能、工作经历与岗位的匹配度、项目' +
    '经验、简历表述质量。如发现数据里残留这些敏感信息也必须忽略。\n' +
    '【可解释 · 强制】每个维度分必须给出依据，综合评分必须写清理由——' +
    '这是个保法第 24 条的要求，候选人有权要求说明为什么是这个分。\n' +
    '【边界 · 强制】你只产出评分与排序建议，不做录用/淘汰决定。' +
    '不要出现"淘汰""拒绝"等词，最终决定由人工 HR 做。\n' +
    '【维度权重 · 强制】8 个维度里，"专业技能"和"经验匹配"这两个对口度' +
    '维度对综合匹配分影响最大——方向不对口的候选人，综合分应明显偏低。';

  const userP =
    `目标岗位 JD（${jdName}）：\n---\n${jdText}\n---\n\n` +
    `候选人结构化数据（已做合规脱敏，敏感字段已剥离）：\n---\n` +
    `${JSON.stringify(cleanCandidate, null, 2)}\n---\n\n` +
    `请按以下 8 个维度评分，每维度 1-5 分（5 最高）：\n` +
    DIMENSIONS.map((d) => `- ${d}`).join('\n') +
    `\n\n输出 JSON（字段名严格照抄，不要改名）：\n` +
    `{\n` +
    `  "candidate_name": "姓名",\n` +
    `  "dimension_scores": {${DIMENSIONS.map((d) => `"${d}": 分`).join(', ')}},\n` +
    `  "dimension_reasons": {"专业技能": "给这个分的依据", ...8 个维度...},\n` +
    `  "jd_match_score": 0-100 综合匹配分,\n` +
    `  "overall_rating": "A/B/C/D 之一（只填字母，评级文字脚本会补）",\n` +
    `  "score_reasoning": "综合评分理由，说清为什么是这个分，2-4 句",\n` +
    `  "highlights": ["亮点1", "亮点2", "亮点3"],\n` +
    `  "concerns": ["顾虑1", "顾虑2"],\n` +
    `  "hard_issues": ["硬伤；没有则空数组"]\n` +
    `}\n\n` +
    `【concerns 与 hard_issues 的区别 · 必须严格区分】\n` +
    `- concerns（顾虑）：岗位匹配度相关的担忧。例如期望薪资超岗位带宽、\n` +
    `  期望城市与岗位不符、经验方向不对口、overqualified。这些放 concerns。\n` +
    `- hard_issues（硬伤）：简历本身的真实性/可信度问题。只有以下三类算硬伤：\n` +
    `  ① 工作经历时间矛盾（两段全职经历时间区间重叠）\n` +
    `  ② 学历存疑（学历与岗位硬性门槛不符，或学历信息自相矛盾）\n` +
    `  ③ 简历内容自相矛盾（如工作年限与经历明显对不上）\n` +
    `  薪资高、城市不符、岗位不匹配【不是硬伤】，不要放进 hard_issues。\n` +
    `  跳槽频繁、就业空窗期也【不是硬伤】——它们是稳定性信号，归 concerns。\n` +
    `只输出 JSON。`;

  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const raw = await callDeepseek(sysP, userP);
    try {
      const score = extractJson(raw);
      // 评级用脚本固定切分覆盖——不取 LLM 自填的字母，保证口径一致。
      const num = Number(score.jd_match_score);
      score.overall_rating = ratingOf(num);
      return score;
    } catch (e) {
      lastErr = e;
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
  throw new Error(`LLM 返回 JSON 多次无法解析：${lastErr.message}`);
}

async function main() {
  const [, , candFile, jdFile, outPath] = process.argv;
  if (!candFile || !jdFile) {
    console.error(
      '用法: node score_candidate.js <脱敏候选人json> <JD-md> [输出json]'
    );
    process.exit(2);
  }
  for (const f of [candFile, jdFile]) {
    if (!fs.existsSync(f)) {
      console.error(`文件不存在: ${f}`);
      process.exit(2);
    }
  }
  if (!API_KEY) {
    console.error('未设置 XIAOMI_API_KEY / LLM_API_KEY（mimo）或 DEEPSEEK_API_KEY');
    process.exit(2);
  }

  let candidate;
  try {
    candidate = JSON.parse(fs.readFileSync(candFile, 'utf8'));
  } catch (e) {
    console.error(`候选人 JSON 无法解析: ${e.message}`);
    process.exit(2);
  }
  const jdText = fs.readFileSync(jdFile, 'utf8');
  const jdName = jdFile.split('/').pop();

  console.log('📊 8 维度评分 · scoring-candidates');
  console.log(`   候选人：${candidate.name || candFile}`);
  console.log(`   目标岗位：${jdName}`);

  let score;
  try {
    score = await scoreCandidate(candidate, jdText, jdName);
  } catch (e) {
    console.error(`❌ 评分失败：${e.message}`);
    process.exit(1);
  }

  console.log(`   综合匹配分：${score.jd_match_score}  评级：${score.overall_rating}（建议）`);
  console.log(`   维度分：${JSON.stringify(score.dimension_scores, null, 0)}`);
  if (score.hard_issues && score.hard_issues.length) {
    console.log(`   ⚠ 硬伤：${JSON.stringify(score.hard_issues)}`);
  } else {
    console.log('   硬伤：无');
  }

  if (outPath) {
    fs.writeFileSync(outPath, JSON.stringify(score, null, 2), 'utf8');
    console.log(`   评分结果已写出：${outPath}`);
  }
  process.exit(0);
}

module.exports = { scoreCandidate, ratingOf, DIMENSIONS, SCORER_VERSION };

if (require.main === module) main();
