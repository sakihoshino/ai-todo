#!/bin/bash
# 在同一地址提供网页及 API；Ctrl+C 会关闭整个服务。
set -euo pipefail
cd "$(dirname "$0")"
root_dir="$PWD"
port="${PORT:-8000}"

if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  echo "需要 Python 3.11 或更高版本。请安装 Python 后重新运行。" >&2
  exit 1
fi
if ! command -v node >/dev/null || ! command -v npm >/dev/null || ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || major > 22 || (major === 22 && minor >= 12) ? 0 : 1)'; then
  echo "需要 Node.js 和 npm。请安装 Node.js 20.19+（20.x）或 22.12 及以上版本。" >&2
  exit 1
fi
if [ ! -f backend/.env ]; then
  (umask 077; cp -n backend/.env.example backend/.env)
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if [ ! -e .venv/.runtime-installed ] || [ backend/requirements.txt -nt .venv/.runtime-installed ]; then
  .venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.txt
  touch .venv/.runtime-installed
fi
cd frontend
if [ ! -d node_modules ] || [ ! -e node_modules/.app-installed ] || [ package-lock.json -nt node_modules/.app-installed ]; then
  npm ci --no-audit --no-fund
  touch node_modules/.app-installed
fi
if [ ! -f dist/index.html ] || [ -n "$(find src public index.html vite.config.* package*.json -newer dist/index.html -print -quit)" ]; then
  npm run build
fi
cd "$root_dir/backend"
echo "AI-Todo 访问地址 http://127.0.0.1:${port}（按 Ctrl+C 停止）"
exec "$root_dir/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$port"
