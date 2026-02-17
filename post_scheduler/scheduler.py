#!/usr/bin/env python3
"""
ホッケ Scheduled Post Executor
予約投稿をチェックし、時刻が来たら実行する
GitHub Actionsから定期実行される
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from x_poster import XPoster

QUEUE_FILE = SCRIPT_DIR / "post_queue.json"


def load_queue() -> List[Dict[str, Any]]:
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_queue(queue: List[Dict[str, Any]]) -> None:
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def get_due_posts(queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """投稿時刻を過ぎたpending投稿を抽出"""
    now = datetime.utcnow() + timedelta(hours=9)  # JST
    due = []
    for post in queue:
        if post.get('status') != 'pending':
            continue
        try:
            scheduled = datetime.strptime(post['scheduled_at'], "%Y-%m-%d %H:%M")
            if scheduled <= now:
                due.append(post)
        except (ValueError, KeyError) as e:
            print(f"日時パースエラー: {post.get('id', '?')} - {e}")
    return due


def execute_post(poster: XPoster, post: Dict[str, Any]) -> bool:
    post_id = post.get('id', '?')
    print(f"\n投稿実行: {post_id} (予約: {post.get('scheduled_at')})")

    try:
        if post.get('thread'):
            thread_data = post['thread']
            for tweet in thread_data:
                if tweet.get('image'):
                    tweet['image'] = str(SCRIPT_DIR.parent / tweet['image'])
            return poster.post_thread(thread_data).get('success', False)

        if post.get('image'):
            image_path = str(SCRIPT_DIR.parent / post['image'])
            return poster.post_with_image(post['text'], image_path).get('success', False)

        return poster.post_text(post['text']).get('success', False)

    except Exception as e:
        print(f"投稿エラー: {e}")
        return False


def main():
    print(f"ホッケ Scheduler - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    queue = load_queue()
    print(f"キュー: {len(queue)}件")

    if not queue:
        print("予約なし")
        return

    due_posts = get_due_posts(queue)
    print(f"投稿対象: {len(due_posts)}件")

    if not due_posts:
        print("現在投稿すべき予約なし")
        return

    try:
        poster = XPoster()
    except ValueError as e:
        print(f"認証エラー: {e}")
        sys.exit(1)

    success = 0
    for post in due_posts:
        ok = execute_post(poster, post)
        for p in queue:
            if p.get('id') == post.get('id'):
                p['status'] = 'completed' if ok else 'failed'
                p['executed_at'] = datetime.now().isoformat()
                break
        if ok:
            success += 1

    # 完了・失敗を除去して保存
    queue = [p for p in queue if p.get('status') == 'pending']
    save_queue(queue)

    print(f"\n結果: {success}/{len(due_posts)}件成功, 残りキュー: {len(queue)}件")


if __name__ == "__main__":
    main()
