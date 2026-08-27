#!/usr/bin/env bash
# ============================================================
# OpenClaw AI HR 数字员工「小慧」· profile 一次性配置脚本
# ------------------------------------------------------------
# 作用：把 profile 里硬编码的本机绝对路径，改写成你这台机器上的实际路径。
# 用法：把本 profile 放好之后，在 profile 根目录执行一次：
#         bash setup.sh
# 幂等：可重复运行，不会重复改写。
# ============================================================
set -euo pipefail

# 本脚本所在目录 = profile 根目录（你把 profile 放在哪，这里就是哪）
PROFILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 打包 / 旧环境路径 → 本机 PROFILE_DIR
rewrite_old_path() {
  local old_path="$1"
  local label="$2"
  if [ "$PROFILE_DIR" = "$old_path" ]; then
    echo "  [$label] 当前路径与 $old_path 相同，跳过。"
    return 0
  fi
  local count=0
  # 只扫描文本文件（-I 跳过二进制，避免损坏 sqlite 等）
  while IFS= read -r f; do
    tmp="$(mktemp)"
    sed "s|$old_path|$PROFILE_DIR|g" "$f" > "$tmp" && cat "$tmp" > "$f" && rm -f "$tmp"
    count=$((count + 1))
    echo "  已改写 ($label): ${f#"$PROFILE_DIR"/}"
  done < <(grep -rlI --exclude='setup.sh' "$old_path" "$PROFILE_DIR" 2>/dev/null || true)
  echo "  [$label] 共处理 $count 个文件。"
}

echo "============================================================"
echo "  OpenClaw AI HR profile 配置"
echo "  Profile 目录 : $PROFILE_DIR"
echo "============================================================"

rewrite_old_path "/Users/hsail/.openclaw-hr" "课程打包机"
rewrite_old_path "/root/.openclaw-hr" "root 残留"

# 运行期目录（打包时已清空/排除，OpenClaw 会按需重建，这里先建好空目录）
mkdir -p "$PROFILE_DIR/memory" "$PROFILE_DIR/logs" "$PROFILE_DIR/sessions" "$PROFILE_DIR/agents"

echo ""
echo "✅ 路径配置完成。接下来按《学员使用指南》(README.md) 操作："
echo "   1. 编辑 env.sh，填入你自己的 API Key 与 Gateway Token"
echo "   2. source env.sh"
echo "   3. 启动 Gateway，开始与「小慧」对话"
echo "============================================================"
