#!/bin/sh
# ホッケ運用ダッシュボード起動スクリプト
# Usage: ./scripts/start.sh
# 環境変数 PORT でポート番号を変更可能（デフォルト: 8099）

set -e

PORT="${PORT:-8099}"
HOST="127.0.0.1"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$APP_DIR"

echo "ホッケ運用ダッシュボード"
echo "  URL: http://${HOST}:${PORT}/"
echo "  停止: Ctrl+C"
echo ""

exec uv run uvicorn app:app --host "$HOST" --port "$PORT"
