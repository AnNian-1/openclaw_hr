#!/usr/bin/env node
/**
 * validate_transcript.js — 面试转写产物校验器
 *
 * 用途：transcribing-interviews Skill 的校验闭环。transcribe_diarize.py
 *       产出转写 JSON 后，用本脚本校验，跑通才算转写合格。把"转写产物
 *       结构对不对、说话人分离结果有没有明显异常"这件确定性的事从 LLM 手里
 *       收回到脚本里——脚本转写，脚本把关。
 *
 * 为什么需要这一道闸：转写产物是面试纪要链路的地基。一份片段为空、
 * 或说话人全归到一类的转写稿，下游 LLM 整理出的纪要必然是错的，但
 * LLM "读一遍觉得差不多"发现不了——它没有"片段数是否合理""说话人
 * 是否分出 ≥ 2 类"这种结构化判断标准。校验器把这些标准固定下来。
 *
 * schema (FunASR + CAM++ 产出):
 *   {
 *     audio: str,
 *     model: "paraformer" | ...,
 *     diarization_method: "funasr-cam++",
 *     spk_campplus_used: true,
 *     device: "cuda:0" | "cpu",
 *     batch_size_s: int,
 *     model_path: str,
 *     wall_sec: float,
 *     segments: [
 *       {start, end, text, spk_int, speaker}   // speaker 形如 speaker_A / speaker_B / speaker_C
 *     ]
 *   }
 *
 * 校验项：
 *   1. JSON 可解析
 *   2. 顶层字段齐全：audio / segments / diarization_method (FunASR schema)
 *   3. segments 非空，每段含 start / end / text / speaker (spk_int 可选溯源)
 *   4. 时间戳自洽：start <= end，片段按时间递增
 *   5. 文本非空片段占比 —— 整段空文本说明转写失败
 *   6. 说话人分离健康度：diarization_method=funasr-cam++ 时，
 *      至少分出 2 个说话人，且没有一方占比畸高（>92% 视为分离失败）
 *
 * CLI：node validate_transcript.js <transcript.json>
 *   退出码 0 = 校验通过；1 = 校验失败（stderr 列出全部问题）；2 = 用法错误
 */

'use strict';
const fs = require('fs');

// 单一说话人占比超过此阈值，判为分离失败（面试问答不可能一方说 92%+）。
// 留足空间只拦"全归一类"——候选人的话可能多一些，但不会到 92%。
const SPEAKER_DOMINANCE_MAX = 0.92;
// 空文本片段占比超过此阈值，判为转写质量异常。
const EMPTY_TEXT_MAX = 0.3;

function fail(problems) {
  console.error('❌ 面试转写产物校验未通过：');
  problems.forEach((p, i) => console.error(`  ${i + 1}. ${p}`));
  process.exit(1);
}

function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('用法: node validate_transcript.js <transcript.json>');
    process.exit(2);
  }
  if (!fs.existsSync(file)) {
    console.error(`ERROR: 文件不存在: ${file}`);
    process.exit(2);
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (e) {
    fail([`JSON 无法解析: ${e.message}`]);
  }

  const problems = [];

  // 2. 顶层字段（FunASR schema）
  ['audio', 'segments', 'diarization_method'].forEach((k) => {
    if (!(k in data)) problems.push(`缺少顶层字段: ${k}`);
  });

  const segs = data.segments;
  if (!Array.isArray(segs) || segs.length === 0) {
    fail([...problems, 'segments 为空或不是数组——转写未产出任何片段']);
  }

  // 3-4. 逐段结构 + 时间戳自洽
  let prevEnd = -1;
  let emptyCount = 0;
  segs.forEach((s, idx) => {
    ['start', 'end', 'text', 'speaker'].forEach((k) => {
      if (!(k in s)) problems.push(`segments[${idx}] 缺少字段: ${k}`);
    });
    if (typeof s.start === 'number' && typeof s.end === 'number') {
      if (s.start > s.end) {
        problems.push(`segments[${idx}] 时间戳倒置: start=${s.start} > end=${s.end}`);
      }
      if (s.start < prevEnd - 0.5) {
        problems.push(`segments[${idx}] 起始时间早于上一段结束，片段未按时间递增`);
      }
      prevEnd = s.end;
    }
    if (typeof s.text === 'string' && s.text.trim() === '') emptyCount += 1;
  });

  // 5. 空文本占比
  const emptyRatio = emptyCount / segs.length;
  if (emptyRatio > EMPTY_TEXT_MAX) {
    problems.push(
      `空文本片段占比 ${(emptyRatio * 100).toFixed(0)}% 过高`
      + `（${emptyCount}/${segs.length}）——转写质量异常`);
  }

  // 6. 说话人分离健康度（FunASR + CAM++）
  if (data.diarization_method === 'funasr-cam++') {
    const counts = {};
    segs.forEach((s) => {
      const k = s.speaker;
      counts[k] = (counts[k] || 0) + 1;
    });
    const speakers = Object.keys(counts).filter((k) => k && k !== 'unknown');
    if (speakers.length < 2) {
      problems.push(
        `说话人分离只分出 ${speakers.length} 类（${speakers.join(', ') || '无'}）`
        + `——CAM++ 聚类失败，所有片段归到了同一说话人`);
    } else {
      const validSegs = segs.filter((s) => speakers.includes(s.speaker));
      const validCount = validSegs.length || 1;
      const maxCount = Math.max(...speakers.map((k) => counts[k]));
      const dominance = maxCount / validCount;
      if (dominance > SPEAKER_DOMINANCE_MAX) {
        problems.push(
          `单一说话人占比 ${(dominance * 100).toFixed(0)}% 过高`
          + `——CAM++ 聚类可能未分离干净，请检查音频或切分`);
      }
    }
  } else if (data.diarization_method && data.diarization_method !== 'funasr-cam++') {
    // 旧版 (faster-whisper + F0) 已废弃——为防止有人误用，向前报警
    problems.push(
      `diarization_method=${data.diarization_method} 是旧版 (faster-whisper + F0) 输出, `
      + `请改用新版 FunASR + CAM++ 重新跑 transcribe_diarize.py`);
  }

  if (problems.length > 0) fail(problems);

  // 全部通过——打汇总
  const counts = {};
  segs.forEach((s) => { counts[s.speaker] = (counts[s.speaker] || 0) + 1; });
  console.log('✅ 面试转写产物校验通过');
  console.log(`   音频: ${data.audio}`);
  console.log(`   diarization: ${data.diarization_method}`
    + ` (model=${data.model || '?'}, device=${data.device || '?'}`
    + `, wall=${data.wall_sec || '?'}s)`);
  console.log(`   片段总数: ${segs.length}  空文本: ${emptyCount}`);
  Object.entries(counts).forEach(([spk, n]) => {
    console.log(`     ${spk}: ${n} 段`);
  });
  process.exit(0);
}

main();
