#!/usr/bin/env bash
# One-shot: restart gateway (same port), build 1-person talent pool, run gap dialogues.
set -euo pipefail
export PATH="$HOME/.local/node/node-22/bin:$PATH"
PROFILE="$HOME/openclaw-hr/.openclaw-hr"
LOG="/tmp/qa-gap-20260827"
mkdir -p "$LOG"
exec > >(tee -a "$LOG/run.log") 2>&1

echo "==== $(date -Is) start ===="
set -a
source "$PROFILE/env.sh"
set +a
export PATH="$HOME/.local/node/node-22/bin:$PATH:$PATH"

echo "SILICONFLOW_len=${#SILICONFLOW_API_KEY}"
echo "node=$(node --version)"
echo "openclaw=$(command -v openclaw)"

# --- 1. stop gateway on 18790, same port restart (no --force port change) ---
# kill only listeners on 18790
if command -v fuser >/dev/null 2>&1; then
  fuser -k 18790/tcp 2>/dev/null || true
fi
# also kill leftover openclaw gateway processes owned by us (not this script)
pkill -u "$USER" -f 'openclaw gateway run' 2>/dev/null || true
sleep 2
# leftover python proxy
pkill -u "$USER" -f 'ThreadingHTTPServer.*8766' 2>/dev/null || true

# start gateway in background
cd "$PROFILE"
nohup openclaw gateway run >>"$LOG/gateway.log" 2>&1 &
echo "gateway_pid=$!"
for i in $(seq 1 40); do
  if curl -sS -m 2 http://127.0.0.1:18790/health | grep -q live; then
    echo "health_ok after ${i}s"
    break
  fi
  sleep 1
done
curl -sS -m 3 http://127.0.0.1:18790/health || true
echo

# --- 2. talent-pool.json with only 张磊 ---
python3 - <<'PY'
import json, os, glob, time, importlib.util
from pathlib import Path
ws = Path(os.path.expanduser("~/openclaw-hr/.openclaw-hr/workspace-recruitment"))
pool_dir = ws / "talent-pool"
pool_dir.mkdir(parents=True, exist_ok=True)

# find a parsed/clean 张磊 json
cands = []
for p in [
    ws / "scoring/clean-张磊-后端开发.json",
    *glob.glob(str(ws / "scoring/**/*张磊*.json"), recursive=True),
    *glob.glob(str(ws / "profile/**/*张磊*.json"), recursive=True),
]:
    p = Path(p)
    if p.is_file() and "node_modules" not in str(p):
        cands.append(p)
print("json candidates", [str(c) for c in cands[:12]])

parsed = None
src = None
for p in cands:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    # unwrap common wrappers
    obj = data.get("parsed") if isinstance(data, dict) and "parsed" in data else data
    if isinstance(obj, dict) and (obj.get("name") == "张磊" or "张磊" in p.name):
        parsed = obj if obj.get("name") else data
        # some ranking files are not resume parse
        if "target_position" in parsed or "work_experience" in parsed or "skills" in parsed:
            src = p
            break
        parsed = None

if parsed is None:
    # minimal structured record from resume md if present
    md = None
    for p in glob.glob(str(ws / "inbox/**/*张磊*"), recursive=True):
        if "node_modules" not in p:
            md = Path(p)
            break
    print("fallback md", md)
    parsed = {
        "name": "张磊",
        "target_position": "后端开发",
        "expected_salary": "",
        "expected_city": "",
        "available_date": "",
        "education": {"school": "", "major": "", "degree": "", "graduation_year": ""},
        "work_experience": [{"company": "", "position": "后端开发", "start_date": "", "end_date": "", "industry": "互联网"}],
        "total_experience_years": 13,
        "job_count": 1,
        "skills": ["Java", "Spring", "微服务"],
        "self_evaluation": "后端开发",
    }
    if md and md.exists():
        text = md.read_text(encoding="utf-8", errors="ignore")[:4000]
        parsed["self_evaluation"] = text[:500]

print("using src", src)
print("parsed keys", list(parsed.keys())[:20], "name", parsed.get("name"))

parsed_all = {"张磊-tech-后端.md": parsed}
(pool_dir / "parsed-all.json").write_text(json.dumps(parsed_all, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote parsed-all.json")
PY

# embed via ingest script (needs env)
python3 "$PROFILE/workspace-recruitment/skills/ingesting-talent-pool/scripts/ingest_talent_pool.py" embed
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-recruitment/talent-pool/talent-pool.json")
d=json.loads(p.read_text())
names=[c.get("name") for c in d.get("candidates",[])]
print("pool_count", d.get("candidate_count"), "names", names, "model", d.get("embedding_model"), "dim", d.get("dimension"), "bytes", p.stat().st_size)
PY

# --- helper: run agent, wait, dump ---
run_agent() {
  local id="$1" agent="$2" timeout_s="$3" msg="$4"
  local sid="qa-gap-${id}-$(date +%H%M%S)"
  echo "======== $id agent=$agent timeout=${timeout_s}s session=$sid ========"
  echo "MSG: $msg"
  local out="$LOG/${id}.stdout.txt"
  local t0
  t0=$(date +%s)
  set +e
  timeout --signal=INT "$timeout_s" openclaw agent --agent "$agent" --session-id "$sid" -m "$msg" >"$out" 2>&1
  local rc=$?
  set -e
  local t1
  t1=$(date +%s)
  echo "exit=$rc elapsed=$((t1-t0))s stdout_bytes=$(wc -c <"$out")"
  echo "----- stdout tail -----"
  tail -n 40 "$out"
  echo "$sid" >"$LOG/${id}.session"
  echo "$rc" >"$LOG/${id}.exit"
}

# record mtimes before dialogues
python3 - <<'PY'
import os, time
from pathlib import Path
paths = [
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-performance/feedback-360/source_feedback/dirty-zhanglei/aggregated-data.json"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-performance/feedback-360/source_feedback/dirty-zhanglei/report.html"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/canvas/documents/feedback-360-zhanglei/index.html"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/canvas/documents/feedback-360-dirty-zhanglei/index.html"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-er-admin/report-output/hr-monthly-report-2026-05.html"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-er-admin/report-output/hr-monthly-report-2026-05-audit.md"),
]
# training eight files
td = Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-training/training-materials/信息安全意识")
if td.is_dir():
    paths.extend(sorted(td.glob("*.md")))
print("==== mtimes BEFORE ====")
for p in paths:
    if p.exists():
        print(f"{p} mtime={time.strftime('%F %T', time.localtime(p.stat().st_mtime))}")
    else:
        print(f"{p} MISSING")
PY

# Dialogues: sequential to avoid router session mixing.
# Use unique --session-id. Expand execution, then disk-check.

P360='把张磊的 360 反馈聚合并出看板。请交给 performance 实际执行。完成后明确说已生成或失败，并给出 aggregated-data.json 和看板 HTML 或 canvas 的磁盘路径。不要只说已分发。'
TTRAIN='生成一套新人培训物料：主题为信息安全意识。请交给 training 实际执行。请在回复里给出是否已开始/已完成/失败，并列出落盘的真实磁盘路径。不要只说已分发。'
XMAY='出一份 2026-05 的 HR 月报。请交给 er-admin 实际执行，指定月份 2026-05，不要生成本月报告。完成后明确说已生成或失败，并给出 HTML 与 audit 的磁盘路径。不要只说已分发。'
R14='从人才库里找几个和张磊背景相似的候选人。请交给 recruitment 实际执行。完成后明确说匹配到了谁，或明确无法匹配。禁止编造库中不存在的姓名。不要只说已分发。'

# 360 can take a few minutes
run_agent P-D-001 router 420 "$P360"
sleep 3
# monthly report usually faster
run_agent X-D-003 router 300 "$XMAY"
sleep 3
# similar search
run_agent R-D-004 router 300 "$R14"
sleep 3
# training is the long one
run_agent T-D-001 router 720 "$TTRAIN"

python3 - <<'PY'
import os, time, json, re
from pathlib import Path

print("==== mtimes AFTER ====")
roots = [
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-performance"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-training"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-er-admin/report-output"),
  Path("/home/yhwz/openclaw-hr/.openclaw-hr/canvas/documents"),
]
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if "node_modules" in str(p):
            continue
        age = time.time() - p.stat().st_mtime
        if age < 3600 and p.suffix.lower() in {".json", ".html", ".md"}:
            print(f"newish {time.strftime('%F %T', time.localtime(p.stat().st_mtime))} {p}")

pool = Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-recruitment/talent-pool/talent-pool.json")
if pool.exists():
    d=json.loads(pool.read_text())
    print("POOL", d.get("candidate_count"), [c.get("name") for c in d.get("candidates",[])])
else:
    print("POOL missing")

# extract claimed paths from stdout
log = Path("/tmp/qa-gap-20260827")
for name in ["P-D-001", "T-D-001", "X-D-003", "R-D-004"]:
    out = log / f"{name}.stdout.txt"
    if not out.exists():
        print(name, "no stdout")
        continue
    text = out.read_text(encoding="utf-8", errors="ignore")
    print(f"\n==== {name} PATH CHECK ====")
    paths = re.findall(r"(/[^\s`'\"<>]+(?:aggregated-data|report|hr-monthly|training-materials|talent-pool|canvas)[^\s`'\"<>]*)", text)
    paths += re.findall(r"(/tmp/[^\s`'\"<>]+)", text)
    paths += re.findall(r"((?:workspace-|feedback-|training-|report-output|canvas/)[^\s`'\"<>]+)", text)
    uniq = []
    for p in paths:
        if p not in uniq:
            uniq.append(p)
    for p in uniq[:30]:
        exp = p
        if not exp.startswith("/"):
            # try common prefixes
            guesses = [
                Path("/home/yhwz/openclaw-hr/.openclaw-hr") / exp,
                Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-performance") / exp,
                Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-training") / exp,
                Path("/home/yhwz/openclaw-hr/.openclaw-hr/workspace-er-admin") / exp,
            ]
        else:
            guesses = [Path(exp)]
        exists = any(g.exists() for g in guesses)
        print(("EXISTS " if exists else "MISSING"), p)

# invented names for R-D-004
text = (log / "R-D-004.stdout.txt").read_text(encoding="utf-8", errors="ignore") if (log/"R-D-004.stdout.txt").exists() else ""
for n in ["徐昊", "周敏", "赵阳", "陈宇", "钱伟", "李明", "王芳"]:
    if n in text:
        print("R-D-004 invented?", n)
PY

echo "==== $(date -Is) done ===="
echo "logs in $LOG"
