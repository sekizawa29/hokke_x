#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ALLOW_FILE="post_scheduler/x_api_client.py"

PATTERN='api\.x\.com|tweepy\.Client\(|tweepy\.API\(|OAuth1UserHandler\('

echo "Checking for direct X API calls outside ${ALLOW_FILE}..."
if rg -n --glob '*.py' -g "!${ALLOW_FILE}" -e "${PATTERN}" post_scheduler reply_system analytics; then
  echo ""
  echo "[ERROR] Direct X API call detected outside ${ALLOW_FILE}."
  echo "Route X API calls through shared client and retry."
  exit 1
fi

echo "OK: no direct X API calls found."
