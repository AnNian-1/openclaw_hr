#!/bin/bash
# HCM 系统一键启动脚本
# 用法: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Use miniconda python if available (has sqlalchemy/fastapi/uvicorn installed)
if [ -x /home/yhwz/miniconda3/bin/python3 ]; then
  PYTHON=/home/yhwz/miniconda3/bin/python3
  export PATH="/home/yhwz/miniconda3/bin:$PATH"
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
echo "   后端 API: http://localhost:8000/docs"
echo "   前端看板: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待子进程
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
