#!/usr/bin/env python3
"""
Claude生成リプライの投稿 + ログ記録
Usage:
  python3 post_claude_reply.py \
    --tweet-id <id> \
    --username <username> \
    --tweet-text <text> \
    --reply-text <reply> \
    --category <category>
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, date

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
from x_poster import XPoster

LOG_FILE = SCRIPT_DIR / "reply_log.json"
TARGETS_FILE = SCRIPT_DIR / "target_accounts.json"


def load_json(path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tweet-id', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--tweet-text', required=True)
    parser.add_argument('--reply-text', required=True)
    parser.add_argument('--category', default='不明')
    args = parser.parse_args()

    poster = XPoster()
    result = poster.post_reply(args.reply_text, args.tweet_id)

    if not result.get('success'):
        print(f"投稿失敗: {result.get('error')}", file=sys.stderr)
        sys.exit(1)

    print(f"投稿成功: {result['url']}")

    # reply_log.json に記録
    log = load_json(LOG_FILE)
    log.append({
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "target_user": args.username,
        "target_tweet_id": args.tweet_id,
        "target_tweet_text": args.tweet_text[:200],
        "reply_text": args.reply_text,
        "category": args.category,
        "status": "posted",
        "generated_by": "claude"
    })
    save_json(LOG_FILE, log)

    # target_accounts.json の reply_count / last_replied_at を更新
    targets = load_json(TARGETS_FILE)
    for t in targets:
        if t['username'] == args.username:
            t['reply_count'] = t.get('reply_count', 0) + 1
            t['last_replied_at'] = datetime.now().isoformat()
            break
    save_json(TARGETS_FILE, targets)

    print(f"ログ記録完了: @{args.username}")


if __name__ == "__main__":
    main()
