#!/usr/bin/env python3
"""
ホッケ リプライエンジン
ターゲットアカウントのツイートにホッケのペルソナでリプライする
"""

import os
import sys
import json
import json as json_module
import time
import random
import argparse
import requests
from pathlib import Path
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
CONFIG_FILE = SCRIPT_DIR / "config.json"
TARGETS_FILE = SCRIPT_DIR / "target_accounts.json"
LOG_FILE = SCRIPT_DIR / "reply_log.json"
NG_FILE = SCRIPT_DIR / "ng_keywords.json"
PERSONA_FILE = PROJECT_DIR / "PERSONA.md"

load_dotenv(ENV_FILE)

# x_poster を import
sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
from x_poster import XPoster


def load_json(path: Path) -> any:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [] if path.name.endswith('_log.json') or path.name.endswith('_accounts.json') else {}


def save_json(path: Path, data: any) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class ReplyEngine:
    def __init__(self):
        self.config = load_json(CONFIG_FILE)
        self.targets = load_json(TARGETS_FILE)
        self.log = load_json(LOG_FILE)
        self.ng = load_json(NG_FILE)
        self.persona = self._load_persona()

        self.bearer_token = os.getenv('X_BEARER_TOKEN')
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN が未設定")

        self.poster = XPoster()

    def _load_persona(self) -> str:
        if PERSONA_FILE.exists():
            return PERSONA_FILE.read_text(encoding='utf-8')
        return ""

    def _is_enabled(self) -> bool:
        return self.config.get('enabled', False)

    # --- X API 検索 ---

    def search_tweets(self, query: str, max_results: int = 10) -> list:
        """X API v2でツイートを検索"""
        url = "https://api.x.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "query": f"{query} -is:retweet -is:reply lang:ja",
            "max_results": min(max_results, 100),
            "tweet.fields": "author_id,created_at,public_metrics",
            "expansions": "author_id",
            "user.fields": "username,public_metrics"
        }

        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"検索エラー ({query}): {e}")
            return {}

    # --- ターゲット管理 ---

    def add_target(self, username: str, user_id: str, category: str, source: str = "auto") -> None:
        """ターゲットリストにアカウントを追加"""
        existing = {t['username'] for t in self.targets}
        if username in existing:
            return

        self.targets.append({
            "username": username,
            "user_id": user_id,
            "category": category,
            "source": source,
            "added_at": datetime.now().isoformat(),
            "reply_count": 0,
            "last_replied_at": None
        })
        save_json(TARGETS_FILE, self.targets)
        print(f"ターゲット追加: @{username} ({category})")

    def discover_targets(self) -> int:
        """キーワード検索でターゲットを発見"""
        keywords = self.config.get('search_keywords', {})
        per_query = self.config.get('search_tweets_per_query', 10)
        max_queries = self.config.get('search_queries_per_run', 2)

        all_queries = []
        for category, kws in keywords.items():
            for kw in kws:
                all_queries.append((category, kw))

        # ランダムに選んで検索（コスト節約）
        random.shuffle(all_queries)
        queries_to_run = all_queries[:max_queries]

        added = 0
        for category, query in queries_to_run:
            print(f"検索中: '{query}' ({category})")
            result = self.search_tweets(query, per_query)

            users = {}
            for u in result.get('includes', {}).get('users', []):
                users[u['id']] = u

            for tweet in result.get('data', []):
                author_id = tweet['author_id']
                user = users.get(author_id, {})
                username = user.get('username', '')
                if username and username != 'cat_hokke':
                    self.add_target(username, author_id, category)
                    added += 1

        print(f"新規ターゲット: {added}件")
        return added

    # --- NGフィルタ ---

    def is_ng(self, text: str) -> bool:
        """NGキーワードが含まれているか"""
        ng_words = self.ng.get('skip_keywords', [])
        text_lower = text.lower()
        for word in ng_words:
            if word.lower() in text_lower:
                return True
        return False

    # --- リプライ実行 ---

    def _today_reply_count(self) -> int:
        """今日のリプライ数"""
        today = date.today().isoformat()
        return sum(1 for r in self.log if r.get('date') == today and r.get('status') == 'posted')

    def _replied_today(self, username: str) -> bool:
        """今日このアカウントにリプ済みか"""
        today = date.today().isoformat()
        return any(
            r.get('target_user') == username and r.get('date') == today
            for r in self.log
        )

    def get_best_tweet(self, user_id: str) -> Optional[dict]:
        """ユーザーのツイートをエンゲージメントスコアで選定"""
        url = f"https://api.x.com/2/users/{user_id}/tweets"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "max_results": 10,
            "tweet.fields": "created_at,public_metrics",
            "exclude": "retweets,replies"
        }

        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json().get('data', [])
            if not data:
                return None

            # エンゲージメントスコアで並び替え
            for t in data:
                m = t.get('public_metrics', {})
                t['_score'] = m.get('like_count', 0) + m.get('retweet_count', 0) * 2 + m.get('reply_count', 0)

            data.sort(key=lambda t: t['_score'], reverse=True)
            top = data[:3]  # 上位3件からランダム

            chosen = random.choice(top)
            print(f"  ツイート選定: スコア{chosen['_score']} (上位3件: {[t['_score'] for t in top]})")
            return chosen

        except requests.RequestException as e:
            print(f"ツイート取得エラー ({user_id}): {e}")
        return None

    def generate_reply(self, tweet_text: str, category: str) -> Optional[str]:
        """DeepSeek APIでリプライすべきか判断し、リプライを生成（1回のAPI呼び出し）

        Returns:
            str: リプライ本文
            None: スキップ（LLM判断 or 生成失敗）
            戻り値がNoneかつ self._last_skip_reason が設定されている場合はLLMスキップ
        """
        self._last_skip_reason = None

        api_key = os.getenv('DEEPSEEK_API_KEY', '')
        if not api_key:
            print("  DEEPSEEK_API_KEY が未設定")
            return None

        system_prompt = """あなたは「ホッケ」というキャラクターです。以下のペルソナに厳密に従ってリプライを生成してください。

## ペルソナ要約
- チャトラの猫。脱力してる。シュール。たまに鋭い。
- 一人称: 使わないか「俺」。「僕」「私」は使わない。
- 語尾キャラにしない。「〜にゃ」は封印。自然な話し言葉。
- 短文。体言止め多め。句読点少なめ。タメ口。
- 絶対やらないこと: 意識高い発言、説教、自己啓発、過度な共感（「わかるー！」）、媚び、絵文字の乱用
- 優しいけど甘くない。慰めない。でも否定もしない。

## 判断ルール（最重要）
まずこのツイートにリプライすべきか判断してください。
以下に該当する場合はリプライしないでください:
- 訃報・お悔やみ・死亡に関する内容
- 深刻な病気・入院・事故の報告
- 炎上中・論争中の話題
- 政治的・宗教的に繊細な内容
- 明らかな宣伝・スパム・勧誘
- 内容が薄すぎてリプしようがない（「あ」「。」だけ等）
- 文脈がわからない（他ツイートへの返信や内輪ネタ等）
- 怒りや悲しみが強すぎて猫がリプすると不謹慎になりそうな内容

## リプライのルール
- 1〜2文で短く返す（最大80文字程度）
- 「すごい」「いいね」「わかる」だけの薄いリプはしない
- 相手のツイート内容に対してホッケらしい視点でコメントする
- 猫の視点から人間を観察するような一言が理想
- 攻撃的にならない。でも媚びない。

## 出力形式（厳守）
JSON形式で出力。他の文字は一切含めないこと。
リプする場合: {"reply": "リプ本文"}
しない場合: {"skip": "簡潔な理由"}"""

        user_prompt = f"以下のツイートを判断し、適切ならホッケとしてリプライしてください。\n\nツイート: {tweet_text}"

        try:
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.8
                }
            )
            resp.raise_for_status()
            reply_raw = resp.json()['choices'][0]['message']['content'].strip()

            # JSONパース
            try:
                result = json_module.loads(reply_raw)
                if "skip" in result:
                    reason = result['skip']
                    print(f"  LLM判断: スキップ ({reason})")
                    self._last_skip_reason = reason
                    return None
                reply = result.get("reply", "")
            except (json_module.JSONDecodeError, TypeError):
                # JSONパース失敗時はテキストをそのままリプとして扱う（従来互換）
                print(f"  JSONパース失敗、テキストをそのまま使用")
                reply = reply_raw

            if not reply:
                return None

            # 長すぎるリプは切る
            if len(reply) > 140:
                reply = reply[:140]

            # 基本的なセルフチェック
            ng_phrases = ['頑張', '応援', '素敵', 'ありがとう', '！！', '😊', '💪', '✨']
            for phrase in ng_phrases:
                if phrase in reply:
                    print(f"  セルフチェックNG: '{phrase}' を含む")
                    return None

            return reply

        except requests.RequestException as e:
            print(f"  リプ生成エラー: {e}")
            return None

    def execute_replies(self, dry_run: bool = False) -> dict:
        """リプライを実行"""
        if not self._is_enabled():
            print("リプライエンジンは無効です")
            return {"posted": 0, "skipped": 0}

        daily_limit = self.config.get('daily_reply_limit', 10)
        interval = self.config.get('reply_interval_seconds', 180)
        today_count = self._today_reply_count()

        if today_count >= daily_limit:
            print(f"今日の上限に到達済み ({today_count}/{daily_limit})")
            return {"posted": 0, "skipped": 0}

        remaining = daily_limit - today_count
        candidates = [
            t for t in self.targets
            if not self._replied_today(t['username'])
        ]
        random.shuffle(candidates)
        candidates = candidates[:remaining]

        posted = 0
        skipped = 0

        for target in candidates:
            username = target['username']
            user_id = target['user_id']
            print(f"\n処理中: @{username}")

            # エンゲージメント上位ツイート取得
            tweet = self.get_best_tweet(user_id)
            if not tweet:
                print(f"  ツイート取得できず。スキップ")
                skipped += 1
                continue

            tweet_text = tweet.get('text', '')
            tweet_id = tweet.get('id', '')

            # NGチェック
            if self.is_ng(tweet_text):
                print(f"  NGキーワード検出。スキップ")
                skipped += 1
                continue

            # LLM判断 + リプ生成
            reply_text = self.generate_reply(tweet_text, target['category'])
            if not reply_text:
                # LLMスキップの場合はログに記録
                if self._last_skip_reason:
                    print(f"  LLMスキップ。理由: {self._last_skip_reason}")
                    self.log.append({
                        "date": date.today().isoformat(),
                        "timestamp": datetime.now().isoformat(),
                        "target_user": username,
                        "target_tweet_id": tweet_id,
                        "target_tweet_text": tweet_text[:200],
                        "reply_text": None,
                        "category": target['category'],
                        "status": "llm_skip",
                        "skip_reason": self._last_skip_reason
                    })
                    save_json(LOG_FILE, self.log)
                else:
                    print(f"  リプ生成失敗。スキップ")
                skipped += 1
                continue

            # 投稿
            if dry_run:
                print(f"  [DRY RUN] @{username} へ: {reply_text}")
                status = "dry_run"
            else:
                result = self.poster.post_reply(reply_text, tweet_id)
                status = "posted" if result.get('success') else "failed"
                if not result.get('success'):
                    print(f"  投稿失敗: {result.get('error')}")
                    skipped += 1
                    continue

            # ログ記録
            self.log.append({
                "date": date.today().isoformat(),
                "timestamp": datetime.now().isoformat(),
                "target_user": username,
                "target_tweet_id": tweet_id,
                "target_tweet_text": tweet_text[:200],
                "reply_text": reply_text,
                "category": target['category'],
                "status": status
            })
            save_json(LOG_FILE, self.log)

            # ターゲット情報更新
            target['reply_count'] = target.get('reply_count', 0) + 1
            target['last_replied_at'] = datetime.now().isoformat()
            save_json(TARGETS_FILE, self.targets)

            posted += 1
            print(f"  リプ完了: {reply_text[:50]}")

            # 間隔を空ける
            if posted < remaining and not dry_run:
                wait = interval + random.randint(0, 60)
                print(f"  {wait}秒待機...")
                time.sleep(wait)

        print(f"\n結果: {posted}件投稿, {skipped}件スキップ")
        return {"posted": posted, "skipped": skipped}

    # --- ステータス ---

    def status(self) -> dict:
        today = date.today().isoformat()
        today_replies = [r for r in self.log if r.get('date') == today]
        return {
            "enabled": self._is_enabled(),
            "targets_count": len(self.targets),
            "today_replies": len([r for r in today_replies if r['status'] == 'posted']),
            "daily_limit": self.config.get('daily_reply_limit', 10),
            "total_replies": len([r for r in self.log if r['status'] == 'posted']),
        }


def main():
    parser = argparse.ArgumentParser(description='ホッケ リプライエンジン')
    parser.add_argument('command', choices=['discover', 'reply', 'status', 'add-target'],
                        help='実行コマンド')
    parser.add_argument('--dry-run', action='store_true', help='投稿せずにシミュレーション')
    parser.add_argument('--username', type=str, help='手動追加するユーザー名')
    parser.add_argument('--user-id', type=str, help='手動追加するユーザーID')
    parser.add_argument('--category', type=str, default='その他', help='カテゴリ')

    args = parser.parse_args()

    engine = ReplyEngine()

    if args.command == 'discover':
        engine.discover_targets()

    elif args.command == 'reply':
        engine.execute_replies(dry_run=args.dry_run)

    elif args.command == 'status':
        s = engine.status()
        print(f"有効: {s['enabled']}")
        print(f"ターゲット数: {s['targets_count']}")
        print(f"今日のリプ: {s['today_replies']}/{s['daily_limit']}")
        print(f"累計リプ: {s['total_replies']}")

    elif args.command == 'add-target':
        if not args.username or not args.user_id:
            print("--username と --user-id が必要です")
            sys.exit(1)
        engine.add_target(args.username, args.user_id, args.category, source="manual")


if __name__ == "__main__":
    main()
