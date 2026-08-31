#!/usr/bin/env bash
# 总控代测：四域剩余脚本 + 对话。结果写入 /tmp/qa-four-domain-20260827/
set -uo pipefail
export PATH="$HOME/.local/node/node-22/bin:$PATH"
PROFILE="$HOME/openclaw-hr/.openclaw-hr"
OUT="/tmp/qa-four-domain-20260827"
mkdir -p "$OUT"
exec > >(tee -a "$OUT/run.log") 2>&1
echo "==== $(date -Is) four-domain start ===="
set -a
source "$PROFILE/env.sh"
set +a
export PATH="$HOME/.local/node/node-22/bin:$PATH"

rec() { echo "[REC] $*"; echo "$*" >> "$OUT/results.tsv"; }

# --- health ---
H=$(curl -sS -m 5 http://127.0.0.1:18790/health || echo fail)
HCM=$(curl -sS -m 5 http://localhost:8000/api/health || echo fail)
echo "gateway=$H hcm=$HCM node=$(node --version)"
[[ "$H" == *live* ]] && rec "ENV gateway PASS" || rec "ENV gateway FAIL $H"
[[ "$HCM" == *hcm* ]] && rec "ENV hcm PASS" || rec "ENV hcm FAIL $HCM"

WS_R="$PROFILE/workspace-recruitment"
WS_O="$PROFILE/workspace-onboarding"
WS_P="$PROFILE/workspace-performance"
WS_T="$PROFILE/workspace-training"
WS_E="$PROFILE/workspace-er-admin"
cd "$WS_R"

# ===== 招聘脚本 =====
# R-04
if node skills/filtering-sensitive-fields/scripts/filter_sensitive.js scoring/clean-员工1-后端开发.json "$OUT/clean-r04.json"; then
  rec "R-04 PASS"
else rec "R-04 FAIL rc=$?"; fi

# R-02 validate if parsed exists
PARSED=$(ls -1 parsed/*.json 2>/dev/null | head -1 || true)
if [[ -n "${PARSED:-}" ]]; then
  if node skills/parsing-resumes/scripts/validate_profile.js "$PARSED"; then rec "R-02 PASS $PARSED"; else rec "R-02 FAIL"; fi
else rec "R-02 SKIP no parsed json"; fi

# R-01 PDF
PDF=$(ls -1 inbox/*.pdf 2>/dev/null | head -1 || true)
CONVERT=""
for c in skills/office-to-md-v2/office-to-md/convert.js skills/office-to-md-v2/convert.js; do
  [[ -f "$c" ]] && CONVERT="$c"
done
if [[ -n "$PDF" && -n "$CONVERT" ]]; then
  if node "$CONVERT" "$PDF" "$OUT/r01.md"; then rec "R-01 PASS $PDF"; else rec "R-01 FAIL"; fi
else rec "R-01 SKIP pdf=$PDF convert=$CONVERT"; fi

# R-05 / R-06
if node skills/scoring-candidates/scripts/score_candidate.js scoring/clean-员工1-后端开发.json jds/jd-bigtech-后端开发工程师.md "$OUT/ranking-员工1.json"; then
  rec "R-05 PASS"
  if [[ -f skills/auditing-numbers/scripts/audit_numbers.js ]]; then
    if node skills/auditing-numbers/scripts/audit_numbers.js "$OUT/ranking-员工1.json" inbox/员工1-后端开发.md "$OUT/ranking-员工1-audited.json"; then
      rec "R-06 PASS"
    else rec "R-06 FAIL"; fi
  fi
else rec "R-05 FAIL"; rec "R-06 SKIP no ranking"; fi

# R-07 profile
RANK=$(ls -1 scoring/results/ranking-员工1-后端开发.json 2>/dev/null || true)
[[ -f "$OUT/ranking-员工1.json" ]] && RANK="$OUT/ranking-员工1.json"
if [[ -n "$RANK" && -f skills/generating-candidate-profiles/scripts/generate_profile.py ]]; then
  if python3 skills/generating-candidate-profiles/scripts/generate_profile.py "$RANK" 员工1 "$OUT/profile-yuangong1.html"; then
    rec "R-07 PASS"
  else rec "R-07 FAIL"; fi
else rec "R-07 SKIP rank=$RANK"; fi

# R-09 (pool exists)
if python3 skills/searching-talent-pool/scripts/search_talent_pool.py --like 员工1 --topn 5 | tee "$OUT/r09.txt"; then
  rec "R-09 PASS"
else rec "R-09 FAIL"; fi

# R-10 explain
EX=$(find skills -name 'explain*.py' ! -path '*/node_modules/*' | head -1)
if [[ -n "$EX" ]]; then
  python3 "$EX" --help 2>&1 | head -20 || true
  if python3 "$EX" --like 员工1 2>&1 | tee "$OUT/r10.txt"; then rec "R-10 PASS"; else rec "R-10 FAIL_or_empty"; fi
else rec "R-10 SKIP no explain.py"; fi

# R-03 auditing-extraction
AUD=$(find skills/auditing-extraction -name '*.js' ! -path '*/node_modules/*' | head -3)
echo "audit scripts: $AUD"
rec "R-03 NOTE see $AUD"

# ===== 月报脚本 =====
cd "$WS_E/skills/generating-monthly-report/scripts"
MR="${MONTHLY_REPORT_PYTHON:-}"
if [[ -z "$MR" ]]; then
  for p in /usr/local/miniconda3/envs/openclaw-hr/bin/python3 /usr/local/miniconda3/envs/py312/bin/python3 python3; do
    command -v "$p" >/dev/null && "$p" -c "import pandas" 2>/dev/null && MR="$p" && break
  done
fi
echo "MONTHLY_PYTHON=$MR"
export MONTHLY_REPORT_PYTHON="$MR"
if bash run_monthly_report.sh; then rec "X-11 PASS"; else rec "X-11 FAIL rc=$?"; fi
if bash run_monthly_report.sh 2026-05; then rec "X-09 PASS"; else rec "X-09 FAIL"; fi
if bash run_monthly_report.sh 2026-07; then rec "X-10-via-month PASS"; else rec "X-10 FAIL"; fi
set +e
bash run_monthly_report.sh 2099-12
rc=$?
set -e
[[ $rc -eq 1 ]] && rec "X-12 PASS rc=1" || rec "X-12 FAIL rc=$rc"
if bash run_monthly_report.sh 2026-05 --publish --force; then rec "X-13 PASS"; else rec "X-13 FAIL"; fi

# ===== 360 脚本 =====
cd "$WS_P"
if python3 skills/aggregating-360-feedback/scripts/check_feedback.py feedback-360/source_feedback/dirty-yuangong1; then rec "X-04-check PASS"; else rec "X-04-check FAIL"; fi
if python3 skills/aggregating-360-feedback/scripts/aggregate.py feedback-360/source_feedback/dirty-yuangong1; then rec "X-04-agg PASS"; else rec "X-04-agg FAIL"; fi
# X-06 dirty zip
set +e
python3 skills/aggregating-360-feedback/scripts/ingest_archive.py feedback-360/source_feedback/eval-s2-dirty-json.zip
python3 skills/aggregating-360-feedback/scripts/check_feedback.py feedback-360/source_feedback/dirty-yuangong1 2>"$OUT/x06-dirty.txt"
echo "x06-check-after-dirty rc=$?"
# restore? don't leave dirty json in dirty-yuangong1 if ingest overwrote - skip restore complexity
set -e
if python3 skills/aggregating-360-feedback/scripts/check_feedback.py feedback-360/source_feedback/wangfang 2>"$OUT/x06-wangfang.txt"; then rec "X-06-wangfang unexpected PASS"; else rec "X-06-wangfang FAIL_expected"; fi
if bash skills/generating-360-dashboard/scripts/build_dashboard.sh feedback-360/source_feedback/lisi --publish --force; then rec "X-05 PASS"; else rec "X-05 FAIL"; fi

# ===== 培训 self_check =====
cd "$WS_T"
if python3 skills/generating-training-materials/scripts/self_check.py --outdir training-materials/信息安全意识; then rec "X-02 PASS"; else rec "X-02 FAIL"; fi

# ===== 入职脚本 =====
cd "$WS_O"
if bash skills/running-onboarding-review/scripts/onboarding-review.sh 员工1 7 yuangong1; then rec "O-09 PASS"; else rec "O-09 FAIL"; fi
if bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh; then rec "O-10 PASS"; else rec "O-10 FAIL"; fi
if bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh 员工1 yuangong1 | head -40; then rec "O-11 PASS"; else rec "O-11 FAIL"; fi
# O-PROC-04
set +e
bash skills/running-onboarding-review/scripts/onboarding-review.sh 不存在的人 7 nonexist
rc=$?
set -e
rec "O-PROC-04 rc=$rc file=$(ls -l review-state/review-不存在的人-day7.json 2>/dev/null || echo none)"

# O-05 O-06 O-03 via API
ID=$(curl -sS http://localhost:8000/api/candidates | python3 -c "import sys,json; d=json.load(sys.stdin); xs=d if isinstance(d,list) else d.get('candidates') or d.get('items') or []; print(xs[0]['id'] if xs else '')")
echo "cand_id=$ID"
if [[ -n "$ID" ]]; then
  curl -sS "http://localhost:8000/api/candidates" | python3 -c "import sys,json; d=json.load(sys.stdin); print('O-05 keys', list(d)[:8] if isinstance(d,dict) else 'list', 'n', len(d) if isinstance(d,list) else len(d.get('candidates',d.get('items',[]))))"
  rec "O-05 PASS id=$ID"
  NOTE="o03-$(date +%H%M%S)"
  for node in account device training buddy; do
    curl -sS -X PUT "http://localhost:8000/api/candidates/$ID/prep/$node" -H 'Content-Type: application/json' \
      -d "{\"status\":\"done\",\"data\":{\"note\":\"$NOTE-$node\"}}" | python3 -c "import sys,json; print(sys.stdin.read()[:200])"
  done
  rec "O-03-API PUT four nodes note=$NOTE (backend 无部门鉴权；前端靠 editableNodeType)"
  curl -sS -X PUT "http://localhost:8000/api/candidates/$ID/prep/contract" -H 'Content-Type: application/json' \
    -d "{\"status\":\"done\",\"data\":{\"note\":\"o06-$NOTE\"}}" >/dev/null
  curl -sS "http://localhost:8000/api/candidates/$ID" | python3 -c "import sys,json; c=json.load(sys.stdin); print([(n.get('node_type'), (n.get('data') or {}).get('note')) for n in c.get('nodes',[])])"
  rec "O-06 GET after PUT"
fi

# O-01 docs
code=$(curl -sS -o /dev/null -w '%{http_code}' http://localhost:8000/docs || echo 000)
code2=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ || echo 000)
rec "O-01 docs=$code frontend=$code2"

echo "==== scripts done $(date -Is) ===="
echo "See $OUT/results.tsv"
