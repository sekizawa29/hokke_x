#!/usr/bin/env python3
"""
ホッケ X Poster
Tweepyを使用してX(Twitter)に投稿するスクリプト
"""

import os
import sys
import json
import argparse
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv
from x_api_client import XApiClient

try:
    import tweepy
except ImportError:
    print("tweepyがインストールされていません")
    print("pip install tweepy python-dotenv")
    sys.exit(1)

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from notifications.discord_notifier import DiscordNotifier

QUEUE_FILE = SCRIPT_DIR / "post_queue.json"
IMAGES_DIR = SCRIPT_DIR.parent / "scheduled_images"
HOOK_PERF_FILE = SCRIPT_DIR.parent / "hook_performance.json"


class XPoster:
    """X (Twitter) への投稿"""

    def __init__(self):
        self.api_client = XApiClient(require_user_auth=True)
        print("X API認証成功")

    def verify_credentials(self) -> bool:
        try:
            user = self.api_client.verify_credentials()
            print(f"認証済み: @{user.screen_name}")
            return True
        except tweepy.TweepyException as e:
            print(f"認証エラー: {e}")
            return False

    def _record_to_hook_performance(self, tweet_id: str, text: str, hook_category: str) -> None:
        if HOOK_PERF_FILE.exists():
            with open(HOOK_PERF_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"version": "1.0", "posts": []}

        data["posts"].append({
            "tweet_id": str(tweet_id),
            "text": text,
            "hookCategory": hook_category,
            "postedAt": datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S'),
            "engagementFetchedAt": None,
            "likes": None, "retweets": None, "replies": None, "quotes": None,
            "impressions": None, "url_link_clicks": None,
            "user_profile_clicks": None, "bookmarks": None,
            "diagnosis": None
        })

        with open(HOOK_PERF_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[HookPerf] 記録完了: {hook_category} / tweet_id={tweet_id}")

    def _upload_media(self, image_path: str) -> int:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"画像が見つからない: {image_path}")
        media = self.api_client.media_upload(filename=str(path))
        return media.media_id

    def _notify_post_success(self, *, text: str, hook_category: str, url: str) -> None:
        """Best-effort Discord notify for normal posts."""
        try:
            notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_POST")
        except ValueError:
            # Not configured: skip silently to avoid breaking posting flow.
            return

        short = text.strip().replace("\n", " ")
        if len(short) > 120:
            short = short[:119] + "…"

        message = (
            "🐾 **ホッケ 投稿通知**\n"
            f"- category: `{hook_category}`\n"
            f"- text: {short}\n"
            f"- url: {url}"
        )
        res = notifier.send(message, username="Hokke Post Bot")
        if not res.ok:
            print(f"[notify] Discord送信失敗: {res.error}")

    def post_text(self, text: str, hook_category: str = "未分類") -> dict:
        try:
            response = self.api_client.create_tweet(
                text=text,
                context="x_poster.post_text",
                metadata={"hook_category": hook_category},
            )
            tweet_id = response.data['id']
            url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"投稿成功: {url}")
            self._record_to_hook_performance(tweet_id, text, hook_category)
            self._notify_post_success(text=text, hook_category=hook_category, url=url)
            return {'success': True, 'tweet_id': tweet_id, 'url': url}
        except tweepy.TweepyException as e:
            print(f"投稿エラー: {e}")
            return {'success': False, 'error': str(e)}

    def post_with_image(self, text: str, image_path: str, hook_category: str = "未分類") -> dict:
        try:
            media_id = self._upload_media(image_path)
            response = self.api_client.create_tweet(
                text=text,
                media_ids=[media_id],
                context="x_poster.post_with_image",
                metadata={"hook_category": hook_category},
            )
            tweet_id = response.data['id']
            url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"画像付き投稿成功: {url}")
            self._record_to_hook_performance(tweet_id, text, hook_category)
            self._notify_post_success(text=text, hook_category=hook_category, url=url)
            return {'success': True, 'tweet_id': tweet_id, 'url': url}
        except (FileNotFoundError, tweepy.TweepyException) as e:
            print(f"投稿エラー: {e}")
            return {'success': False, 'error': str(e)}

    def post_reply(self, text: str, reply_to_tweet_id: str, image_path: Optional[str] = None) -> dict:
        try:
            media_ids = None
            if image_path:
                media_ids = [self._upload_media(image_path)]
            response = self.api_client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to_tweet_id,
                media_ids=media_ids,
                context="x_poster.post_reply",
            )
            tweet_id = response.data['id']
            url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"リプライ投稿成功: {url}")
            return {'success': True, 'tweet_id': tweet_id, 'url': url}
        except tweepy.TweepyException as e:
            print(f"リプライエラー: {e}")
            return {'success': False, 'error': str(e)}

    def post_thread(self, tweets: List[Dict]) -> dict:
        if not tweets:
            return {'success': False, 'error': '投稿リストが空'}

        results = []
        prev_tweet_id = None

        for i, tweet in enumerate(tweets):
            text = tweet.get('text', '')
            image_path = tweet.get('image')

            if i == 0:
                result = self.post_with_image(text, image_path) if image_path else self.post_text(text)
            else:
                result = self.post_reply(text, prev_tweet_id, image_path)

            if not result['success']:
                return {'success': False, 'error': result.get('error'), 'completed': results}

            results.append(result)
            prev_tweet_id = result['tweet_id']

        return {
            'success': True,
            'tweets': results,
            'main_url': results[0]['url'],
            'count': len(results)
        }

    def add_to_queue(
        self, text: str, scheduled_at: str,
        image_path: Optional[str] = None,
        thread_data: Optional[List[Dict]] = None
    ) -> dict:
        IMAGES_DIR.mkdir(exist_ok=True)

        if QUEUE_FILE.exists():
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        else:
            queue = []

        post_id = str(uuid.uuid4())[:8]

        saved_image = None
        if image_path:
            src = Path(image_path)
            if src.exists():
                dest = IMAGES_DIR / f"{post_id}{src.suffix}"
                shutil.copy2(src, dest)
                saved_image = f"scheduled_images/{dest.name}"

        if thread_data:
            for i, tweet in enumerate(thread_data):
                if tweet.get('image'):
                    src = Path(tweet['image'])
                    if src.exists():
                        dest = IMAGES_DIR / f"{post_id}_t{i}{src.suffix}"
                        shutil.copy2(src, dest)
                        tweet['image'] = f"scheduled_images/{dest.name}"

        post_data = {
            "id": post_id,
            "text": text,
            "scheduled_at": scheduled_at,
            "image": saved_image,
            "thread": thread_data,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }

        queue.append(post_data)
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)

        print(f"予約追加: {post_id} ({scheduled_at})")
        return {'success': True, 'post_id': post_id, 'scheduled_at': scheduled_at}


def main():
    parser = argparse.ArgumentParser(description='ホッケ X Poster')
    parser.add_argument('--text', '-t', type=str, help='投稿テキスト')
    parser.add_argument('--image', '-i', type=str, help='画像パス')
    parser.add_argument('--verify', '-v', action='store_true', help='認証確認')
    parser.add_argument('--reply-to', '-r', type=str, help='リプライ先ツイートID')
    parser.add_argument('--thread', type=str, help='スレッド用JSONファイル')
    parser.add_argument('--schedule', '-s', type=str, help='予約日時 (YYYY-MM-DD HH:MM)')
    parser.add_argument('--hook-category', '-c', type=str, default='未分類',
        help='投稿カテゴリ（脱力系/猫写真/鋭い一言/日常観察/時事ネタ/たまに有益）')

    args = parser.parse_args()

    if not args.text and not args.verify and not args.thread:
        parser.print_help()
        sys.exit(1)

    poster = XPoster()

    if args.verify:
        poster.verify_credentials()
        return

    if args.schedule:
        thread_data = None
        if args.thread:
            with open(args.thread, 'r', encoding='utf-8') as f:
                thread_data = json.load(f)
        poster.add_to_queue(
            text=args.text or "", scheduled_at=args.schedule,
            image_path=args.image, thread_data=thread_data
        )
        return

    if args.thread:
        with open(args.thread, 'r', encoding='utf-8') as f:
            tweets = json.load(f)
        poster.post_thread(tweets)
    elif args.reply_to:
        poster.post_reply(args.text, args.reply_to, args.image)
    elif args.image:
        poster.post_with_image(args.text, args.image, args.hook_category)
    else:
        poster.post_text(args.text, args.hook_category)


if __name__ == "__main__":
    main()
