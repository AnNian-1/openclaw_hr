#!/usr/bin/env bash
# 招聘 exec 唯一入口：禁止把路径打到其它域 workspace（D-011）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$(cd "$ROOT/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/recruitment-run.sh <command> [args...]" >&2
  echo "禁止 python/node -c；禁止读写 workspace-onboarding 等其它域。" >&2
  exit 2
fi

deny() {
  echo "recruitment-run: 拒绝越权 exec：$*" >&2
  echo "入职 stub-state / 其它域请转交对应 agent。本域只用 workspace-recruitment 内 Skill。" >&2
  exit 2
}

for a in "$@"; do
  case "$a" in
    -c|-e|-p|--eval|--pyeval|-E|-r)
      deny "内联求值参数 $a"
      ;;
  esac
done

SIBLINGS=(
  "$PROFILE/workspace-onboarding"
  "$PROFILE/workspace-er-admin"
  "$PROFILE/workspace-training"
  "$PROFILE/workspace-performance"
  "$PROFILE/workspace-router"
)

under() {
  local abs="$1" root="$2"
  [[ "$abs" == "$root" || "$abs" == "$root"/* ]]
}

check_abs() {
  local abs="$1"
  local s
  for s in "${SIBLINGS[@]}"; do
    if under "$abs" "$s"; then
      deny "$abs"
    fi
  done
}

pathish() {
  local a="$1"
  [[ "$a" == */* || "$a" == ~* || "$a" == ./* || "$a" == ../* ]]
}

resolve() {
  local a="$1"
  if [[ "$a" == /* ]]; then
    realpath -m -- "$a"
  else
    realpath -m -- "$PWD/$a"
    realpath -m -- "$ROOT/$a"
  fi
}

while IFS= read -r abs; do
  [[ -n "$abs" ]] || continue
  check_abs "$abs"
done < <(
  for a in "$@"; do
    pathish "$a" || continue
    resolve "$a"
  done
)

cd "$ROOT"

# IMAP / 模型 Key 由 Gateway 启动时注入；exec 闸禁止 source && 和 $(date)。
# 脚本内 source，Agent 只需：bash scripts/recruitment-run.sh python3 skills/...
if [[ -f "$PROFILE/env.sh" ]]; then
  set +u
  # shellcheck disable=SC1091
  source "$PROFILE/env.sh"
  set -u
fi

# env.sh 的 python3 是 conda base。通用 Skill 走 openclaw-hr；转写脚本会自行切 funasr_me。
OC_PY_BIN="$HOME/miniconda3/envs/openclaw-hr/bin"
if [[ -x "$OC_PY_BIN/python3" ]]; then
  export PATH="$OC_PY_BIN:$PATH"
fi
export FUNASR_VENV="${FUNASR_VENV:-$HOME/miniconda3/envs/funasr_me}"
export MODELSCOPE_CACHE="${MODELSCOPE_CACHE:-$ROOT/models}"

export LLM_MODEL="${LLM_MODEL:-mimo-v2.5-pro}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://token-plan-cn.xiaomimimo.com/v1}"

exec "$@"
