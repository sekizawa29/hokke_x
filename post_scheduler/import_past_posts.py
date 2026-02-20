#!/usr/bin/env python3
"""
過去の投稿を hook_performance.json にインポートするスクリプト
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
HOOK_PERF_FILE = SCRIPT_DIR.parent / "hook_performance.json"

# 過去の投稿データ（memory/2026-02-18.md から抽出）
PAST_POSTS = [
    {
        "tweet_id": "2023904669148549576",
        "text": "朝から何か始めようとしてる人間を見る。俺は今日も寝るだけ",
        "hookCategory": "脱力系",
        "postedAt": "2026-02-18T08:38:00+09:00",
    },
    {
        "tweet_id": "2023970882369319303",
        "text": "午後。眠い。猫はいつも眠いけど",
        "hookCategory": "日常観察",
        "postedAt": "2026-02-18T13:00:00+09:00",
    },
    {
        "tweet_id": "2024046386606645549",
        "text": "夕方六時。そろそろ飼い主が帰ってくる時間。猫は今日も寝るだけ",
        "hookCategory": "日常観察",
        "postedAt": "2026-02-18T18:00:00+09:00",
    },
]

def load_perf_data() -> dict:
    if not HOOK_PERF_FILE.exists():
        return {"version": "1.0", "posts": []}
    with open(HOOK_PERF_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_perf_data(data: dict) -> None:
    with open(HOOK_PERF_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    data = load_perf_data()

    existing_ids = set(p.get("tweet_id") for p in data["posts"])
    new_count = 0

    for post in PAST_POSTS:
        if post["tweet_id"] in existing_ids:
            print(f"[SKIP] 既存: {post['tweet_id']}")
            continue

        # デフォルト値を設定
        entry = {
            "tweet_id": post["tweet_id"],
            "text": post["text"],
            "hookCategory": post["hookCategory"],
            "postedAt": post["postedAt"],
            "engagementFetchedAt": None,
            "likes": None, "retweets": None, "replies": None, "quotes": None,
            "impressions": None, "url_link_clicks": None,
            "user_profile_clicks": None, "bookmarks": None,
            "diagnosis": None
        }

        data["posts"].append(entry)
        print(f"[ADD] {post['hookCategory']} | {post['text'][:30]}...")
        new_count += 1

    if new_count == 0:
        print("追加する投稿はありませんでした")
        return

    save_perf_data(data)
    print(f"\n[完了] {new_count}件をインポートしました → {HOOK_PERF_FILE}")

if __name__ == "__main__":
    main()
