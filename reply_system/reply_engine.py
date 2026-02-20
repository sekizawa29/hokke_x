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
import subprocess
import re
import shutil
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv

# 即時フラッシュ設定（長時間実行時の進捗表示のため）
sys.stdout.reconfigure(line_buffering=True)

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
from x_api_client import XApiClient


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
        self.x_api = XApiClient(require_bearer=True)

    def _load_persona(self) -> str:
        if PERSONA_FILE.exists():
            return PERSONA_FILE.read_text(encoding='utf-8')
        return ""

    def _is_enabled(self) -> bool:
        return self.config.get('enabled', False)

    # --- X API 検索 ---

    def search_tweets(self, query: str, max_results: int = 10) -> list:
        """X API v2でツイートを検索"""
        try:
            return self.x_api.search_recent_tweets(query, max_results=max_results)
        except Exception as e:
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

            min_followers = self.config.get('min_followers_to_target', 0)
            for tweet in result.get('data', []):
                author_id = tweet['author_id']
                user = users.get(author_id, {})
                username = user.get('username', '')
                followers = user.get('public_metrics', {}).get('followers_count', 0)
                if username and username != 'cat_hokke' and followers >= min_followers:
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

    def _within_active_hours(self) -> bool:
        """JSTベースの稼働時間判定"""
        active = self.config.get("active_hours_jst", {})
        start = int(active.get("start", 0))
        end = int(active.get("end", 23))
        jst = timezone(timedelta(hours=9))
        now_hour = datetime.now(jst).hour
        if start <= end:
            return start <= now_hour <= end
        # e.g. start=22, end=5 (overnight)
        return now_hour >= start or now_hour <= end

    def get_best_tweet(self, user_id: str) -> Optional[dict]:
        """ユーザーのツイートをエンゲージメントスコアで選定"""
        try:
            data = self.x_api.get_user_tweets(user_id, max_results=10)
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

    def _call_claude(self, system_prompt: str, user_prompt: str, timeout: int = 45) -> Optional[str]:
        """Claude CLI共通呼び出し"""
        prompt = f"""# System
{system_prompt}

# User
{user_prompt}
"""
        # Prefer PATH lookup for portability; fallback to known local path.
        claude_cmd = shutil.which("claude")
        if not claude_cmd:
            fallback = "/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude"
            if Path(fallback).exists():
                claude_cmd = fallback
            else:
                print("  claude コマンドが見つからない")
                return None

        try:
            result = subprocess.run(
                [claude_cmd, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print("  Claude呼び出しタイムアウト")
            return None
        except FileNotFoundError:
            print("  claude コマンドが見つからない")
            return None

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            print(f"  Claude実行エラー (exit={result.returncode}): {err[:200]}")
            return None
        return (result.stdout or "").strip()

    def _extract_reply_text(self, raw: str) -> str:
        """Model output sanitization for reply body."""
        text = (raw or "").strip()
        if not text:
            return ""

        # Remove fenced blocks if present.
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)

        # Drop common leading labels.
        text = re.sub(r"^(リプライ|返信|Reply)\s*[:：]\s*", "", text)

        # Use first meaningful line to avoid explanatory tails.
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            text = lines[0]

        # Trim enclosing quotes
        text = text.strip().strip('"').strip("「").strip("」")
        return text.strip()

    def judge_tweet(self, tweet_text: str) -> Optional[str]:
        """Step 1: ツイートにリプすべきか判断（低temperature）

        Returns:
            None: リプOK
            str: スキップ理由
        """
        system_prompt = """あなたはSNS投稿の安全性を判断するモデレーターです。
以下のツイートに、猫キャラクターのアカウントがリプライしても問題ないか判断してください。

## スキップすべきケース
- 訃報・お悔やみ・死亡に関する内容
- 深刻な病気・入院・事故の報告
- 炎上中・論争中の話題
- 政治的・宗教的に繊細な内容
- 明らかな宣伝・スパム・勧誘
- 内容が薄すぎてリプしようがない（「あ」「。」だけ等）
- 文脈がわからない（他ツイートへの返信や内輪ネタ等）
- 怒りや悲しみが強すぎて猫がリプすると不謹慎になりそうな内容
- 下ネタ・性的な含意があるツイート（隠語・スラング・ダブルミーニング含む）
- 誤読リスクが高いツイート（字面と真意が異なる可能性がある）

## 出力形式（厳守）
JSON形式で出力。他の文字は一切含めないこと。
リプOK: {"ok": true}
スキップ: {"ok": false, "reason": "簡潔な理由"}"""

        user_prompt = f"このツイートを判断してください:\n\n{tweet_text}"

        raw = self._call_claude(system_prompt, user_prompt, timeout=45)
        if not raw:
            return "LLM呼び出し失敗"

        try:
            # Claude出力に説明が混ざる場合に備えてJSONを抽出
            m = re.search(r"\{.*?\}", raw, re.DOTALL)
            payload = m.group(0) if m else raw
            result = json_module.loads(payload)
            if result.get("ok"):
                return None  # リプOK
            return result.get("reason", "不明な理由でスキップ")
        except (json_module.JSONDecodeError, TypeError):
            print(f"  判断JSONパース失敗: {raw}")
            return "判断レスポンス不正"

    def generate_reply(self, tweet_text: str, category: str) -> Optional[str]:
        """Step 1で判断 → Step 2でリプ生成の2段階

        Returns:
            str: リプライ本文
            None: スキップ（LLM判断 or 生成失敗）
            戻り値がNoneかつ self._last_skip_reason が設定されている場合はLLMスキップ
        """
        self._last_skip_reason = None

        # --- Step 1: 判断 ---
        skip_reason = self.judge_tweet(tweet_text)
        if skip_reason:
            print(f"  LLM判断: スキップ ({skip_reason})")
            self._last_skip_reason = skip_reason
            return None

        # --- Step 2: リプ生成 ---
        system_prompt = """あなたは「ホッケ」というキャラクターです。以下のペルソナに厳密に従ってリプライを生成してください。

## ペルソナ要約
- チャトラの猫。脱力してる。シュール。たまに鋭い。
- 一人称: 使わないか「俺」。「僕」「私」は使わない。
- 語尾キャラにしない。「〜にゃ」は封印。自然な話し言葉。
- 短文。体言止め多め。句読点少なめ。タメ口。
- 絶対やらないこと: 意識高い発言、説教、自己啓発、過度な共感（「わかるー！」）、媚び、絵文字の乱用
- 優しいけど甘くない。慰めない。でも否定もしない。

## リプライのルール
- 1〜2文で短く返す（最大80文字程度）
- 「すごい」「いいね」「わかる」だけの薄いリプはしない
- 相手のツイート内容に対してホッケらしい視点でコメントする
- 猫の視点から人間を観察するような一言が理想
- 攻撃的にならない。でも媚びない。
- リプライ本文のみを出力。説明や前置きは不要。"""

        user_prompt = f"以下のツイートにホッケとしてリプライしてください。\n\nツイート: {tweet_text}"

        reply_raw = self._call_claude(system_prompt, user_prompt, timeout=60)
        reply = self._extract_reply_text(reply_raw or "")
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

    def execute_replies(self, dry_run: bool = False) -> dict:
        """リプライを実行"""
        if not self._is_enabled():
            print("リプライエンジンは無効です")
            return {"posted": 0, "skipped": 0}

        if not self._within_active_hours():
            print("稼働時間外のためスキップ")
            return {"posted": 0, "skipped": 0}

        daily_limit = self.config.get('daily_reply_limit', 10)
        session_limit = self.config.get('session_reply_limit', daily_limit)
        interval = self.config.get('reply_interval_seconds', 180)
        per_query = self.config.get('search_tweets_per_query', 10)
        max_queries = self.config.get('search_queries_per_run', 2)
        min_followers = self.config.get('min_followers_to_target', 0)
        max_followers = self.config.get('max_followers_to_target', 999999999)
        max_consecutive_skips = self.config.get('max_consecutive_skips', 5)
        max_consecutive_failures = self.config.get('max_consecutive_failures', 3)

        today_count = self._today_reply_count()

        if today_count >= daily_limit:
            print(f"今日の上限に到達済み ({today_count}/{daily_limit})")
            return {"posted": 0, "skipped": 0}

        remaining_today = daily_limit - today_count
        remaining = min(session_limit, remaining_today)
        if remaining <= 0:
            print("このセッションの残り投稿枠なし")
            return {"posted": 0, "skipped": 0}

        keywords = self.config.get('search_keywords', {})
        query_pool = []
        for category, kws in keywords.items():
            for kw in kws:
                query_pool.append((category, kw))
        random.shuffle(query_pool)
        queries_to_run = query_pool[:max_queries]

        posted = 0
        skipped = 0
        seen_tweet_ids: set[str] = set()
        session_replied_users: set[str] = set()
        consecutive_skips = 0
        consecutive_failures = 0

        print(f"\n--- 開始: {len(queries_to_run)}クエリから最大{remaining}件を処理します ---")

        for qi, (category, query) in enumerate(queries_to_run):
            if posted >= remaining:
                break
            print(f"\n[query {qi+1}/{len(queries_to_run)}] 検索中: '{query}' ({category})")
            result = self.search_tweets(query, per_query)
            tweets = result.get("data", [])
            users = {u["id"]: u for u in result.get("includes", {}).get("users", [])}

            for tweet in tweets:
                if posted >= remaining:
                    break

                tweet_id = str(tweet.get("id", ""))
                tweet_text = tweet.get("text", "")
                author_id = tweet.get("author_id", "")
                user = users.get(author_id, {})
                username = user.get("username", "")
                followers = user.get("public_metrics", {}).get("followers_count", 0)

                if not tweet_id or tweet_id in seen_tweet_ids:
                    continue
                seen_tweet_ids.add(tweet_id)

                if not username or username == "cat_hokke":
                    skipped += 1
                    continue
                if followers < min_followers or followers > max_followers:
                    skipped += 1
                    continue
                if self._replied_today(username) or username in session_replied_users:
                    skipped += 1
                    continue
                if self.is_ng(tweet_text):
                    skipped += 1
                    consecutive_skips += 1
                    if consecutive_skips >= max_consecutive_skips:
                        print(f"連続スキップ上限に到達 ({consecutive_skips})。セッション終了")
                        return {"posted": posted, "skipped": skipped}
                    continue

                reply_text = self.generate_reply(tweet_text, category)
                if not reply_text:
                    if self._last_skip_reason:
                        print(f"  LLMスキップ。理由: {self._last_skip_reason}")
                        self.log.append({
                            "date": date.today().isoformat(),
                            "timestamp": datetime.now().isoformat(),
                            "target_user": username,
                            "target_tweet_id": tweet_id,
                            "target_tweet_text": tweet_text[:200],
                            "reply_text": None,
                            "category": category,
                            "status": "llm_skip",
                            "skip_reason": self._last_skip_reason,
                            "source_query": query
                        })
                        save_json(LOG_FILE, self.log)
                    skipped += 1
                    consecutive_skips += 1
                    if consecutive_skips >= max_consecutive_skips:
                        print(f"連続スキップ上限に到達 ({consecutive_skips})。セッション終了")
                        return {"posted": posted, "skipped": skipped}
                    continue

                # 投稿
                if dry_run:
                    print(f"  [DRY RUN] @{username} へ: {reply_text}")
                    status = "dry_run"
                else:
                    post_result = self.poster.post_reply(reply_text, tweet_id)
                    status = "posted" if post_result.get('success') else "failed"
                    if not post_result.get('success'):
                        print(f"  投稿失敗: {post_result.get('error')}")
                        skipped += 1
                        consecutive_failures += 1
                        if consecutive_failures >= max_consecutive_failures:
                            print(f"連続失敗上限に到達 ({consecutive_failures})。セッション終了")
                            return {"posted": posted, "skipped": skipped}
                        continue

                self.log.append({
                    "date": date.today().isoformat(),
                    "timestamp": datetime.now().isoformat(),
                    "target_user": username,
                    "target_tweet_id": tweet_id,
                    "target_tweet_text": tweet_text[:200],
                    "reply_text": reply_text,
                    "category": category,
                    "status": status,
                    "source_query": query
                })
                save_json(LOG_FILE, self.log)

                # ターゲット情報更新（既存ターゲットのみ）
                for target in self.targets:
                    if target.get("username") == username:
                        target['reply_count'] = target.get('reply_count', 0) + 1
                        target['last_replied_at'] = datetime.now().isoformat()
                        save_json(TARGETS_FILE, self.targets)
                        break

                posted += 1
                consecutive_skips = 0
                consecutive_failures = 0
                session_replied_users.add(username)
                print(f"  リプ完了: @{username} / {reply_text[:50]}")

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
