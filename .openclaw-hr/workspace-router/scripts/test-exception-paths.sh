#!/usr/bin/env bash
# R-EXC 契约：yaml 超时/并发、prompt 禁止编造空结果、工具名 sessions_spawn。
# 不改 yaml、不等 1800s。真人对话补测另跑。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$(cd "$ROOT/.." && pwd)"
YAML="$PROFILE/config/openclaw.yaml"
SOUL="$ROOT/SOUL.md"
AGENTS="$ROOT/AGENTS.md"
INTRO="$ROOT/总控小慧INTRO.md"
fail=0
note() { echo "$*"; }
die() { echo "FAIL: $*" >&2; fail=1; }

python3 - <<PY
import sys, yaml
from pathlib import Path
y = yaml.safe_load(Path("$YAML").read_text())
defaults = y["agents"]["defaults"]["subagents"]
assert defaults["maxChildrenPerAgent"] == 8, defaults
assert defaults["runTimeoutSeconds"] == 1800, defaults
for a in y["agents"]["list"]:
    sub = a.get("subagents") or {}
    if "maxChildrenPerAgent" in sub or "runTimeoutSeconds" in sub:
        raise SystemExit(f"illegal list[].subagents keys on {a.get('id')}: {sub}")
print("PASS yaml defaults maxChildren=8 runTimeout=1800; no list[].subagents timeout keys")
PY

for f in "$SOUL" "$AGENTS" "$INTRO"; do
  grep -q 'sessions_spawn' "$f" || die "$f missing sessions_spawn"
done
if grep -n 'agent_to_agent' "$SOUL" "$AGENTS" "$INTRO"; then
  die "SOUL/AGENTS/INTRO still name agent_to_agent as the dispatch tool"
else
  note "PASS prompts use sessions_spawn (topology name stays in hr-agents.yaml)"
fi
grep -q '禁止编造' "$SOUL" || die "SOUL missing 禁止编造"
grep -qE '找不到指定文件|回流为空' "$SOUL" || die "SOUL missing empty-result rule"
grep -qE '找不到指定文件|回流为空' "$AGENTS" || die "AGENTS missing empty-result rule"
note "PASS empty-result / no-invent language"

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "R-EXC contract: all pass"
