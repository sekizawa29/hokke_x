#!/bin/bash
# Cron用リプライ実行スクリプト
export DISPLAY=:0
export PATH="/mnt/c/Users/sekiz/AppData/Local/Programs/Python/Python310:/usr/local/bin:/usr/bin:/bin:$PATH"
cd /home/sekiz/pjt/hokke_x

PYTHON_WIN="/mnt/c/Users/sekiz/AppData/Local/Programs/Python/Python310/python.exe"
LOG="/home/sekiz/pjt/hokke_x/reply_system/browser_automation/cron_reply.log"
echo "=== $(date) ===" >> "$LOG"

# モニターを起こす（Shiftキー空打ち → 5秒待機）
$PYTHON_WIN -c "import pyautogui; pyautogui.press('shift')" >> "$LOG" 2>&1
sleep 5

python3 reply_system/browser_automation/orchestrator.py --no-confirm --limit 5 >> "$LOG" 2>&1
echo "exit_code=$?" >> "$LOG"
