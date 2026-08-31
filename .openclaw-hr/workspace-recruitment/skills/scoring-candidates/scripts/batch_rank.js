#!/usr/bin/env node
/**
 * batch_rank.js — 批量评分一批候选人 + 按综合分排序
 *
 * 用途：scoring-candidates Skill 的批量入口。对一个 JD，批量评分一个目录
 *       下的多份脱敏候选人 JSON，全部评完按综合匹配分降序排序，产出
 *       初筛排序结果。对应场景 1「上午集中筛简历」——HR 把一批简历丢进来，
 *       拿到排序好的候选人。
 *
 * 增量：每人一份 scoring/score-<stem>.json（含 cache：scorer_version、
 *       jd_sha256、clean_sha256）。命中则跳过 LLM。规则变更请 bump
 *       score_candidate.js 的 SCORER_VERSION。大批量脏数据用 --limit /
 *       --max-seconds 分片，不要一次 exec 打完全库。
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
 *      [--force] [--stale-only] [--merge-only] [--limit N] [--max-seconds N]
 *   文件名前缀可选——只评目录里匹配该前缀的 json（默认评全部 .json）。
 *   退出码 0 = 批量完成（即使有个别候选人失败也算完成，失败已标记）；
 *           2 = 文件/用法问题。
 */

'use strict';
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { scoreCandidate, SCORER_VERSION } = require('./score_candidate.js');

function sha256Text(s) {
  return crypto.createHash('sha256').update(String(s), 'utf8').digest('hex');
}

function parseArgs(argv) {
  const flags = {
    force: false,
    staleOnly: false,
    mergeOnly: false,
    limit: null,
    maxSeconds: null,
  };
  const pos = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--force') flags.force = true;
    else if (a === '--stale-only') flags.staleOnly = true;
    else if (a === '--merge-only') flags.mergeOnly = true;
    else if (a === '--limit') {
      const n = Number(argv[++i]);
      if (!Number.isFinite(n) || n < 1) {
        console.error('--limit 必须是正整数');
        process.exit(2);
      }
      flags.limit = n;
    } else if (a === '--max-seconds') {
      const n = Number(argv[++i]);
      if (!Number.isFinite(n) || n < 1) {
        console.error('--max-seconds 必须是正整数');
        process.exit(2);
      }
      flags.maxSeconds = n;
    } else if (a.startsWith('--')) {
      console.error(`未知参数: ${a}`);
      process.exit(2);
    } else {
      pos.push(a);
    }
  }
  return { flags, pos };
}

function scorePathFor(cleanFile) {
  const dir = path.dirname(cleanFile);
  const base = path.basename(cleanFile, '.json');
  const stem = base.startsWith('clean-') ? base.slice('clean-'.length) : base;
  return path.join(dir, `batch-score-${stem}.json`);
}

/** 检查 batch-score-* 和 score-* 两条路径，返回已有的评分 JSON */
function readExistingScore(cleanFile) {
  const dir = path.dirname(cleanFile);
  const base = path.basename(cleanFile, '.json');
  const stem = base.startsWith('clean-') ? base.slice('clean-'.length) : base;
  const batchPath = path.join(dir, `batch-score-${stem}.json`);
  const singlePath = path.join(dir, `score-${stem}.json`);
  for (const p of [batchPath, singlePath]) {
    if (fs.existsSync(p)) {
      try {
        return { json: JSON.parse(fs.readFileSync(p, 'utf8')), path: p };
      } catch (_) { /* 损坏，继续检查下一个 */ }
    }
  }
  return null;
}

function readCache(scoreObj) {
  if (!scoreObj || typeof scoreObj !== 'object') return null;
  const c = scoreObj.cache;
  if (c && typeof c === 'object') return c;
  return null;
}

function stripCache(scoreObj) {
  if (!scoreObj || typeof scoreObj !== 'object') return scoreObj;
  const { cache, ...rest } = scoreObj;
  return rest;
}

function isFresh(scoreObj, { jdSha, cleanSha, version }) {
  const c = readCache(scoreObj);
  if (!c) return false;
  return (
    Number(c.scorer_version) === version &&
    c.jd_sha256 === jdSha &&
    c.clean_sha256 === cleanSha
  );
}

function attachCache(score, { jdName, jdSha, cleanSha, version }) {
  return {
    ...score,
    cache: {
      scorer_version: version,
      jd_name: jdName,
      jd_sha256: jdSha,
      clean_sha256: cleanSha,
      scored_at: new Date().toISOString(),
    },
  };
}

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

function usage() {
  console.error(
    '用法: node batch_rank.js <JD-md> <脱敏候选人json目录> [输出json] [文件名前缀]\n' +
      '      [--force] [--stale-only] [--merge-only] [--limit N] [--max-seconds N]'
  );
}

async function main() {
  const { flags, pos } = parseArgs(process.argv.slice(2));
  const [jdFile, candDir, outPath, prefix] = pos;
  if (!jdFile || !candDir) {
    usage();
    process.exit(2);
  }
  if (flags.mergeOnly && flags.force) {
    console.error('--merge-only 与 --force 不能同时用');
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
  if (
    !flags.mergeOnly &&
    !process.env.XIAOMI_API_KEY &&
    !process.env.LLM_API_KEY &&
    !process.env.DEEPSEEK_API_KEY
  ) {
    console.error('未设置 XIAOMI_API_KEY / LLM_API_KEY');
    process.exit(2);
  }

  const jdText = fs.readFileSync(jdFile, 'utf8');
  const jdName = path.basename(jdFile);
  const jdSha = sha256Text(jdText);
  const files = fs
    .readdirSync(candDir)
    .filter((f) => {
      if (!f.endsWith('.json')) return false;
      if (f.startsWith('score-') || f.startsWith('ranking-')) return false;
      if (prefix) return f.startsWith(prefix);
      return true;
    })
    .sort();

  let poolDir = candDir;
  let poolFiles = files;
  if (poolFiles.length === 0 && path.basename(path.resolve(candDir)) === 'clean') {
    const parent = path.dirname(path.resolve(candDir));
    const fromRoot = fs
      .readdirSync(parent)
      .filter((f) => f.startsWith('clean-') && f.endsWith('.json'))
      .sort();
    if (fromRoot.length) {
      console.log(
        `   提示：${candDir} 为空，改用 ${parent}/clean-*.json（${fromRoot.length} 份）`
      );
      poolDir = parent;
      poolFiles = fromRoot;
    }
  }

  console.log(`📊 批量评分 · scoring-candidates`);
  console.log(`   JD：${jdName}`);
  console.log(`   scorer_version：${SCORER_VERSION}`);
  console.log(
    `   候选人池：${poolFiles.length} 份${prefix ? `（前缀 ${prefix}）` : ''}` +
      `${flags.mergeOnly ? ' · merge-only' : ''}` +
      `${flags.force ? ' · force' : ''}` +
      `${flags.staleOnly ? ' · stale-only' : ''}` +
      `${flags.limit ? ` · limit ${flags.limit}` : ''}` +
      `${flags.maxSeconds ? ` · max-seconds ${flags.maxSeconds}` : ''}\n`
  );

  const results = [];
  const failed = [];
  const pendingRescore = [];
  const skippedCached = [];
  let llmUsed = 0;
  const t0 = Date.now();

  for (let i = 0; i < poolFiles.length; i++) {
    const f = poolFiles[i];
    const full = path.join(poolDir, f);
    console.log(`--- [${i + 1}/${poolFiles.length}] ${f} ---`);
    let candidate;
    let cleanRaw;
    try {
      cleanRaw = fs.readFileSync(full, 'utf8');
      candidate = JSON.parse(cleanRaw);
    } catch (e) {
      console.log(`  ✗ JSON 无法解析，标记待人工处理：${e.message}`);
      failed.push(f);
      continue;
    }
    const cleanSha = sha256Text(cleanRaw);
    const outScorePath = scorePathFor(full);

    let cached = null;
    const existing = readExistingScore(full);
    if (existing) {
      cached = existing.json;
    }

    const fresh =
      !flags.force && cached && isFresh(cached, { jdSha, cleanSha, version: SCORER_VERSION });

    if (fresh) {
      const score = stripCache(cached);
      if (flags.staleOnly) {
        console.log(
          `  skip 缓存新鲜（stale-only 不纳入本榜）综合分 ${score.jd_match_score}`
        );
        skippedCached.push(f);
        continue;
      }
      const action = suggestedAction(score);
      console.log(
        `  skip 缓存 综合分 ${score.jd_match_score} | 评级 ${score.overall_rating} | ${action}`
      );
      skippedCached.push(f);
      results.push({
        resume_json: full,
        name: score.candidate_name || candidate.name || f,
        parsed: candidate,
        score,
        suggested_action: action,
      });
      continue;
    }

    if (flags.mergeOnly) {
      const why = !cached
        ? '无 score 文件'
        : `缓存失效（version/JD/clean 不一致，现 scorer_version=${SCORER_VERSION}）`;
      console.log(`  pending 重评：${why}`);
      pendingRescore.push({ file: f, reason: why });
      continue;
    }

    if (flags.limit != null && llmUsed >= flags.limit) {
      console.log('  已达 --limit，本进程不再调 LLM');
      pendingRescore.push({ file: f, reason: 'limit' });
      continue;
    }
    if (flags.maxSeconds != null && (Date.now() - t0) / 1000 >= flags.maxSeconds) {
      console.log('  已达 --max-seconds，本进程停止调 LLM');
      pendingRescore.push({ file: f, reason: 'max-seconds' });
      continue;
    }

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
    llmUsed += 1;
    const stored = attachCache(score, {
      jdName,
      jdSha,
      cleanSha,
      version: SCORER_VERSION,
    });
    fs.writeFileSync(outScorePath, JSON.stringify(stored, null, 2), 'utf8');
    console.log(`  已写出 ${outScorePath}`);

    const action = suggestedAction(score);
    console.log(
      `  综合分 ${score.jd_match_score} | 评级 ${score.overall_rating}` +
        `${score.hard_issues && score.hard_issues.length ? ' | ⚠硬伤 ' + JSON.stringify(score.hard_issues) : ''}` +
        ` | ${action}`
    );
    results.push({
      resume_json: full,
      name: score.candidate_name || candidate.name || f,
      parsed: candidate,
      score,
      suggested_action: action,
    });
  }

  results.sort((a, b) => b.score.jd_match_score - a.score.jd_match_score);

  console.log(`\n${'='.repeat(60)}`);
  console.log(`初筛排序结果（按综合匹配分降序）—— ${jdName}`);
  if (pendingRescore.length) {
    console.log(
      `⚠ 未纳入本榜（待重评 ${pendingRescore.length}）：勿与已评人混成终榜`
    );
    pendingRescore.forEach((p) => console.log(`   - ${p.file} (${p.reason})`));
  }
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
  console.log(
    `本进程 LLM 调用 ${llmUsed} 次，缓存命中 ${skippedCached.length}，待重评 ${pendingRescore.length}`
  );
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
      scorer_version: SCORER_VERSION,
      candidate_count: results.length,
      llm_calls: llmUsed,
      failed_candidates: failed,
      pending_rescore: pendingRescore,
      cached_skipped: skippedCached,
      ranking,
      details: results,
    };
    fs.writeFileSync(outPath, JSON.stringify(payload, null, 2), 'utf8');
    console.log(`\n完整结果已保存：${outPath}`);
  }
  process.exit(0);
}

if (require.main === module) main();
