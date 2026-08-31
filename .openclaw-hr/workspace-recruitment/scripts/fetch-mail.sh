#!/usr/bin/env bash
# 招聘 IMAP 收信入口：给 OpenClaw exec 用。
# 只允许这一条：bash scripts/fetch-mail.sh
# 不要 source / cd / && / $(date) / 2>&1。凭证由 recruitment-run.sh 注入。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/recruitment-run.sh" python3 \
  skills/fetching-resumes-by-mail/scripts/fetch_resumes.py \
  --inbox-dir inbox \
  --llm-timeout 20 \
  --backend live \
  "$@"
