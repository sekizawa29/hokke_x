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

try:
    import tweepy
except ImportError:
    print("tweepyがインストールされていません")
    print("pip install tweepy python-dotenv")
    sys.exit(1)

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
QUEUE_FILE = SCRIPT_DIR / "post_queue.json"
IMAGES_DIR = SCRIPT_DIR.parent / "scheduled_images"


class XPoster:
    """X (Twitter) への投稿"""

    def __init__(self):
        api_key = os.getenv('X_API_KEY')
        api_secret = os.getenv('X_API_SECRET')
        access_token = os.getenv('X_ACCESS_TOKEN')
        access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')

        if not all([api_key, api_secret, access_token, access_token_secret]):
            missing = []
            if not api_key: missing.append('X_API_KEY')
            if not api_secret: missing.append('X_API_SECRET')
            if not access_token: missing.append('X_ACCESS_TOKEN')
            if not access_token_secret: missing.append('X_ACCESS_TOKEN_SECRET')
            raise ValueError(f"環境変数が未設定: {', '.join(missing)}")

        self.auth = tweepy.OAuth1UserHandler(
            api_key, api_secret, access_token, access_token_secret
        )
        self.api_v1 = tweepy.API(self.auth)
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        print("X API認証成功")

    def verify_credentials(self) -> bool:
        try:
            user = self.api_v1.verify_credentials()
            print(f"認証済み: @{user.screen_name}")
            return True
        except tweepy.TweepyException as e:
            print(f"認証エラー: {e}")
            return False

    def _upload_media(self, image_path: str) -> int:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"画像が見つからない: {image_path}")
        media = self.api_v1.media_upload(filename=str(path))
        return media.media_id

    def post_text(self, text: str) -> dict:
        try:
            response = self.client.create_tweet(text=text)
            tweet_id = response.data['id']
            url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"投稿成功: {url}")
            return {'success': True, 'tweet_id': tweet_id, 'url': url}
        except tweepy.TweepyException as e:
            print(f"投稿エラー: {e}")
            return {'success': False, 'error': str(e)}

    def post_with_image(self, text: str, image_path: str) -> dict:
        try:
            media_id = self._upload_media(image_path)
            response = self.client.create_tweet(text=text, media_ids=[media_id])
            tweet_id = response.data['id']
            url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"画像付き投稿成功: {url}")
            return {'success': True, 'tweet_id': tweet_id, 'url': url}
        except (FileNotFoundError, tweepy.TweepyException) as e:
            print(f"投稿エラー: {e}")
            return {'success': False, 'error': str(e)}

    def post_reply(self, text: str, reply_to_tweet_id: str, image_path: Optional[str] = None) -> dict:
        try:
            media_ids = None
            if image_path:
                media_ids = [self._upload_media(image_path)]
            response = self.client.create_tweet(
                text=text, in_reply_to_tweet_id=reply_to_tweet_id, media_ids=media_ids
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
        poster.post_with_image(args.text, args.image)
    else:
        poster.post_text(args.text)


if __name__ == "__main__":
    main()
