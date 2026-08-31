#!/usr/bin/env node
/**
 * audit_numbers.js — 评分产出的数字回核
 *
 * 用途：auditing-numbers Skill 的核心脚本。评分 Pipeline 第三层。
 *       对一份评分产出做数字回核——评分文字（亮点/顾虑/评分理由/维度
 *       理由）里凡是引用候选人简历的数字（TPS、金额、增长率、年限、
 *       规模等），必须能在【该候选人的原简历】里找到对应值。对不上的
 *       判为虚构，用最小替换对精确修正回原简历真实值，并留存修正
 *       前后快照。
 *
 *       为什么需要这一层：评分第二层用大模型生成亮点、理由等自由文本时，
 *       大模型会在"复述"候选人简历时把数字串台——实测案例：员工1原简历
 *       写"大促峰值 12.8 万 TPS"，评分 highlights 复述成了"双十一峰值
 *       58 万笔/秒"。追因发现 58 万笔/秒 出现在【JD 的岗位职责】里，
 *       大模型把 JD 的场景数字张冠李戴安到了候选人头上。这是大模型
 *       自由文本生成的典型"上下文串台"风险，靠 prompt 叮嘱不可靠。
 *
 * 回核基准 = 候选人原简历，且【只能是原简历】。不能拿 JD 当基准——
 *       JD 里的数字看起来"相关"，但它不属于候选人，正是串台的来源。
 *       本脚本签名只吃简历、不留 JD 参数位，从机制上杜绝基准被污染。
 *
 * 三步 + 一步修正：
 *   step1 extract     从评分文字里正则抽出所有「数字 + 上下文短语」（确定性）
 *   step2 verify       每个数字在原简历里归一化比对（确定性）
 *   step3 adjudicate   简历里找不到的，交大模型判定是不是真虚构
 *                      （排除通用表述、JD 场景数字、约数；非确定性，故重试容错）
 *   step4 apply        判为虚构的，用大模型给的最小替换对精确修正，留存快照
 *
 * CLI：node audit_numbers.js <评分结果json> <候选人原简历md> [修正后输出json]
 *   评分结果 json 可以是 score 对象本身，也可以是含 score 字段的包裹对象。
 *   不给输出路径时只打印回核报告、不写文件。
 *   退出码 0 = 回核完成（含"发现并修正了虚构数字"也算完成）；
 *           1 = 回核失败（大模型判定多次重试仍不可用——绝不当作"无虚构"放行）；
 *           2 = 文件 / 用法问题。
 *
 * 可被其它脚本 require：module.exports.auditNumbers
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

// ── 要回核的评分文字字段 ────────────────────────────────────────────
// 这几个字段是评分第二层用大模型生成的自由文本，有"复述简历时串台"的
// 漂移风险。candidate_name、jd_match_score 这类是结构化值不在此列。
// dimension_reasons 是 dict，单独遍历。
const TEXT_FIELDS = ['highlights', 'concerns', 'score_reasoning'];

// ── 数字模式 ────────────────────────────────────────────────────────
// 捕获 数字 + 紧跟的单位/量词。覆盖 TPS/QPS/万/亿/%/年/人/倍/ms 等
// 招聘评分文字里会出现的量纲。单位列表来自对真实评分产出的归纳。
const NUM_PATTERN = new RegExp(
  '\\d+(?:\\.\\d+)?\\s*' +
    '(?:万|亿|千|百|个|人|年|月|天|倍|次|' +
    'TPS|QPS|tps|qps|ms|秒|笔/秒|条/秒|%|pp|K|w|元)?',
  'g'
);

/** 归一化：去掉所有空白。简历排版常把数字和单位换行拆开
 *  （如 '12.8 万\nTPS'），归一化后才能正确做子串匹配。 */
function norm(text) {
  return (text || '').replace(/\s+/g, '');
}

/** 调 DeepSeek。json_mode 强制返回合法 JSON。retries 兜偶发网络故障。 */
function callDeepseek(systemPrompt, userPrompt, opts = {}) {
  const { maxTokens = 2000, temperature = 0.0, retries = 3 } = opts;
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
          host: API_HOST,
          path: API_PATH,
          method: 'POST',
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
    return JSON.parse(t.replace(/,(\s*[}\]])/g, '$1'));
  }
}

// ══ step1 · extract ════════════════════════════════════════════════
/** 从一段文本抽出所有「数字 token」。返回 [{token, phrase}]。
 *  phrase 取 token 前后各 12 字，便于人读和大模型判定上下文。 */
function extractNumbers(text) {
  const found = [];
  let m;
  NUM_PATTERN.lastIndex = 0;
  while ((m = NUM_PATTERN.exec(text)) !== null) {
    const token = m[0].trim();
    if (!/\d/.test(token)) continue; // 跳过纯标点残留
    if (m[0].length === 0) {
      NUM_PATTERN.lastIndex++; // 防零宽匹配死循环
      continue;
    }
    const s = Math.max(0, m.index - 12);
    const e = Math.min(text.length, m.index + m[0].length + 12);
    const phrase = text.slice(s, e).replace(/\n/g, ' ');
    found.push({ token, phrase });
  }
  return found;
}

/** 把评分产出里所有要回核的文本片段收集出来。返回 [{loc, text}]。
 *  loc 形如 highlights[1] / score_reasoning / dimension_reasons.抗压能力。 */
function collectOutputs(score) {
  const items = [];
  for (const f of TEXT_FIELDS) {
    const v = score[f];
    if (Array.isArray(v)) {
      v.forEach((s, i) => {
        if (typeof s === 'string' && s) items.push({ loc: `${f}[${i}]`, text: s });
      });
    } else if (typeof v === 'string' && v) {
      items.push({ loc: f, text: v });
    }
  }
  const dr = score.dimension_reasons;
  if (dr && typeof dr === 'object') {
    for (const [dim, reason] of Object.entries(dr)) {
      if (typeof reason === 'string' && reason) {
        items.push({ loc: `dimension_reasons.${dim}`, text: reason });
      }
    }
  }
  return items;
}

// ══ step2 · verify ═════════════════════════════════════════════════
/** 数字 token 是否在原简历（已归一化）里出现。
 *  返回 true=简历里有；false=数字本身都查不到（基本确定虚构）；
 *  null=纯数字命中但单位/量级不同（疑似改写，需大模型看）。 */
function verifyInResume(token, resumeNorm) {
  const tokenNorm = norm(token);
  if (resumeNorm.includes(tokenNorm)) return true;
  const numMatch = tokenNorm.match(/\d+(?:\.\d+)?/);
  if (numMatch && resumeNorm.includes(numMatch[0])) return null;
  return false;
}

// ══ step4 · apply（最小替换对精确修正）═══════════════════════════════
/** 把一段文本里的虚构数字改成真实值。
 *  优先：用大模型给的最小替换对 bad_span→good_span 精确替换——bad_span
 *        只圈住虚构数字+错误单位，替换范围最小，旧单位随虚构数字一起换掉。
 *  回退：bad_span 在文本里逐字对不上时，退化为 token 级替换。 */
function replaceIn(text, token, realValue, badSpan, goodSpan) {
  if (badSpan && goodSpan && text.includes(badSpan)) {
    return text.split(badSpan).join(goodSpan);
  }
  if (token && realValue && text.includes(token)) {
    return text.split(token).join(realValue);
  }
  return text;
}

/** 按 loc 取出评分产出里某字段的当前文本（用于留存修正前后快照）。 */
function fieldText(score, loc) {
  const m = loc.match(/^(\w+)\[(\d+)\]$/);
  if (m) {
    const lst = score[m[1]];
    const idx = Number(m[2]);
    if (Array.isArray(lst) && idx >= 0 && idx < lst.length) return lst[idx];
  } else if (loc.startsWith('dimension_reasons.')) {
    const dim = loc.slice('dimension_reasons.'.length);
    return (score.dimension_reasons || {})[dim] || '';
  } else if (typeof score[loc] === 'string') {
    return score[loc];
  }
  return '';
}

/** 把评分产出里某字段的虚构数字替换成原简历真实值。返回是否真改了。 */
function applyFix(score, loc, token, realValue, badSpan, goodSpan) {
  if (!realValue && !goodSpan) return false;
  const m = loc.match(/^(\w+)\[(\d+)\]$/);
  if (m) {
    const field = m[1];
    const idx = Number(m[2]);
    const lst = score[field];
    if (Array.isArray(lst) && idx >= 0 && idx < lst.length) {
      const next = replaceIn(lst[idx], token, realValue, badSpan, goodSpan);
      const changed = next !== lst[idx];
      lst[idx] = next;
      return changed;
    }
  } else if (loc.startsWith('dimension_reasons.')) {
    const dim = loc.slice('dimension_reasons.'.length);
    const dr = score.dimension_reasons || {};
    if (dim in dr) {
      const next = replaceIn(dr[dim], token, realValue, badSpan, goodSpan);
      const changed = next !== dr[dim];
      dr[dim] = next;
      return changed;
    }
  } else if (typeof score[loc] === 'string') {
    const next = replaceIn(score[loc], token, realValue, badSpan, goodSpan);
    const changed = next !== score[loc];
    score[loc] = next;
    return changed;
  }
  return false;
}

// ══ 主流程 ═════════════════════════════════════════════════════════
/**
 * 对一份评分产出做数字回核。原地修正 score 对象里的虚构数字。
 * @param {object} score   评分产出（score 对象本身）
 * @param {string} resumeMd 候选人原简历全文（唯一回核基准——不接收 JD）
 * @param {string} name    候选人姓名（仅用于日志）
 * @returns {Promise<object>} 回核报告 {total_numbers, suspects, fabricated, fixes}
 */
async function auditNumbers(score, resumeMd, name) {
  const resumeNorm = norm(resumeMd);
  const outputs = collectOutputs(score);

  // step1 + step2：抽数字，逐个在简历里比对
  const suspects = [];
  let totalNums = 0;
  for (const { loc, text } of outputs) {
    for (const { token, phrase } of extractNumbers(text)) {
      totalNums++;
      const hit = verifyInResume(token, resumeNorm);
      if (hit === false) {
        suspects.push({ loc, token, phrase, kind: '简历无此数字' });
      } else if (hit === null) {
        suspects.push({ loc, token, phrase, kind: '数字在但量级/单位存疑' });
      }
    }
  }

  console.log(
    `  数字回核 · ${name}：评分文字共抽取 ${totalNums} 个数字，` +
      `简历比对存疑 ${suspects.length} 个`
  );

  if (suspects.length === 0) {
    return { total_numbers: totalNums, suspects: 0, fabricated: 0, fixes: [] };
  }

  // step3：大模型判定——简历里对不上的，是真虚构还是合理表述
  const sysP =
    '你是招聘评分的真实性审计员。给你一份候选人的【原简历全文】和一批' +
    '从评分产出里抽出的、在简历里找不到的数字。判断每个数字是不是' +
    '【虚构】——即评分文字声称这是候选人的经历/能力数据，但原简历里' +
    '并没有这个数据。\n' +
    '判定规则：\n' +
    '1. 评分文字把某个数字当作候选人的经历事实陈述，但简历里查无此数 ' +
    '→ verdict=fabricated（虚构）。要找出简历里被改写的真实原值。\n' +
    '2. 数字属于通用表述、约数、岗位职级代号（如 P6/P7）、年份、' +
    '或明显是 JD 岗位要求而非候选人经历 → verdict=ok（不算虚构）。\n' +
    '3. 数字是简历真实数据的合理换算（如年限换算）→ verdict=ok。\n' +
    '对 fabricated 的，必须给出修正用的【最小替换对】：\n' +
    '- real_value：原简历里对应的真实数字【最简原文】，只含数字+单位' +
    "（如 '12.8 万 TPS'、'7 年'），不要带括号注释、不要带'简历原文'字样。\n" +
    '- bad_span：评分文字里【需要被替换掉的那一小段连续原文】。' +
    '它必须是『出现短语』里**逐字出现**的一个子串，且尽量短——' +
    '只圈住虚构数字连同它紧跟的错误单位/量词。例如出现短语是' +
    "'…双十一峰值58万笔/秒保障经历…'，bad_span 应为 '58万笔/秒'。\n" +
    '- good_span：把 bad_span 换成真实值后的【通顺替换文本】。' +
    "上面例子里 good_span 应为 '12.8 万 TPS'。\n" +
    '  要求：用『good_span 原样替换 bad_span』后，整句必须读起来通顺、' +
    '单位正确、不残留旧单位、不重复词语。\n' +
    '- fix：一句话修正说明。';

  const userP =
    `候选人「${name}」原简历全文：\n---\n${resumeMd}\n---\n\n` +
    `从该候选人评分产出里抽出的、简历里找不到的数字（逐个判定）：\n` +
    JSON.stringify(
      suspects.map((s, i) => ({
        id: i,
        字段: s.loc,
        数字: s.token,
        出现短语: s.phrase,
      })),
      null,
      2
    ) +
    `\n\n逐个判定，输出 JSON：\n` +
    `{\n` +
    `  "verdicts": [\n` +
    `    {\n` +
    `      "id": 数字编号,\n` +
    `      "verdict": "fabricated 或 ok",\n` +
    `      "reason": "判定依据，1-2 句",\n` +
    `      "real_value": "若 fabricated，原简历真实数字的最简原文（数字+单位，无注释）；ok 则空",\n` +
    `      "bad_span": "若 fabricated，评分文字里要被替换的最短连续原文子串（含虚构数字+错误单位）；ok 则空",\n` +
    `      "good_span": "若 fabricated，bad_span 替换成真实值后的通顺文本；ok 则空",\n` +
    `      "fix": "若 fabricated，一句话修正说明；ok 则空"\n` +
    `    }\n` +
    `  ]\n` +
    `}\n` +
    `只输出 JSON。`;

  // 大模型判定是非确定性的一步——重试 + 解析容错。多次失败必须显式
  // 抛错，绝不能把"判定没拿到"当成"无虚构"放行。
  let verdicts;
  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const raw = await callDeepseek(sysP, userP, { maxTokens: 2500 });
      verdicts = extractJson(raw).verdicts || [];
      break;
    } catch (e) {
      lastErr = e;
      if (attempt < 3) await new Promise((r) => setTimeout(r, 2000 * attempt));
    }
  }
  if (verdicts === undefined) {
    throw new Error(`数字回核判定阶段失败：${lastErr.message}`);
  }

  // step4：判为虚构的，用最小替换对精确修正，留存修正前后快照
  const fixes = [];
  for (const v of verdicts) {
    if (v.verdict !== 'fabricated') continue;
    const sid = v.id;
    const sus = typeof sid === 'number' && suspects[sid] ? suspects[sid] : {};
    const loc = sus.loc || '';
    const before = fieldText(score, loc); // 修正前快照（审计证据）
    const ok = applyFix(
      score,
      loc,
      sus.token || '',
      v.real_value || '',
      v.bad_span || '',
      v.good_span || ''
    );
    const after = fieldText(score, loc); // 修正后文本
    fixes.push({
      loc,
      fabricated: sus.token,
      real_value: v.real_value,
      bad_span: v.bad_span,
      good_span: v.good_span,
      reason: v.reason,
      applied: ok,
      text_before: before,
      text_after: after,
    });
    const mark = ok ? '已修正' : '需人工';
    console.log(
      `  ✗ 数字虚构【${mark}】${loc}：产出「${sus.token}」→ ` +
        `原简历「${v.real_value}」`
    );
  }
  if (fixes.length === 0) {
    console.log('  ✓ 数字回核通过：评分产出未发现虚构数字');
  }

  return {
    total_numbers: totalNums,
    suspects: suspects.length,
    fabricated: fixes.length,
    fixes,
  };
}

async function main() {
  const [, , scoreFile, resumeFile, outPath] = process.argv;
  if (!scoreFile || !resumeFile) {
    console.error(
      '用法: node audit_numbers.js <评分结果json> <候选人原简历md> [修正后输出json]'
    );
    console.error(
      '注意：第二个参数只能是候选人原简历——回核基准不能用 JD。'
    );
    process.exit(2);
  }
  for (const f of [scoreFile, resumeFile]) {
    if (!fs.existsSync(f)) {
      console.error(`文件不存在: ${f}`);
      process.exit(2);
    }
  }
  if (!API_KEY) {
    console.error('未设置 XIAOMI_API_KEY / LLM_API_KEY（mimo）或 DEEPSEEK_API_KEY');
    process.exit(2);
  }

  let scored;
  try {
    scored = JSON.parse(fs.readFileSync(scoreFile, 'utf8'));
  } catch (e) {
    console.error(`评分结果 JSON 无法解析: ${e.message}`);
    process.exit(2);
  }
  const resumeMd = fs.readFileSync(resumeFile, 'utf8');
  // 评分结果可以是 score 对象本身，也可以是含 score 字段的包裹对象。
  const score = scored.score && typeof scored.score === 'object' ? scored.score : scored;
  const name = score.candidate_name || '候选人';

  console.log('🔢 数字回核 · auditing-numbers');
  console.log(`   候选人：${name}`);
  console.log(`   回核基准：${resumeFile}（原简历）`);

  let report;
  try {
    report = await auditNumbers(score, resumeMd, name);
  } catch (e) {
    console.error(`❌ 数字回核失败：${e.message}`);
    process.exit(1);
  }

  console.log(
    `   回核结果：抽取 ${report.total_numbers} 个数字 / ` +
      `存疑 ${report.suspects} 个 / 判定 ${report.fabricated} 处虚构` +
      `${report.fabricated ? '（已修正）' : ''}`
  );
  for (const fx of report.fixes) {
    console.log(`\n   ✗ 虚构 · 字段 ${fx.loc}`);
    console.log(`      产出写的    : ${fx.fabricated}`);
    console.log(`      原简历真实值 : ${fx.real_value}`);
    console.log(`      修正前       : ${fx.text_before}`);
    console.log(`      修正后       : ${fx.text_after}`);
    console.log(`      判定依据    : ${fx.reason}`);
  }

  if (outPath) {
    // 修正后的 score 写回——若原文件是包裹对象，连 number_audit 报告一起写。
    const out =
      scored.score && typeof scored.score === 'object'
        ? Object.assign({}, scored, { score, number_audit: report })
        : score;
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2), 'utf8');
    console.log(`\n   修正后评分结果已写出：${outPath}`);
  }
  process.exit(0);
}

module.exports = { auditNumbers, extractNumbers, verifyInResume, replaceIn };

if (require.main === module) main();
