#!/usr/bin/env bash
# REEV DB Monitor — launcher
# Usage: ./start.sh [port]
set -euo pipefail

PORT="${1:-8300}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧬 REEV DB Monitor — http://localhost:${PORT}"
cd "$DIR"
exec uvicorn app:app --host 0.0.0.0 --port "$PORT" --reload
