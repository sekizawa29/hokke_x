#!/usr/bin/env python3
"""
ほっけ エンゲージメント取得スクリプト
hook_performance.json の未取得エントリに対してX APIでエンゲージメントを一括取得し診断する。
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from x_api_client import XApiClient

try:
    import tweepy
except ImportError:
    print("tweepyがインストールされていません")
    print("pip install tweepy python-dotenv")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).parent
HOOK_PERF_FILE = SCRIPT_DIR.parent / "hook_performance.json"


def diagnose(likes: int, retweets: int) -> str:
    total = likes + retweets
    if total >= 50:
        return "SCALE"   # バリエーション3本すぐ作る
    elif total >= 10:
        return "GOOD"    # そのカテゴリ継続
    elif total >= 3:
        return "OK"      # 別アングルで1回再挑戦
    else:
        return "DROP"    # 別カテゴリに切り替え


def load_perf_data() -> dict:
    if not HOOK_PERF_FILE.exists():
        return {"version": "1.0", "posts": []}
    with open(HOOK_PERF_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_perf_data(data: dict) -> None:
    with open(HOOK_PERF_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_pending_posts(data: dict, threshold_hours: int) -> list:
    """エンゲージメント未取得かつ閾値時間経過済みの投稿を返す"""
    now = datetime.now(timezone.utc)
    pending = []
    for post in data["posts"]:
        if post.get("engagementFetchedAt") is not None:
            continue
        posted_at_str = post.get("postedAt")
        if not posted_at_str:
            continue
        # タイムゾーン情報がある場合とない場合を両対応
        try:
            posted_at = datetime.fromisoformat(posted_at_str)
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone(timedelta(hours=9)))  # JST
        except ValueError:
            continue
        elapsed_hours = (now - posted_at).total_seconds() / 3600
        if elapsed_hours >= threshold_hours:
            pending.append(post)
    return pending


def fetch_engagement(api_client: XApiClient, posts: list) -> list:
    """バッチでエンゲージメントを取得して posts を更新して返す"""
    tweet_ids = [p["tweet_id"] for p in posts]
    now_str = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S')

    # 最大100件ずつバッチ処理
    updated = []
    for batch_start in range(0, len(tweet_ids), 100):
        batch_ids = tweet_ids[batch_start:batch_start + 100]
        batch_posts = posts[batch_start:batch_start + 100]

        try:
            response = api_client.get_tweets_public_metrics(batch_ids)
        except tweepy.TweepyException as e:
            print(f"[ERROR] API呼び出し失敗: {e}")
            updated.extend(batch_posts)
            continue

        if not response.data:
            print(f"[WARN] レスポンスデータなし（batch {batch_start}）")
            updated.extend(batch_posts)
            continue

        # tweet_id → data のマップを作成
        tweet_map = {str(t.id): t for t in response.data}

        for post in batch_posts:
            tid = post["tweet_id"]
            tweet = tweet_map.get(tid)
            if not tweet:
                print(f"[WARN] tweet_id={tid} が見つからない")
                updated.append(post)
                continue

            pub = tweet.public_metrics or {}

            post["likes"] = pub.get("like_count")
            post["retweets"] = pub.get("retweet_count")
            post["replies"] = pub.get("reply_count")
            post["quotes"] = pub.get("quote_count")
            post["bookmarks"] = pub.get("bookmark_count")
            post["impressions"] = None  # Free プランでは取得不可
            post["url_link_clicks"] = None
            post["user_profile_clicks"] = None
            post["engagementFetchedAt"] = now_str

            likes = post["likes"] or 0
            retweets = post["retweets"] or 0
            post["diagnosis"] = diagnose(likes, retweets)

            print(
                f"[取得] {post['hookCategory']} | "
                f"likes={post['likes']} RT={post['retweets']} "
                f"imp={post['impressions']} → {post['diagnosis']}"
            )
            updated.append(post)

    return updated


def print_recommend(data: dict) -> None:
    """今日の投稿カテゴリ推薦を表示（APIコールなし）"""
    from collections import defaultdict

    VALID_CATEGORIES = ["脱力系", "猫写真", "鋭い一言", "日常観察", "時事ネタ", "たまに有益", "未分類"]

    # 診断済み投稿をカテゴリ別に分類（投稿日時順）
    categories: dict = defaultdict(list)
    for post in data["posts"]:
        if post.get("diagnosis"):
            cat = post.get("hookCategory", "未分類")
            categories[cat].append(post)

    # 各カテゴリを投稿日時の新しい順にソート
    for cat in categories:
        categories[cat].sort(key=lambda p: p.get("postedAt", ""), reverse=True)

    lines_priority = []
    lines_candidate = []
    lines_ng = []
    lines_unknown = []

    seen_cats = set(categories.keys())

    for cat, posts in categories.items():
        n = len(posts)
        avg = sum((p.get("likes") or 0) + (p.get("retweets") or 0) for p in posts) / n
        latest_diag = posts[0].get("diagnosis", "")
        second_diag = posts[1].get("diagnosis", "") if n >= 2 else ""

        if n >= 2 and latest_diag == "DROP" and second_diag == "DROP":
            lines_ng.append(f"NG:   {cat} [DROP x2] avg={avg:.0f} ({n}件) ← 今日は避ける")
        elif latest_diag in ("SCALE", "GOOD"):
            lines_priority.append(f"優先: {cat} [{latest_diag}] avg={avg:.0f} ({n}件)")
        elif latest_diag == "OK":
            lines_candidate.append(f"候補: {cat} [OK] avg={avg:.0f} ({n}件)")
        else:
            # DROPだが連続ではない
            lines_candidate.append(f"候補: {cat} [DROP] avg={avg:.0f} ({n}件)")

    # データなしのカテゴリ
    for cat in VALID_CATEGORIES:
        if cat not in seen_cats and cat != "未分類":
            lines_unknown.append(f"未知: {cat} (データなし → 試してもOK)")

    print("\n=== 今日の投稿カテゴリ推薦 ===")
    for line in lines_priority:
        print(line)
    for line in lines_candidate:
        print(line)
    for line in lines_ng:
        print(line)
    for line in lines_unknown:
        print(line)

    if not (lines_priority or lines_candidate or lines_ng or lines_unknown):
        print("（データなし — まず投稿してカテゴリデータを蓄積してください）")


def print_summary(data: dict) -> None:
    """カテゴリ別パフォーマンス集計を表示"""
    fetched = [p for p in data["posts"] if p.get("engagementFetchedAt")]
    if not fetched:
        print("集計対象データなし（エンゲージメント取得済みの投稿がありません）")
        return

    from collections import defaultdict
    categories: dict = defaultdict(list)
    for post in fetched:
        categories[post.get("hookCategory", "未分類")].append(post)

    print("\n=== カテゴリ別パフォーマンス集計 ===")
    for cat, posts in sorted(categories.items()):
        n = len(posts)
        avg_likes = sum(p["likes"] or 0 for p in posts) / n
        avg_rt = sum(p["retweets"] or 0 for p in posts) / n
        avg_imp = sum(p["impressions"] or 0 for p in posts) / n

        diagnosis_counts: dict = defaultdict(int)
        for p in posts:
            if p.get("diagnosis"):
                diagnosis_counts[p["diagnosis"]] += 1

        diag_str = " / ".join(
            f"{k}: {v}件" for k, v in sorted(diagnosis_counts.items())
        )

        print(
            f"\n[{cat}] {n}件  "
            f"平均いいね:{avg_likes:.1f} / 平均RT:{avg_rt:.1f} / 平均impressions:{avg_imp:.0f}"
        )
        if diag_str:
            print(f"  {diag_str}")


def main():
    parser = argparse.ArgumentParser(description='ほっけ エンゲージメント取得・診断')
    parser.add_argument(
        '--threshold-hours', type=int, default=24,
        help='投稿からの経過時間（時間）の閾値（デフォルト: 24）'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='APIコールなしで対象一覧だけ表示'
    )
    parser.add_argument(
        '--summary', action='store_true',
        help='カテゴリ別集計を表示（週次レビュー用）'
    )
    parser.add_argument(
        '--recommend', action='store_true',
        help='今日の投稿カテゴリ推薦を表示（APIコールなし・自律投稿チェック用）'
    )
    args = parser.parse_args()

    data = load_perf_data()

    if args.recommend:
        print_recommend(data)
        return

    if args.summary:
        print_summary(data)
        return

    pending = get_pending_posts(data, args.threshold_hours)

    if not pending:
        print(f"対象投稿なし（閾値: {args.threshold_hours}時間, 未取得投稿数: 0）")
        return

    print(f"対象: {len(pending)}件（閾値: {args.threshold_hours}時間経過済み）")
    for p in pending:
        print(f"  - [{p['hookCategory']}] {p['postedAt']} | {p['text'][:30]}...")

    if args.dry_run:
        print("\n[dry-run] APIコールはスキップします")
        return

    try:
        api_client = XApiClient(require_bearer=True)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # pending posts を data["posts"] 内の同一オブジェクト参照で更新
    fetch_engagement(api_client, pending)
    save_perf_data(data)
    print(f"\n[完了] {len(pending)}件を更新しました → {HOOK_PERF_FILE}")


if __name__ == "__main__":
    main()
