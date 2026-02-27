#!/usr/bin/env python3
"""候補が10件未満なら generate_reply_dashboard.py を実行する"""
import json, subprocess, sys
from pathlib import Path

THRESHOLD = 10
PROJECT_DIR = Path(__file__).parent.parent
CANDIDATES = PROJECT_DIR / "dashboard" / "reply_candidates.json"

# 現在の候補数を確認
count = 0
if CANDIDATES.exists():
    try:
        data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        count = len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError):
        pass

if count >= THRESHOLD:
    print(f"候補{count}件 >= {THRESHOLD}件。スキップ")
    sys.exit(0)

print(f"候補{count}件 < {THRESHOLD}件。補充実行")
result = subprocess.run(
    [sys.executable, str(PROJECT_DIR / "reply_system" / "generate_reply_dashboard.py"), "--queries", "2"],
    cwd=str(PROJECT_DIR),
)
sys.exit(result.returncode)
