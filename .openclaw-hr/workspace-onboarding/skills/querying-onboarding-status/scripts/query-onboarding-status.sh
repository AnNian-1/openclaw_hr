#!/usr/bin/env bash
# query-onboarding-status.sh —— running-onboarding-workflow Skill 的查询启动器
#
# 用法：
#   query-onboarding-status.sh <候选人全名> [pinyin]
#
# 例：
#   query-onboarding-status.sh 员工1 yuangong1   # 工整路径
#   query-onboarding-status.sh 员工1            # 用内嵌 pinyin 字典查
#
# 输出：stdout = 结构化 JSON；stderr = 人话摘要
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PREPEND_NODE="$(cd "$SCRIPT_DIR/../../../.." && pwd)/scripts/prepend-node22.sh"
# shellcheck disable=SC1090
[ -f "$_PREPEND_NODE" ] && . "$_PREPEND_NODE"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# 优先用外部传入的 $WORKSPACE（如 run-onboarding.sh / 测试 export），
# 否则按脚本位置倒推：.../workspace-onboarding/skills/querying-onboarding-status/scripts
#   → .../workspace-onboarding
if [ -z "${WORKSPACE:-}" ]; then
  WORKSPACE="$(cd "$SKILL_DIR/../.." && pwd)"
fi
export WORKSPACE

exec python3 "$SCRIPT_DIR/query-onboarding-status.py" "$@"
