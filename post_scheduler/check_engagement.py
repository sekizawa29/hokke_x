#!/usr/bin/env python3
"""
ほっけ エンゲージメント取得スクリプト
hook_performance.json の未取得エントリに対してX APIでエンゲージメントを一括取得し診断する。
"""

import os
import sys
import json
import re
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from x_api_client import XApiClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from notifications.discord_notifier import DiscordNotifier

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


def diagnose(likes: int, retweets: int, impressions: int = 0) -> str:
    # --- フォロワー少数期（~数百）: インプレッション基準 ---
    # アルゴリズムリーチを主指標とする
    if impressions >= 50:
        return "SCALE"   # バリエーション3本すぐ作る
    elif impressions >= 30:
        return "GOOD"    # そのカテゴリ継続
    elif impressions >= 10:
        return "OK"      # 別アングルで1回再挑戦
    else:
        return "DROP"    # 別カテゴリに切り替え
    # --- フォロワー増加後（数百〜）: いいね+RT基準に戻す ---
    # total = likes + retweets
    # if total >= 50:   return "SCALE"
    # elif total >= 10: return "GOOD"
    # elif total >= 3:  return "OK"
    # else:             return "DROP"


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
            post["diagnosis"] = diagnose(likes, retweets, impressions=0)

            print(
                f"[取得] {post['hookCategory']} | "
                f"likes={post['likes']} RT={post['retweets']} "
                f"imp={post['impressions']} → {post['diagnosis']}"
            )
            updated.append(post)

    return updated


def get_or_fetch_user_id(data: dict, api_client: XApiClient) -> str:
    """my_user_id をキャッシュから取得、なければAPIで取得して保存"""
    if data.get("my_user_id"):
        return data["my_user_id"]
    response = api_client.get_me()
    user_id = str(response.data.id)
    data["my_user_id"] = user_id
    print(f"[sync] user_id 取得・保存: {user_id}")
    return user_id


def sync_timeline(api_client: XApiClient, data: dict) -> int:
    """タイムラインを取得して hook_performance.json に upsert。返り値は追加+更新件数。"""
    user_id = get_or_fetch_user_id(data, api_client)
    since_id = data.get("last_since_id")

    tweets = api_client.get_user_tweets(user_id, max_results=100, since_id=since_id)
    if not tweets:
        print(f"[sync] 新規ツイートなし（since_id={since_id}）")
        return 0

    existing_ids = {p["tweet_id"] for p in data["posts"]}
    now_str = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S')
    max_id: Optional[str] = since_id
    added = 0
    updated = 0

    for tweet in tweets:
        tid = str(tweet.id)
        is_new = tid not in existing_ids

        if max_id is None or int(tid) > int(max_id):
            max_id = tid

        pub = tweet.public_metrics or {}
        non_pub = tweet.non_public_metrics or {}
        ref_types = {r["type"] for r in (tweet.referenced_tweets or [])}
        if tweet.in_reply_to_user_id is not None:
            tweet_type = "reply"
        elif "quoted" in ref_types:
            tweet_type = "quote"
        else:
            tweet_type = "post"
        likes = pub.get("like_count")
        retweets = pub.get("retweet_count")
        impressions = (non_pub.get("impression_count") or 0)
        diagnosis = diagnose(likes or 0, retweets or 0, impressions=impressions)

        if tweet.created_at:
            posted_at = tweet.created_at.astimezone(
                timezone(timedelta(hours=9))
            ).strftime('%Y-%m-%dT%H:%M:%S')
        else:
            posted_at = now_str

        if is_new:
            hook_category = "リプライ" if tweet_type == "reply" else "未分類"
            data["posts"].append({
                "tweet_id": tid,
                "text": tweet.text,
                "hookCategory": hook_category,
                "tweet_type": tweet_type,
                "postedAt": posted_at,
                "engagementFetchedAt": now_str,
                "likes": likes,
                "retweets": retweets,
                "replies": pub.get("reply_count"),
                "quotes": pub.get("quote_count"),
                "bookmarks": pub.get("bookmark_count"),
                "impressions": non_pub.get("impression_count"),
                "engagements": non_pub.get("engagements"),
                "url_link_clicks": non_pub.get("url_link_clicks"),
                "user_profile_clicks": non_pub.get("user_profile_clicks"),
                "diagnosis": diagnosis,
            })
            existing_ids.add(tid)
            added += 1
        else:
            for post in data["posts"]:
                if post["tweet_id"] == tid:
                    post["likes"] = likes
                    post["retweets"] = retweets
                    post["replies"] = pub.get("reply_count")
                    post["quotes"] = pub.get("quote_count")
                    post["bookmarks"] = pub.get("bookmark_count")
                    post["impressions"] = non_pub.get("impression_count")
                    post["engagements"] = non_pub.get("engagements")
                    post["url_link_clicks"] = non_pub.get("url_link_clicks")
                    post["user_profile_clicks"] = non_pub.get("user_profile_clicks")
                    post["tweet_type"] = tweet_type
                    post["engagementFetchedAt"] = now_str
                    post["diagnosis"] = diagnosis
                    break
            updated += 1

        imp = non_pub.get("impression_count")
        label = "新規" if is_new else "更新"
        print(
            f"[sync] {label} {tweet_type} | "
            f"likes={likes} RT={retweets} imp={imp} | "
            f"{tweet.text[:30]}..."
        )

    data["last_since_id"] = max_id
    print(f"[sync] 完了: 新規{added}件 / 更新{updated}件 / last_since_id={max_id}")
    return added + updated


VALID_HOOK_CATEGORIES = ["猫写真", "鋭い一言", "日常観察", "脱力系", "時事ネタ", "たまに有益", "猫Meme", "猫vs人間", "シュール猫"]

CATEGORIZE_SYSTEM_PROMPT = """あなたはホッケ（茶トラ猫AIアカウント）の投稿分析アシスタントです。
与えられた投稿テキストを以下のカテゴリのどれか1つに分類してください。

カテゴリ一覧:
- 猫写真: 画像付き、猫の様子を見せる投稿（リアル猫写真）
- 鋭い一言: 人間vs猫の哲学的観察、社会への皮肉・気づき
- 日常観察: 飼い主や日常の出来事を淡々と描写
- 脱力系: やる気のなさ・眠い・どうでもいい系
- 時事ネタ: 時事・トレンドへの猫目線コメント
- たまに有益: 実用的・有益な情報を含む
- 猫Meme: 共感・あるある系のMeme画像付き投稿
- 猫vs人間: 猫と人間の生活を対比する画像付き投稿
- シュール猫: 猫が人間の行動をしているシュール画像付き投稿

カテゴリ名のみを1単語で返してください。余計な説明は不要です。"""


def _call_claude(prompt: str, timeout: int = 30) -> Optional[str]:
    claude_cmd = shutil.which("claude")
    if not claude_cmd:
        fallback = "/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude"
        if Path(fallback).exists():
            claude_cmd = fallback
        else:
            return None
    # CLAUDECODE を除いた環境変数（ネスト起動ブロックを回避）
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        result = subprocess.run(
            [claude_cmd, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def categorize_unknown_posts(data: dict) -> int:
    """hookCategory='未分類' の投稿を Claude で自動分類する。返り値は更新件数。"""
    unknown = [p for p in data["posts"] if p.get("hookCategory") == "未分類"]
    if not unknown:
        return 0

    print(f"[categorize] 未分類: {len(unknown)}件 → Claude で分類します", flush=True)
    updated = 0

    for post in unknown:
        prompt = f"""{CATEGORIZE_SYSTEM_PROMPT}

投稿テキスト:
{post['text']}"""

        result = _call_claude(prompt)
        if not result:
            print(f"  [SKIP] Claude 応答なし: {post['text'][:30]}...", flush=True)
            continue

        # カテゴリ名を正規化（余分な文字除去）
        category = result.strip().strip("「」'\"")
        if category not in VALID_HOOK_CATEGORIES:
            # 部分一致で救済
            matched = next((c for c in VALID_HOOK_CATEGORIES if c in category), None)
            if matched:
                category = matched
            else:
                print(f"  [SKIP] 不明カテゴリ '{category}': {post['text'][:30]}...", flush=True)
                continue

        post["hookCategory"] = category
        print(f"  [{category}] {post['text'][:50]}...", flush=True)
        updated += 1

    print(f"[categorize] 完了: {updated}/{len(unknown)}件 分類済み", flush=True)
    return updated


def print_recommend(data: dict) -> None:
    """今日の投稿カテゴリ推薦を表示（APIコールなし）"""
    from collections import defaultdict

    VALID_CATEGORIES = ["脱力系", "猫写真", "鋭い一言", "日常観察", "時事ネタ", "たまに有益", "猫Meme", "猫vs人間", "シュール猫", "未分類"]

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


def build_quote_analysis_summary(data: dict) -> str:
    """hook_performance.json から引用ツイートのみをカテゴリ別に集計"""
    from collections import defaultdict, Counter
    quotes = [p for p in data["posts"]
              if p.get("engagementFetchedAt")
              and p.get("tweet_type") == "quote"
              and p.get("hookCategory") not in ("未分類",)]
    if not quotes:
        return "引用ツイートデータなし"

    categories: dict = defaultdict(list)
    for post in quotes:
        categories[post.get("hookCategory", "未分類")].append(post)

    lines = [f"分析対象: 引用ツイート {len(quotes)}件\n"]
    for cat, posts in sorted(categories.items(),
                              key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
        n = len(posts)
        avg_imp = sum(p.get("impressions") or 0 for p in posts) / n
        avg_likes = sum(p.get("likes") or 0 for p in posts) / n
        diag = Counter(p.get("diagnosis", "DROP") for p in posts)
        recent = sorted(posts, key=lambda p: p.get("postedAt", ""), reverse=True)[:3]
        lines.append(f"【{cat}】{n}件 平均imp={avg_imp:.0f} 平均いいね={avg_likes:.1f}")
        lines.append(f"  診断: {dict(diag)}")
        for p in recent:
            lines.append(f"  - imp={p.get('impressions')} likes={p.get('likes')} 「{p['text'][:40]}」")
    return "\n".join(lines)


STRATEGY_FILE = SCRIPT_DIR.parent / "post_scheduler" / "strategy.json"
REPLY_LOG_FILE = SCRIPT_DIR.parent / "reply_system" / "reply_log.json"
REPLY_STRATEGY_FILE = SCRIPT_DIR.parent / "reply_system" / "reply_strategy.json"


def migrate_replies(data: dict) -> int:
    """hook_performance.json の hookCategory='リプライ' を reply_log.json のカテゴリで更新する"""
    if not REPLY_LOG_FILE.exists():
        print("[migrate] reply_log.json が見つかりません")
        return 0

    with open(REPLY_LOG_FILE, 'r', encoding='utf-8') as f:
        reply_log = json.load(f)

    # reply_log のテキスト → カテゴリ マッピング構築
    text_to_category = {}
    for entry in reply_log:
        if entry.get("status") == "posted" and entry.get("reply_text") and entry.get("category"):
            text_to_category[entry["reply_text"].strip()] = entry["category"]

    updated = 0
    for post in data["posts"]:
        if post.get("hookCategory") != "リプライ":
            continue
        text = (post.get("text") or "").strip()
        # hook_performance のテキストは "@username 本文" 形式なので、本文部分を抽出
        text_body = re.sub(r'^@\S+\s+', '', text)
        # 完全一致
        category = text_to_category.get(text_body)
        if not category:
            # reply_log のテキストが post.text に含まれるか
            for reply_text, cat in text_to_category.items():
                if reply_text and reply_text in text:
                    category = cat
                    break
        if category:
            post["hookCategory"] = category
            post["tweet_type"] = "reply"
            print(f"  [migrate] {category}: {text[:40]}...")
            updated += 1

    print(f"[migrate] 完了: {updated}件のリプライカテゴリを更新")
    return updated


def build_analysis_summary(data: dict) -> str:
    """hook_performance.json からテキスト形式の分析サマリーを生成する"""
    from collections import defaultdict
    fetched = [p for p in data["posts"] if p.get("engagementFetchedAt") and p.get("tweet_type") not in ("reply", "quote") and p.get("hookCategory") != "リプライ"]
    if not fetched:
        return "データなし"

    categories: dict = defaultdict(list)
    for post in fetched:
        categories[post.get("hookCategory", "未分類")].append(post)

    lines = [f"分析対象: 通常投稿 {len(fetched)}件（リプライ・引用除く）\n"]
    for cat, posts in sorted(categories.items(), key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
        n = len(posts)
        avg_imp = sum(p.get("impressions") or 0 for p in posts) / n
        avg_likes = sum(p.get("likes") or 0 for p in posts) / n
        from collections import Counter
        diag = Counter(p.get("diagnosis", "DROP") for p in posts)
        recent = sorted(posts, key=lambda p: p.get("postedAt", ""), reverse=True)[:3]
        lines.append(f"【{cat}】{n}件 平均imp={avg_imp:.0f} 平均いいね={avg_likes:.1f}")
        lines.append(f"  診断: {dict(diag)}")
        for p in recent:
            lines.append(f"  - imp={p.get('impressions')} likes={p.get('likes')} 「{p['text'][:40]}」")
    return "\n".join(lines)


def build_reply_analysis_summary(data: dict) -> str:
    """hook_performance.json からリプライのみをカテゴリ別に集計"""
    from collections import defaultdict, Counter
    replies = [p for p in data["posts"]
               if p.get("engagementFetchedAt")
               and p.get("tweet_type") == "reply"
               and p.get("hookCategory") not in ("リプライ", "未分類")]
    if not replies:
        return "リプライデータなし"

    categories: dict = defaultdict(list)
    for post in replies:
        categories[post.get("hookCategory", "未分類")].append(post)

    lines = [f"分析対象: リプライ {len(replies)}件\n"]
    for cat, posts in sorted(categories.items(),
                              key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
        n = len(posts)
        avg_imp = sum(p.get("impressions") or 0 for p in posts) / n
        avg_likes = sum(p.get("likes") or 0 for p in posts) / n
        diag = Counter(p.get("diagnosis", "DROP") for p in posts)
        recent = sorted(posts, key=lambda p: p.get("postedAt", ""), reverse=True)[:3]
        lines.append(f"【{cat}】{n}件 平均imp={avg_imp:.0f} 平均いいね={avg_likes:.1f}")
        lines.append(f"  診断: {dict(diag)}")
        for p in recent:
            lines.append(f"  - imp={p.get('impressions')} likes={p.get('likes')} 「{p['text'][:40]}」")
    return "\n".join(lines)


def run_act_reply(data: dict) -> None:
    """リプライデータを分析して reply_strategy.json を生成"""
    summary = build_reply_analysis_summary(data)
    if summary == "リプライデータなし":
        print("[act-reply] リプライデータなし。スキップ", flush=True)
        return

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""あなたはホッケ（茶トラ猫AIアカウント）のリプライ戦略アナリストです。
以下のリプライのエンゲージメントデータを分析し、今後のリプライ戦略をJSONで出力してください。

# 本日（{today}）のリプライパフォーマンスデータ
{summary}

# 出力形式（JSONのみ・説明不要）
{{
  "preferred_categories": ["カテゴリ名", ...],
  "avoid_categories": ["カテゴリ名", ...],
  "guidance": "具体的なリプライ指針（100字以内）",
  "reason": "戦略の根拠（50字以内）",
  "updated_at": "{today}"
}}

ルール:
- preferred_categories: エンゲージメントが高いリプライカテゴリを1〜3個
- avoid_categories: 反応が悪いカテゴリ（なければ空配列）
- guidance: ホッケのペルソナに沿った具体的なリプライの方向性
- カテゴリは検索キーワードのカテゴリ（猫系/脱力系/メンタル系/食べ物系 等）"""

    print("[act-reply] Claude でリプライ戦略を生成中...", flush=True)
    result = _call_claude(prompt, timeout=60)
    if not result:
        print("[act-reply] Claude 応答なし。スキップ", flush=True)
        return

    import re
    json_match = re.search(r'\{[\s\S]*\}', result)
    if not json_match:
        print(f"[act-reply] JSON が見つからない: {result[:100]}", flush=True)
        return

    try:
        strategy = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"[act-reply] JSON パース失敗: {e}", flush=True)
        return

    REPLY_STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPLY_STRATEGY_FILE, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)

    print(f"[act-reply] リプライ戦略を保存: {REPLY_STRATEGY_FILE}", flush=True)
    print(f"  優先: {strategy.get('preferred_categories')}", flush=True)
    print(f"  回避: {strategy.get('avoid_categories')}", flush=True)
    print(f"  指針: {strategy.get('guidance')}", flush=True)


def run_act(data: dict) -> None:
    """分析データを Claude に渡して戦略を生成し strategy.json に保存する"""
    summary = build_analysis_summary(data)
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""あなたはホッケ（茶トラ猫AIアカウント）の運用戦略アナリストです。
以下のエンゲージメントデータを分析し、明日以降の投稿戦略をJSONで出力してください。

# 本日（{today}）のパフォーマンスデータ
{summary}

# 出力形式（JSONのみ・説明不要）
{{
  "preferred_categories": ["カテゴリ名", ...],
  "avoid_categories": ["カテゴリ名", ...],
  "guidance": "具体的な投稿指針（100字以内）",
  "reason": "戦略の根拠（50字以内）",
  "updated_at": "{today}"
}}

ルール:
- preferred_categories: インプレッション・いいねが高いカテゴリを1〜3個
- avoid_categories: DROP が続いているカテゴリ（なければ空配列）
- guidance: ホッケのペルソナに沿った具体的な投稿の方向性
- カテゴリは 脱力系/猫写真/鋭い一言/日常観察/時事ネタ/たまに有益/猫Meme/猫vs人間/シュール猫 から選ぶ"""

    print("[act] Claude で戦略を生成中...", flush=True)
    result = _call_claude(prompt, timeout=60)
    if not result:
        print("[act] Claude 応答なし。スキップします", flush=True)
        return

    # JSON 抽出（マークダウンコードブロック対応）
    import re
    json_match = re.search(r'\{[\s\S]*\}', result)
    if not json_match:
        print(f"[act] JSON が見つからない: {result[:100]}", flush=True)
        return

    try:
        strategy = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"[act] JSON パース失敗: {e}", flush=True)
        return
    if not isinstance(strategy, dict):
        print(f"[act] JSON が dict でない: {type(strategy).__name__}", flush=True)
        return

    # 既存の非LLMフィールド（image_probability 等）を保持してマージ
    STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PRESERVE_KEYS = ("max_image_posts_per_day",)
    if STRATEGY_FILE.exists():
        try:
            with open(STRATEGY_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for k in _PRESERVE_KEYS:
                if k in existing and k not in strategy:
                    strategy[k] = existing[k]
        except (OSError, json.JSONDecodeError):
            pass
    with open(STRATEGY_FILE, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)

    print(f"[act] 戦略を保存: {STRATEGY_FILE}", flush=True)
    print(f"  優先: {strategy.get('preferred_categories')}", flush=True)
    print(f"  回避: {strategy.get('avoid_categories')}", flush=True)
    print(f"  指針: {strategy.get('guidance')}", flush=True)

    # Discord 通知
    try:
        preferred = " / ".join(strategy.get("preferred_categories") or [])
        avoid = " / ".join(strategy.get("avoid_categories") or []) or "なし"
        guidance = strategy.get("guidance", "")
        reason = strategy.get("reason", "")
        lines = [
            "**📊 ホッケ 日次エンゲージメント & 戦略レポート**",
            f"`date` {today}",
            "",
            "**カテゴリ別インプレッション（通常投稿）**",
        ]
        # カテゴリ集計を追加
        from collections import defaultdict
        posts = [p for p in data["posts"] if p.get("engagementFetchedAt") and p.get("tweet_type") not in ("reply", "quote") and p.get("hookCategory") not in ("リプライ", "未分類")]
        cats: dict = defaultdict(list)
        for p in posts:
            cats[p["hookCategory"]].append(p)
        for cat, ps in sorted(cats.items(), key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
            avg_imp = sum(p.get("impressions") or 0 for p in ps) / len(ps)
            lines.append(f"- `{cat}`: 平均imp {avg_imp:.0f} ({len(ps)}件)")
        lines += [
            "",
            "**📌 明日の投稿戦略**",
            f"優先: `{preferred}`",
            f"回避: `{avoid}`",
            f"指針: {guidance}",
            f"根拠: {reason}",
        ]
        # 引用ツイートセクション
        quote_posts = [p for p in data["posts"] if p.get("engagementFetchedAt") and p.get("tweet_type") == "quote" and p.get("hookCategory") not in ("未分類",)]
        if quote_posts:
            quote_cats: dict = defaultdict(list)
            for p in quote_posts:
                quote_cats[p["hookCategory"]].append(p)
            lines += ["", "**🔁 引用ツイート パフォーマンス**"]
            for cat, ps in sorted(quote_cats.items(), key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
                avg_imp = sum(p.get("impressions") or 0 for p in ps) / len(ps)
                avg_likes = sum(p.get("likes") or 0 for p in ps) / len(ps)
                lines.append(f"- `{cat}`: 平均imp {avg_imp:.0f} / 平均いいね {avg_likes:.1f} ({len(ps)}件)")
        # リプライ戦略もあれば追加
        if REPLY_STRATEGY_FILE.exists():
            try:
                with open(REPLY_STRATEGY_FILE, 'r', encoding='utf-8') as f:
                    rs = json.load(f)
                r_preferred = " / ".join(rs.get("preferred_categories") or [])
                r_avoid = " / ".join(rs.get("avoid_categories") or []) or "なし"
                r_guidance = rs.get("guidance", "")
                lines += [
                    "",
                    "**💬 リプライ戦略**",
                ]
                # リプライのカテゴリ別インプレッション
                reply_posts = [p for p in data["posts"] if p.get("engagementFetchedAt") and p.get("tweet_type") == "reply" and p.get("hookCategory") not in ("リプライ", "未分類")]
                reply_cats: dict = defaultdict(list)
                for p in reply_posts:
                    reply_cats[p["hookCategory"]].append(p)
                if reply_cats:
                    lines.append("**カテゴリ別インプレッション（リプライ）**")
                    for cat, ps in sorted(reply_cats.items(), key=lambda x: -(sum(p.get("impressions") or 0 for p in x[1]) / len(x[1]))):
                        avg_imp = sum(p.get("impressions") or 0 for p in ps) / len(ps)
                        lines.append(f"- `{cat}`: 平均imp {avg_imp:.0f} ({len(ps)}件)")
                    lines.append("")
                lines += [
                    f"優先: `{r_preferred}`",
                    f"回避: `{r_avoid}`",
                    f"指針: {r_guidance}",
                ]
            except Exception:
                pass
        message = "\n".join(lines)
        notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_POST")
        result = notifier.send(message, username="ホッケ戦略レポート")
        if result.ok:
            print("[act] Discord 通知送信成功", flush=True)
        else:
            print(f"[act] Discord 通知失敗: {result.error}", flush=True)
    except Exception as e:
        print(f"[act] Discord 通知エラー: {e}", flush=True)


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
    parser.add_argument(
        '--sync', action='store_true',
        help='タイムラインを取得してエンゲージメントを一括sync（通常投稿+リプライ）'
    )
    parser.add_argument(
        '--act', action='store_true',
        help='エンゲージメントデータを分析してClaude が戦略を生成し strategy.json に保存'
    )
    parser.add_argument(
        '--migrate-replies', action='store_true',
        help='hook_performance.json のリプライを reply_log.json のカテゴリで更新'
    )
    args = parser.parse_args()

    data = load_perf_data()

    if args.migrate_replies:
        migrate_replies(data)
        save_perf_data(data)
        return

    if args.recommend:
        print_recommend(data)
        return

    if args.sync:
        try:
            api_client = XApiClient(require_user_auth=True)
        except ValueError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
        sync_timeline(api_client, data)
        categorize_unknown_posts(data)
        save_perf_data(data)
        if args.act:
            run_act_reply(data)
            run_act(data)
        return

    if args.act:
        run_act_reply(data)
        run_act(data)
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
