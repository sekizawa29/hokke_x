#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 \"相談内容\""
  exit 1
fi

PROMPT="$*"
claude -p "$PROMPT"
