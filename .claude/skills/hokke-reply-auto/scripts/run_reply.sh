#!/usr/bin/env bash
# hokke-reply-auto: 自律リプライ実行スクリプト
# 決定的に status → discover → reply を実行し、JSON結果を出力する
set -euo pipefail

X_CLI="python3 /home/sekiz/pjt/hokke_x/x_cli.py"
LOG_FILE="/home/sekiz/pjt/hokke_x/reply_system/reply_log.json"

# --- 1. ステータス確認 ---
echo "=== STATUS ==="
STATUS_OUTPUT=$($X_CLI reply status 2>&1) || true
echo "$STATUS_OUTPUT"

# 今日のリプ数を抽出
TODAY_REPLIES=$(echo "$STATUS_OUTPUT" | grep -oP '今日のリプ: \K[0-9]+' || echo "0")
DAILY_LIMIT=$(echo "$STATUS_OUTPUT" | grep -oP '今日のリプ: [0-9]+/\K[0-9]+' || echo "10")

if [ "$TODAY_REPLIES" -ge "$DAILY_LIMIT" ]; then
    echo ""
    echo "=== RESULT ==="
    echo "{\"action\":\"skipped\",\"reason\":\"daily_limit_reached\",\"today_replies\":$TODAY_REPLIES,\"daily_limit\":$DAILY_LIMIT,\"discovered\":0,\"posted\":0,\"skipped\":0}"
    exit 0
fi

# --- 2. ターゲット発見 ---
echo ""
echo "=== DISCOVER ==="
DISCOVER_OUTPUT=$($X_CLI reply discover 2>&1) || true
echo "$DISCOVER_OUTPUT"

# 発見数を抽出（"新規ターゲット: X件" のパターン）
DISCOVERED=$(echo "$DISCOVER_OUTPUT" | grep -oP '新規ターゲット: \K[0-9]+' || echo "0")

# --- 3. リプライ実行（--dry-run なし） ---
echo ""
echo "=== REPLY ==="
REPLY_OUTPUT=$($X_CLI reply run 2>&1) || true
echo "$REPLY_OUTPUT"

# 結果を抽出
POSTED=$(echo "$REPLY_OUTPUT" | grep -oP '結果: \K[0-9]+' || echo "0")
SKIPPED=$(echo "$REPLY_OUTPUT" | grep -oP '[0-9]+件スキップ' | grep -oP '[0-9]+' || echo "0")

# --- 4. 最近のリプログから投稿内容を取得 ---
echo ""
echo "=== RECENT_REPLIES ==="
# 今日のpostedエントリを抽出
python3 -c "
import json
from datetime import date
with open('$LOG_FILE') as f:
    logs = json.load(f)
today = date.today().isoformat()
recent = [l for l in logs if l.get('date') == today and l.get('status') == 'posted']
for r in recent[-5:]:
    print(f\"@{r['target_user']} → {r['reply_text']}\")
" 2>/dev/null || true

# --- 5. JSON結果出力 ---
echo ""
echo "=== RESULT ==="
echo "{\"action\":\"executed\",\"today_replies\":$TODAY_REPLIES,\"daily_limit\":$DAILY_LIMIT,\"discovered\":$DISCOVERED,\"posted\":$POSTED,\"skipped\":$SKIPPED}"
