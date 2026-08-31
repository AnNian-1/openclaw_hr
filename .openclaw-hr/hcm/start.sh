#!/bin/bash
# HCM 系统一键启动脚本
# 用法: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# conda 环境 openclaw-hr 才有 sqlalchemy/fastapi/uvicorn，base 没有
CONDA_BIN=/usr/local/miniconda3/envs/openclaw-hr/bin
if [ -x "$CONDA_BIN/python3" ]; then
  PYTHON="$CONDA_BIN/python3"
  export PATH="$CONDA_BIN:$PATH"
fi
# 前端 Vite 需要 Node 22
if [ -d /opt/node/node-22/bin ]; then
  export PATH="/opt/node/node-22/bin:$PATH"
fi

echo "🚀 启动 HCM 入职管理系统..."

# 1. 启动后端
echo "📦 启动 FastAPI 后端 (port 8000)..."
cd "$SCRIPT_DIR/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2

# 2. 启动前端
echo "🎨 启动 Vue 3 前端 (port 5173)..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ HCM 系统已启动"
echo "   后端 API: http://0.0.0.0:8000/docs （本机可用 127.0.0.1）"
echo "   前端看板: http://0.0.0.0:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待子进程
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
