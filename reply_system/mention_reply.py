#!/usr/bin/env python3
"""
ホッケ メンションリプライシステム
@cat_hokke へのメンションに対してリプライを返す
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import date, datetime

# 即時フラッシュ
sys.stdout.reconfigure(line_buffering=True)

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
STATE_FILE = SCRIPT_DIR / "mention_state.json"

sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
from x_api_client import XApiClient
from x_poster import XPoster

# ReplyEngine を利用（judge_tweet, generate_reply, is_ng）
from reply_engine import ReplyEngine

USERNAME = "cat_hokke"
DAILY_LIMIT = 10
SESSION_LIMIT = 3
REPLY_INTERVAL_SECONDS = 300
# processed_ids は直近100件だけ保持（肥大化防止）
MAX_PROCESSED_IDS = 100


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] mention_state.json 読み込み失敗、初期状態で続行: {e}")
    return {
        "last_since_id": None,
        "today_reply_count": 0,
        "today_date": None,
        "processed_ids": [],
    }


def save_state(state: dict) -> None:
    # processed_ids をトリム
    state["processed_ids"] = state["processed_ids"][-MAX_PROCESSED_IDS:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def run_mention_reply(dry_run: bool = False) -> dict:
    """メンションを取得してリプライを実行"""
    state = load_state()
    today = date.today().isoformat()

    # 日付変わったらカウントリセット
    if state.get("today_date") != today:
        state["today_date"] = today
        state["today_reply_count"] = 0

    if state["today_reply_count"] >= DAILY_LIMIT:
        print(f"日次上限到達済み ({state['today_reply_count']}/{DAILY_LIMIT})")
        return {"posted": 0, "skipped": 0}

    # API クライアント
    x_api = XApiClient(require_bearer=True)

    # メンション取得
    since_id = state.get("last_since_id")
    print(f"メンション検索中... (since_id={since_id})")
    try:
        result = x_api.search_mentions(USERNAME, since_id=since_id)
    except Exception as e:
        print(f"メンション検索エラー: {e}")
        return {"posted": 0, "skipped": 0, "error": str(e)}

    tweets = result.get("data", []) or []
    users_list = result.get("includes", {}).get("users", []) or []
    users = {u["id"]: u for u in users_list}

    if not tweets:
        print("新着メンションなし")
        if not dry_run:
            save_state(state)
        return {"posted": 0, "skipped": 0}

    print(f"新着メンション: {len(tweets)}件")

    # ReplyEngine インスタンス生成（judge_tweet, generate_reply, is_ng を使う）
    engine = ReplyEngine()

    # 投稿用
    poster = None
    if not dry_run:
        poster = XPoster()

    processed_set = set(state.get("processed_ids", []))
    posted = 0
    skipped = 0
    new_since_id = since_id

    for tweet in tweets:
        tweet_id = str(tweet.get("id", ""))
        tweet_text = tweet.get("text", "")
        author_id = tweet.get("author_id", "")
        user = users.get(author_id, {})
        author_username = user.get("username", "")

        # since_id 更新（最大IDを追跡、int比較で桁数差異に対応）
        if not new_since_id or int(tweet_id) > int(new_since_id):
            new_since_id = tweet_id

        # セッション上限
        if posted >= SESSION_LIMIT:
            print(f"セッション上限到達 ({SESSION_LIMIT}件)")
            break

        # 日次上限
        if state["today_reply_count"] + posted >= DAILY_LIMIT:
            print(f"日次上限到達 ({DAILY_LIMIT}件)")
            break

        # 既処理スキップ
        if tweet_id in processed_set:
            continue

        # 自分自身のツイートはスキップ
        if author_username == USERNAME:
            if not dry_run:
                state["processed_ids"].append(tweet_id)
            continue

        print(f"\n--- @{author_username}: {tweet_text[:80]} ---")

        # NGフィルタ
        if engine.is_ng(tweet_text):
            print("  NGキーワード検出 → スキップ")
            if not dry_run:
                state["processed_ids"].append(tweet_id)
            skipped += 1
            continue

        # LLM安全性チェック
        skip_reason = engine.judge_tweet(tweet_text)
        if skip_reason:
            print(f"  LLM判断: スキップ ({skip_reason})")
            if not dry_run:
                state["processed_ids"].append(tweet_id)
            skipped += 1
            continue

        # リプライ生成
        reply_text = engine.generate_reply(tweet_text, "メンション")
        if not reply_text:
            reason = getattr(engine, "_last_skip_reason", None) or "生成失敗"
            print(f"  リプライ生成失敗: {reason}")
            if not dry_run:
                state["processed_ids"].append(tweet_id)
            skipped += 1
            continue

        # 投稿
        if dry_run:
            print(f"  [DRY RUN] → {reply_text}")
        else:
            post_result = poster.post_reply(reply_text, tweet_id)
            if not post_result.get("success"):
                print(f"  投稿失敗: {post_result.get('error')}")
                state["processed_ids"].append(tweet_id)
                skipped += 1
                continue
            reply_tweet_id = post_result.get("tweet_id")
            if reply_tweet_id:
                poster._record_to_hook_performance(
                    reply_tweet_id, reply_text, "メンション", tweet_type="reply"
                )
            print(f"  投稿成功: {reply_text[:50]}")
            state["processed_ids"].append(tweet_id)

        posted += 1

        # インターバル（最後の投稿後は不要）
        if not dry_run and posted < SESSION_LIMIT:
            print(f"  {REPLY_INTERVAL_SECONDS}秒待機...")
            time.sleep(REPLY_INTERVAL_SECONDS)

    # 状態更新（dry-run時は保存しない）
    if not dry_run:
        if new_since_id:
            state["last_since_id"] = new_since_id
        state["today_reply_count"] += posted
        save_state(state)

    print(f"\n結果: {posted}件投稿, {skipped}件スキップ")
    return {"posted": posted, "skipped": skipped}


def show_status() -> None:
    """現在の状態を表示"""
    state = load_state()
    today = date.today().isoformat()
    is_today = state.get("today_date") == today
    count = state.get("today_reply_count", 0) if is_today else 0

    print(f"メンションリプライ状態:")
    print(f"  last_since_id: {state.get('last_since_id', 'なし')}")
    print(f"  今日のリプライ数: {count}/{DAILY_LIMIT}")
    print(f"  セッション上限: {SESSION_LIMIT}件/実行")
    print(f"  処理済みID数: {len(state.get('processed_ids', []))}")
    print(f"  記録日: {state.get('today_date', 'なし')}")


def main():
    parser = argparse.ArgumentParser(description="ホッケ メンションリプライ")
    sub = parser.add_subparsers(dest="action", required=True)

    run_p = sub.add_parser("run", help="メンションリプライ実行")
    run_p.add_argument("--dry-run", action="store_true", help="投稿せずにシミュレーション")

    sub.add_parser("status", help="状態表示")

    args = parser.parse_args()

    if args.action == "run":
        result = run_mention_reply(dry_run=args.dry_run)
        if result.get("error"):
            sys.exit(1)
    elif args.action == "status":
        show_status()


if __name__ == "__main__":
    main()
