#!/usr/bin/env node
/**
 * search_ima_policies.cjs — er-admin 政策答疑：指定 IMA 知识库的「正文全文检索」
 *
 * 对齐 playground ima-skills（knowledge-base）读原文路径：
 *   get_knowledge_list → get_media_info
 *     → url_info.url(+headers) 拉 Markdown/TXT 等原文
 *     → 或 media_type=11 时 notes get_doc_content
 * 然后在本地对正文任意段落做全文匹配（不依赖 search_knowledge 的标题召回）。
 *
 * 用法:
 *   node search_ima_policies.cjs "<员工问题>"
 *   node search_ima_policies.cjs --list-kb
 *   node search_ima_policies.cjs --refresh-cache "<问题>"   # 强制重拉原文
 *
 * 环境变量（必填）:
 *   IMA_OPENAPI_CLIENTID 或 IMA_CLIENT_ID
 *   IMA_OPENAPI_APIKEY    或 IMA_API_KEY
 *
 * 可选:
 *   IMA_HR_KNOWLEDGE_BASE_ID  固定 HR 政策知识库 ID（推荐）
 *   IMA_BASE_URL              默认 https://ima.qq.com
 *   IMA_FULLTEXT_TOP_K        返回命中文档数，默认 5
 *   IMA_FULLTEXT_SNIPPETS     每篇最多片段数，默认 4
 *   IMA_CONTENT_CACHE_DIR     原文缓存目录（默认 <cwd>/memory/hr-policies/.ima-content-cache）
 *   IMA_CONTENT_CACHE_TTL_SEC 缓存秒数，默认 86400；0=禁用缓存
 *   IMA_FETCH_CONCURRENCY     并行拉原文数，默认 4
 */
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const BASE = process.env.IMA_BASE_URL || 'https://ima.qq.com';
const TOP_K = Math.max(1, parseInt(process.env.IMA_FULLTEXT_TOP_K || '5', 10) || 5);
const SNIPPETS_PER_DOC = Math.max(
  1,
  parseInt(process.env.IMA_FULLTEXT_SNIPPETS || '4', 10) || 4,
);
const CACHE_TTL_SEC = Math.max(
  0,
  parseInt(process.env.IMA_CONTENT_CACHE_TTL_SEC || '86400', 10) || 0,
);
const FETCH_CONCURRENCY = Math.max(
  1,
  parseInt(process.env.IMA_FETCH_CONCURRENCY || '4', 10) || 4,
);

function creds() {
  const clientId =
    process.env.IMA_OPENAPI_CLIENTID || process.env.IMA_CLIENT_ID || '';
  const apiKey =
    process.env.IMA_OPENAPI_APIKEY || process.env.IMA_API_KEY || '';
  if (!clientId || !apiKey) {
    console.error(
      JSON.stringify({
        ok: false,
        error:
          '缺少 IMA 凭证：请设置 IMA_OPENAPI_CLIENTID 与 IMA_OPENAPI_APIKEY（或 IMA_CLIENT_ID / IMA_API_KEY）',
      }),
    );
    process.exit(2);
  }
  return { clientId, apiKey };
}

async function imaPost(apiPath, body, { clientId, apiKey }) {
  const res = await fetch(`${BASE}/${apiPath}`, {
    method: 'POST',
    headers: {
      'ima-openapi-clientid': clientId,
      'ima-openapi-apikey': apiKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text || '{}');
  } catch {
    throw new Error(`IMA 返回非 JSON (HTTP ${res.status}): ${text.slice(0, 200)}`);
  }
  if (!res.ok) {
    throw new Error(`IMA HTTP ${res.status}: ${text.slice(0, 300)}`);
  }
  return data;
}

function normKb(k) {
  if (!k) return null;
  return {
    id: k.id || k.kb_id || '',
    name: k.name || k.kb_name || '',
    raw: k,
  };
}

function pickKb(list) {
  const normalized = list.map(normKb).filter((k) => k && k.id);
  const fixed = process.env.IMA_HR_KNOWLEDGE_BASE_ID;
  if (fixed) {
    const hit = normalized.find((k) => k.id === fixed);
    if (hit) return hit;
    return { id: fixed, name: '(IMA_HR_KNOWLEDGE_BASE_ID)' };
  }
  const re = /政策|HR|人事|行政|helpdesk|员工手册|制度|示例科技|hr_er/i;
  const preferred = normalized.find((k) => re.test(k.name || ''));
  return preferred || normalized[0] || null;
}

async function listKnowledgeBases(c) {
  const all = [];
  let cursor = '';
  for (let i = 0; i < 10; i++) {
    const resp = await imaPost(
      'openapi/wiki/v1/search_knowledge_base',
      { query: '', cursor, limit: 20 },
      c,
    );
    const rows = (resp.data && resp.data.info_list) || resp.info_list || [];
    all.push(...rows);
    const ended = resp.data ? resp.data.is_end : resp.is_end;
    const next = resp.data ? resp.data.next_cursor : resp.next_cursor;
    if (ended || !next || rows.length === 0) break;
    cursor = next;
  }
  return all;
}

/** ima-skills: get_knowledge_list 浏览知识库全部文件（递归子文件夹） */
async function listAllMedia(c, kbId, folderId) {
  const out = [];
  let cursor = '';
  for (let page = 0; page < 50; page++) {
    const body = {
      knowledge_base_id: kbId,
      cursor,
      limit: 50,
    };
    if (folderId) body.folder_id = folderId;
    const resp = await imaPost('openapi/wiki/v1/get_knowledge_list', body, c);
    const data = resp.data || resp;
    const rows = data.knowledge_list || [];
    const folders = data.folder_list || [];
    for (const r of rows) {
      if (r && r.media_id && r.title) {
        out.push({
          media_id: r.media_id,
          title: r.title,
          parent_folder_id: r.parent_folder_id || '',
          media_type: r.media_type,
        });
      }
      // 部分实现把文件夹混在 knowledge_list
      if (r && r.folder_id && r.name && !r.media_id) {
        folders.push(r);
      }
    }
    for (const f of folders) {
      const fid = f.folder_id || f.id;
      if (fid && fid !== folderId && fid !== kbId) {
        const nested = await listAllMedia(c, kbId, fid);
        out.push(...nested);
      }
    }
    if (data.is_end || !data.next_cursor || rows.length === 0) break;
    cursor = data.next_cursor;
  }
  // 去重
  const map = new Map();
  for (const m of out) map.set(m.media_id, m);
  return [...map.values()];
}

/**
 * ima-skills「获取媒体原文」:
 * - url_info.url + headers → 拉原文
 * - media_type=11 → notes get_doc_content
 */
async function fetchMediaText(c, mediaId) {
  const resp = await imaPost(
    'openapi/wiki/v1/get_media_info',
    { media_id: mediaId },
    c,
  );
  if (resp.code && resp.code !== 0) {
    throw new Error(resp.msg || `get_media_info code=${resp.code}`);
  }
  const data = resp.data || {};
  const mediaType = data.media_type;

  if (
    mediaType === 11 &&
    data.notebook_ext_info &&
    data.notebook_ext_info.notebook_id
  ) {
    const noteId = data.notebook_ext_info.notebook_id;
    const noteResp = await imaPost(
      'openapi/note/v1/get_doc_content',
      { note_id: noteId },
      c,
    );
    if (noteResp.code && noteResp.code !== 0) {
      throw new Error(noteResp.msg || `get_doc_content code=${noteResp.code}`);
    }
    const content =
      (noteResp.data && (noteResp.data.content || noteResp.data.text)) ||
      noteResp.content ||
      '';
    return { text: String(content), media_type: mediaType, via: 'get_doc_content' };
  }

  const urlInfo = data.url_info || {};
  const url = urlInfo.url || data.url;
  if (!url) {
    throw new Error('无 url_info，请使用 IMA 客户端查看原文');
  }
  const headers = { ...(urlInfo.headers || {}) };
  const res = await fetch(url, { headers });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`拉取原文 HTTP ${res.status}: ${text.slice(0, 160)}`);
  }
  return { text, media_type: mediaType, via: 'url_info' };
}

function resolveCacheDir() {
  if (process.env.IMA_CONTENT_CACHE_DIR) {
    return process.env.IMA_CONTENT_CACHE_DIR;
  }
  const candidates = [
    path.resolve(process.cwd(), 'memory/hr-policies/.ima-content-cache'),
    path.resolve(__dirname, '../../../memory/hr-policies/.ima-content-cache'),
  ];
  for (const d of candidates) {
    try {
      fs.mkdirSync(d, { recursive: true });
      return d;
    } catch {
      /* try next */
    }
  }
  const tmp = path.join(require('os').tmpdir(), 'ima-hr-content-cache');
  fs.mkdirSync(tmp, { recursive: true });
  return tmp;
}

function cachePath(cacheDir, mediaId) {
  const h = crypto.createHash('sha1').update(mediaId).digest('hex');
  return path.join(cacheDir, `${h}.json`);
}

async function loadDocText(c, media, { refresh, cacheDir }) {
  const fp = cachePath(cacheDir, media.media_id);
  if (!refresh && CACHE_TTL_SEC > 0 && fs.existsSync(fp)) {
    try {
      const cached = JSON.parse(fs.readFileSync(fp, 'utf8'));
      const age = (Date.now() - (cached.fetched_at || 0)) / 1000;
      if (age >= 0 && age <= CACHE_TTL_SEC && typeof cached.text === 'string') {
        return {
          text: cached.text,
          media_type: cached.media_type ?? media.media_type,
          via: 'cache',
          from_cache: true,
        };
      }
    } catch {
      /* refetch */
    }
  }
  const got = await fetchMediaText(c, media.media_id);
  if (CACHE_TTL_SEC > 0) {
    try {
      fs.writeFileSync(
        fp,
        JSON.stringify({
          media_id: media.media_id,
          title: media.title,
          media_type: got.media_type,
          fetched_at: Date.now(),
          text: got.text,
        }),
        'utf8',
      );
    } catch {
      /* ignore cache write */
    }
  }
  return { ...got, from_cache: false };
}

async function mapPool(items, concurrency, fn) {
  const results = new Array(items.length);
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await fn(items[idx], idx);
    }
  }
  const n = Math.min(concurrency, Math.max(1, items.length));
  await Promise.all(Array.from({ length: n }, () => worker()));
  return results;
}

/** 领域短词白名单（允许 2 字参与打分；普通 2-gram 太噪不采用） */
const DOMAIN_BIGRAMS = new Set([
  '年假', '病假', '婚假', '产假', '事假', '调休', '加班', '考勤', '打卡',
  '弹性', '远程', '居家', '社保', '公积金', '薪酬', '工资', '个税', '试用',
  '转正', '入职', '离职', '绩效', '报销', '差旅', '培训', '晋升', '福利',
  '仲裁', '辞退', '合同', '迟到', '早退', '缺勤', '工时', '坐班',
]);

/** 从查询抽出用于正文匹配的词（偏长词/领域词，覆盖正文任意位置） */
function queryTerms(query) {
  const terms = new Set();
  const raw = String(query || '').trim();
  if (!raw) return [];

  const cleaned = raw
    .replace(/[？?！!。，、；;：:\s]+/g, ' ')
    .replace(/(吗|呢|啊|吧|嘛|帮我|请问|一下|是什么|怎么|如何|是否)/g, ' ')
    .trim();

  if (cleaned.length >= 2) terms.add(cleaned);
  for (const part of cleaned.split(/\s+/)) {
    if (part.length >= 2) terms.add(part);
  }

  const compact = cleaned.replace(/\s+/g, '');
  // 3～6 字连续片段：足以命中正文任意位置，又避免「工作」类 2 字噪声
  for (let n = 3; n <= Math.min(6, compact.length); n++) {
    for (let i = 0; i + n <= compact.length; i++) {
      const gram = compact.slice(i, i + n);
      if (/[\u4e00-\u9fff]/.test(gram)) terms.add(gram);
    }
  }
  // 2 字仅保留领域白名单
  for (let i = 0; i + 2 <= compact.length; i++) {
    const bi = compact.slice(i, i + 2);
    if (DOMAIN_BIGRAMS.has(bi)) terms.add(bi);
  }

  // 轻量同义扩展：问句含「弹性工作」时正文常写「弹性与远程 / 远程办公」
  if (/弹性/.test(compact)) {
    terms.add('弹性');
    terms.add('远程');
    terms.add('远程办公');
  }
  if (/公积金|住房公积/.test(compact)) {
    terms.add('住房公积金');
    terms.add('公积金');
    terms.add('缴存');
  }
  if (/年假|清零|结转/.test(compact)) {
    terms.add('年假');
    terms.add('结转');
  }

  for (const bad of ['公司的', '公司', '政策', '规定', '多少', '什么', '如何', '可以', '有没有', '政策是']) {
    terms.delete(bad);
  }

  return [...terms].sort((a, b) => b.length - a.length).slice(0, 48);
}

/** 去掉空白与常见标点，便于「6 月 30 日」对上「6月30日」、「弹性与远程」对上「弹性」 */
function compactText(s) {
  return String(s || '')
    .replace(/\s+/g, '')
    .replace(/[，。？！、：；·\-_/（）()【】\[\]《》"'`]/g, '');
}

function splitChunks(text) {
  const norm = String(text || '').replace(/\r\n/g, '\n');
  const paras = norm
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length >= 8);

  // 单行块也纳入（表格行、短 FAQ）
  const lines = norm
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length >= 6 && !/^#{1,6}\s/.test(l));

  const chunks = [];
  const seen = new Set();
  for (const c of [...paras, ...lines]) {
    const key = c.slice(0, 120);
    if (seen.has(key)) continue;
    seen.add(key);
    chunks.push(c);
  }
  return chunks;
}

function scoreChunk(chunk, terms) {
  let score = 0;
  const hits = [];
  const chunkCompact = compactText(chunk);
  for (const t of terms) {
    if (!t) continue;
    const tc = compactText(t);
    if (!tc) continue;
    if (chunk.includes(t) || (tc.length >= 2 && chunkCompact.includes(tc))) {
      const weight = tc.length >= 5 ? 8 : tc.length >= 4 ? 5 : tc.length >= 3 ? 3 : 2;
      score += weight;
      hits.push(t);
    }
  }
  // 领域二字词（如「弹性」「年假」）单独即可命中；普通噪声 2-gram 已不进 terms
  if (hits.length === 0) return { score: 0, hits: [] };
  return { score, hits };
}

function fulltextSearchDocs(docs, query) {
  const terms = queryTerms(query);
  if (terms.length === 0) return [];

  const scoredDocs = [];
  for (const doc of docs) {
    if (!doc.text) continue;
    const chunks = splitChunks(doc.text);
    const chunkHits = [];
    for (const chunk of chunks) {
      const { score, hits } = scoreChunk(chunk, terms);
      if (score > 0) chunkHits.push({ chunk, score, matched_terms: hits });
    }
    if (chunkHits.length === 0) {
      // 整篇子串兜底（极短查询）
      const whole = scoreChunk(doc.text, terms.filter((t) => t.length >= 2).slice(0, 12));
      if (whole.score > 0) {
        chunkHits.push({
          chunk: doc.text.slice(0, 600),
          score: whole.score,
          matched_terms: whole.hits,
        });
      }
    }
    if (chunkHits.length === 0) continue;

    chunkHits.sort((a, b) => b.score - a.score);
    const top = chunkHits.slice(0, SNIPPETS_PER_DOC);
    const docScore = top.reduce((s, x) => s + x.score, 0);
    const highlight = top.map((x) => x.chunk).join('\n\n---\n\n');
    scoredDocs.push({
      media_id: doc.media_id,
      title: doc.title,
      parent_folder_id: doc.parent_folder_id || '',
      media_type: doc.media_type,
      score: docScore,
      matched_terms: [...new Set(top.flatMap((x) => x.matched_terms))],
      highlight,
      content_excerpt: doc.text.slice(0, 4000),
      content_chars: doc.text.length,
      content_source: `fulltext:${doc.via || 'get_media_info'}`,
      snippet_count: top.length,
    });
  }

  scoredDocs.sort((a, b) => b.score - a.score);
  return scoredDocs.slice(0, TOP_K);
}

async function main() {
  const args = process.argv.slice(2);
  const c = creds();

  if (args[0] === '--list-kb') {
    const kbs = await listKnowledgeBases(c);
    console.log(
      JSON.stringify(
        {
          ok: true,
          knowledge_bases: kbs.map(normKb),
          tip: '将 HR 政策库的 id 写入环境变量 IMA_HR_KNOWLEDGE_BASE_ID',
        },
        null,
        2,
      ),
    );
    return;
  }

  let refresh = false;
  let qArgs = args;
  if (args[0] === '--refresh-cache') {
    refresh = true;
    qArgs = args.slice(1);
  }

  const query = qArgs.join(' ').trim();
  if (!query) {
    console.error(
      JSON.stringify({
        ok: false,
        error:
          '用法: node search_ima_policies.cjs "<问题>" | --list-kb | --refresh-cache "<问题>"',
      }),
    );
    process.exit(2);
  }

  const kbs = await listKnowledgeBases(c);
  const kb = pickKb(kbs);
  if (!kb) {
    console.log(
      JSON.stringify({
        ok: false,
        error: '账号下未找到任何 IMA 知识库。请先在 IMA 创建并上传 HR 政策文档。',
        knowledge_bases: [],
      }),
    );
    process.exit(1);
  }

  const mediaList = await listAllMedia(c, kb.id);
  if (mediaList.length === 0) {
    console.log(
      JSON.stringify({
        ok: false,
        error: `知识库「${kb.name}」为空，请先上传政策文档。`,
        knowledge_base: { id: kb.id, name: kb.name },
      }),
    );
    process.exit(1);
  }

  const cacheDir = resolveCacheDir();
  const loaded = await mapPool(mediaList, FETCH_CONCURRENCY, async (m) => {
    try {
      const body = await loadDocText(c, m, { refresh, cacheDir });
      return {
        ...m,
        text: body.text,
        media_type: body.media_type ?? m.media_type,
        via: body.via,
        from_cache: body.from_cache,
        error: null,
      };
    } catch (e) {
      return { ...m, text: '', error: String(e.message || e) };
    }
  });

  const docs = loaded.filter((d) => d.text && d.text.trim());
  const failed = loaded.filter((d) => d.error);
  const hits = fulltextSearchDocs(docs, query);

  const out = {
    ok: true,
    knowledge_base: { id: kb.id, name: kb.name },
    query,
    search_mode: 'fulltext_content',
    docs_indexed: docs.length,
    docs_failed: failed.length,
    cache_dir: cacheDir,
    query_terms: queryTerms(query).slice(0, 16),
    hit_count: hits.length,
    hits,
    note:
      '正文全文检索：list 全库 → get_media_info 拉原文 → 本地匹配任意片段（对齐 ima-skills 读原文路径）。关键数字只能来自 highlight/content_excerpt。',
    warning:
      hits.length === 0
        ? '全文检索未命中任何正文片段。若问题超出政策库覆盖范围，按第 4 类红线转人工，禁止用通用知识硬答。'
        : failed.length
          ? `${failed.length} 篇原文拉取失败（不影响已命中结果）。`
          : undefined,
    cite_hint:
      '出处优先用 hits[].title；关键数字只能来自 highlight / content_excerpt，禁止脑补。',
  };
  console.log(JSON.stringify(out, null, 2));
  if (hits.length === 0) process.exit(1);
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e.message || e) }));
  process.exit(1);
});
