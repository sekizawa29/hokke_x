#!/usr/bin/env python3
"""
ホッケ 引用ツイートエンジン
良さそうなツイートを見つけて、猫の視点で引用コメントを付ける
"""

import sys
import json
import time
import random
import argparse
from pathlib import Path
from datetime import date, datetime, timezone, timedelta

# 即時フラッシュ
sys.stdout.reconfigure(line_buffering=True)

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "quote_config.json"
STATE_FILE = SCRIPT_DIR / "quote_state.json"
LOG_FILE = SCRIPT_DIR / "quote_log.json"

sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
from x_api_client import XApiClient
from x_poster import XPoster

# ReplyEngine の共通機能を再利用
from reply_engine import ReplyEngine


def load_json(path: Path) -> any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] {path.name} 読み込み失敗: {e}")
    return [] if path.name.endswith("_log.json") else {}


def save_json(path: Path, data: any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] quote_state.json 読み込み失敗、初期状態で続行: {e}")
    return {
        "today_quote_count": 0,
        "today_date": None,
        "quoted_users": {},
    }


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _within_active_hours(config: dict) -> bool:
    active = config.get("active_hours_jst", {})
    start = int(active.get("start", 0))
    end = int(active.get("end", 23))
    jst = timezone(timedelta(hours=9))
    now_hour = datetime.now(jst).hour
    if start <= end:
        return start <= now_hour <= end
    return now_hour >= start or now_hour <= end


def _is_cooled_down(state: dict, username: str, cooldown_days: int) -> bool:
    """ユーザーへの引用が十分冷却されているか"""
    quoted_users = state.get("quoted_users", {})
    last_quoted = quoted_users.get(username)
    if not last_quoted:
        return True
    try:
        last_date = datetime.fromisoformat(last_quoted).date()
        return (date.today() - last_date).days >= cooldown_days
    except (ValueError, TypeError):
        return True


QUOTE_SYSTEM_PROMPT_TEMPLATE = """あなたは「ホッケ」というキャラクターです。以下のペルソナ定義に厳密に従って、引用ツイートのコメントを生成してください。

{persona}

## 引用ツイートのルール
- 1〜2文で短く（最大80文字程度）
- 相手への語りかけではなく、自分のフォロワーに向けた独り言・感想として書く
- 猫として「これは気になる」「猫的にはこう思う」という視点
- カテゴリが「逆張り・猫の教え」の場合は、人間の努力に対して「猫はそんなことしなくても生きてる」的な軽い逆張り。説教にはしない。
- 「すごい」「いいね」「わかる」だけの薄いコメントは禁止
- @ユーザー名は入れない（引用で通知が飛ぶから不要）
- 引用コメント本文のみを出力。説明や前置きは不要。"""


def run_quote(dry_run: bool = False) -> dict:
    """引用ツイートを実行"""
    config = load_json(CONFIG_FILE)
    if not config:
        print("quote_config.json が見つからないか空です")
        return {"posted": 0, "skipped": 0, "error": "no config"}

    state = load_state()
    log = load_json(LOG_FILE)
    today = date.today().isoformat()

    # 日付リセット
    if state.get("today_date") != today:
        state["today_date"] = today
        state["today_quote_count"] = 0

    daily_limit = config.get("daily_quote_limit", 2)
    session_limit = config.get("session_quote_limit", 1)

    if state["today_quote_count"] >= daily_limit:
        print(f"日次上限到達済み ({state['today_quote_count']}/{daily_limit})")
        return {"posted": 0, "skipped": 0}

    if not _within_active_hours(config):
        print("稼働時間外のためスキップ")
        return {"posted": 0, "skipped": 0}

    remaining = min(session_limit, daily_limit - state["today_quote_count"])

    # 検索
    x_api = XApiClient(require_bearer=True)
    engine = ReplyEngine()

    keywords = config.get("search_keywords", {})
    per_query = config.get("search_tweets_per_query", 10)
    max_queries = config.get("search_queries_per_run", 2)
    min_followers = config.get("min_followers_to_target", 50)
    max_followers = config.get("max_followers_to_target", 50000)
    cooldown_days = config.get("cooldown_days_per_user", 7)
    max_consecutive_skips = config.get("max_consecutive_skips", 5)
    max_consecutive_failures = config.get("max_consecutive_failures", 3)

    query_pool = []
    for category, kws in keywords.items():
        for kw in kws:
            query_pool.append((category, kw))
    random.shuffle(query_pool)
    queries_to_run = query_pool[:max_queries]

    poster = None
    if not dry_run:
        poster = XPoster()

    posted = 0
    skipped = 0
    seen_tweet_ids: set[str] = set()
    consecutive_skips = 0
    consecutive_failures = 0

    print(f"\n--- 引用ツイート: {len(queries_to_run)}クエリから最大{remaining}件 ---")

    for qi, (category, query) in enumerate(queries_to_run):
        if posted >= remaining:
            break

        print(f"\n[query {qi+1}/{len(queries_to_run)}] 検索中: '{query}' ({category})")
        try:
            result = x_api.search_recent_tweets(query, max_results=per_query)
        except Exception as e:
            print(f"  検索エラー: {e}")
            continue

        tweets = result.get("data", []) or []
        users = {u["id"]: u for u in result.get("includes", {}).get("users", []) or []}

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

            if not _is_cooled_down(state, username, cooldown_days):
                skipped += 1
                continue

            if engine.is_ng(tweet_text):
                skipped += 1
                consecutive_skips += 1
                if consecutive_skips >= max_consecutive_skips:
                    print(f"連続スキップ上限 ({consecutive_skips})。停止")
                    break
                continue

            # LLM安全性チェック
            skip_reason = engine.judge_tweet(tweet_text)
            if skip_reason:
                print(f"  LLM判断: スキップ ({skip_reason})")
                skipped += 1
                consecutive_skips += 1
                if consecutive_skips >= max_consecutive_skips:
                    print(f"連続スキップ上限 ({consecutive_skips})。停止")
                    break
                continue

            # 引用コメント生成
            print(f"  対象: @{username}: {tweet_text[:80]}")
            system_prompt = QUOTE_SYSTEM_PROMPT_TEMPLATE.format(persona=engine.persona)
            if category == "逆張り・猫の教え":
                user_prompt = f"以下のツイートに対して、猫の視点から「別にそれ要らなくない？」的な軽い逆張りコメントを引用ツイートとして書いてください。説教にはしないこと。\n\nツイート: {tweet_text}"
            else:
                user_prompt = f"以下のツイートに対して、猫として気になったポイントにコメントする引用ツイートを書いてください。\n\nカテゴリ: {category}\nツイート: {tweet_text}"

            raw = engine._call_claude(system_prompt, user_prompt, timeout=60)
            comment = engine._extract_reply_text(raw or "")
            if not comment:
                print("  コメント生成失敗")
                skipped += 1
                consecutive_skips += 1
                continue

            if len(comment) > 140:
                comment = comment[:140]

            # セルフチェック
            ng_phrases = ['頑張', '応援', '素敵', 'ありがとう', '！！', '😊', '💪', '✨']
            ng_hit = False
            for phrase in ng_phrases:
                if phrase in comment:
                    print(f"  セルフチェックNG: '{phrase}'")
                    ng_hit = True
                    break
            if ng_hit:
                skipped += 1
                consecutive_skips += 1
                continue

            # 投稿
            if dry_run:
                print(f"  [DRY RUN] 引用コメント: {comment}")
            else:
                post_result = poster.post_quote(comment, tweet_id)
                if not post_result.get("success"):
                    print(f"  投稿失敗: {post_result.get('error')}")
                    skipped += 1
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        print(f"連続失敗上限 ({consecutive_failures})。停止")
                        break
                    continue
                quote_tweet_id = post_result.get("tweet_id")
                if quote_tweet_id:
                    poster._record_to_hook_performance(
                        quote_tweet_id, comment, category, tweet_type="quote"
                    )
                print(f"  投稿成功: {comment[:50]}")

            # ログ記録
            log_entry = {
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "target_user": username,
                "target_tweet_id": tweet_id,
                "target_tweet_text": tweet_text[:200],
                "quote_comment": comment,
                "category": category,
                "status": "dry_run" if dry_run else "posted",
                "source_query": query,
            }
            log.append(log_entry)
            if not dry_run:
                save_json(LOG_FILE, log)

            posted += 1
            consecutive_skips = 0
            consecutive_failures = 0

            # クールダウン記録
            if not dry_run:
                state["quoted_users"][username] = datetime.now().isoformat()

            if not dry_run and posted < remaining:
                interval = config.get("quote_interval_seconds", 300)
                print(f"  {interval}秒待機...")
                time.sleep(interval)

    # 状態更新
    if not dry_run:
        state["today_quote_count"] += posted
        save_state(state)

    print(f"\n結果: {posted}件投稿, {skipped}件スキップ")
    return {"posted": posted, "skipped": skipped}


def show_status() -> None:
    config = load_json(CONFIG_FILE)
    state = load_state()
    log = load_json(LOG_FILE)
    today = date.today().isoformat()
    is_today = state.get("today_date") == today
    count = state.get("today_quote_count", 0) if is_today else 0
    daily_limit = config.get("daily_quote_limit", 2)
    total = len([e for e in log if e.get("status") == "posted"]) if isinstance(log, list) else 0

    print("引用ツイート状態:")
    print(f"  今日の引用数: {count}/{daily_limit}")
    print(f"  セッション上限: {config.get('session_quote_limit', 1)}件/実行")
    print(f"  累計引用数: {total}")
    print(f"  クールダウン中ユーザー数: {len(state.get('quoted_users', {}))}")
    print(f"  記録日: {state.get('today_date', 'なし')}")


def main():
    parser = argparse.ArgumentParser(description="ホッケ 引用ツイートエンジン")
    sub = parser.add_subparsers(dest="action", required=True)

    run_p = sub.add_parser("run", help="引用ツイート実行")
    run_p.add_argument("--dry-run", action="store_true", help="投稿せずにシミュレーション")

    sub.add_parser("status", help="状態表示")

    args = parser.parse_args()

    if args.action == "run":
        result = run_quote(dry_run=args.dry_run)
        if result.get("error"):
            sys.exit(1)
    elif args.action == "status":
        show_status()


if __name__ == "__main__":
    main()
