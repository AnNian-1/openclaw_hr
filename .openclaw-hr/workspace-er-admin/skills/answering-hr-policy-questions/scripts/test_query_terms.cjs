#!/usr/bin/env node
'use strict';
const { queryTerms } = require('./search_ima_policies.cjs');

const terms = queryTerms('报销流程怎么走');
const need = ['报销', '差旅', '出差'];
const missing = need.filter((t) => !terms.includes(t));
if (missing.length) {
  console.error('missing synonyms', missing, 'got', terms);
  process.exit(1);
}
const travel = queryTerms('差旅标准');
if (!travel.includes('报销') || !travel.includes('出差')) {
  console.error('差旅 query missing 报销/出差', travel);
  process.exit(1);
}
console.log('ok');
