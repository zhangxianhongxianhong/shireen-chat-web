#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "未找到虚拟环境，请先执行："
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! .venv/bin/python -c "import app" >/dev/null 2>&1; then
  echo "Python 依赖与当前架构不匹配，正在重装（$(uname -m)）..."
  .venv/bin/pip install -r requirements.txt --force-reinstall
fi

if lsof -ti :8000 >/dev/null 2>&1; then
  echo "端口 8000 已被占用，正在释放..."
  lsof -ti :8000 | xargs kill -9
  sleep 1
fi

echo "启动后端 http://127.0.0.1:8000"
.venv/bin/uvicorn app:app --reload --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  echo "后端启动失败，请检查上方报错"
  exit 1
fi

echo "启动前端 http://localhost:5173"
cd frontend
npm run dev
