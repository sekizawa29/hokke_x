#!/usr/bin/env python3
"""
Claude直接リプライ用: ツイート候補をJSON出力する
reply_engineのインフラ（API検索・NGチェック等）を再利用
"""

import sys
import json
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from reply_engine import ReplyEngine


def main():
    engine = ReplyEngine()

    daily_limit = engine.config.get('daily_reply_limit', 10)
    today_count = engine._today_reply_count()
    remaining = daily_limit - today_count

    if remaining <= 0:
        print(json.dumps({
            "error": "daily_limit_reached",
            "today_count": today_count,
            "daily_limit": daily_limit,
            "candidates": []
        }, ensure_ascii=False))
        return

    targets = [t for t in engine.targets if not engine._replied_today(t['username'])]
    random.shuffle(targets)

    candidates = []
    for target in targets:
        if len(candidates) >= remaining:
            break

        tweet = engine.get_best_tweet(target['user_id'])
        if not tweet:
            continue

        tweet_text = tweet.get('text', '')
        if engine.is_ng(tweet_text):
            continue

        candidates.append({
            "username": target['username'],
            "user_id": target['user_id'],
            "category": target['category'],
            "tweet_id": tweet['id'],
            "tweet_text": tweet_text
        })

    print(json.dumps({
        "today_count": today_count,
        "daily_limit": daily_limit,
        "remaining": remaining,
        "candidates": candidates
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
