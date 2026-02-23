#!/usr/bin/env python3
"""
ホッケ 自動投稿スクリプト
cronから実行。claude -p でツイートを生成してx_poster.pyで投稿する。
"""

import json
import subprocess
import sys
import re
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
PERSONA_FILE = PROJECT_DIR / "PERSONA.md"
PERFORMANCE_FILE = PROJECT_DIR / "hook_performance.json"
LOG_FILE = SCRIPT_DIR / "auto_post.log"
X_POSTER = SCRIPT_DIR / "x_poster.py"
STATE_FILE = SCRIPT_DIR / "auto_post_state.json"
STRATEGY_FILE = SCRIPT_DIR / "strategy.json"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    # Avoid duplicate lines when stdout is redirected to the same log file by cron.
    if getattr(sys.stdout, "isatty", lambda: False)():
        print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_drop_categories() -> list[str]:
    if not PERFORMANCE_FILE.exists():
        return []
    with open(PERFORMANCE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    drops = []
    for post in data.get("posts", []):
        if post.get("diagnosis") == "DROP":
            cat = post.get("hookCategory") or post.get("hook_category")
            if cat and cat not in drops:
                drops.append(cat)
    return drops


def _parse_posted_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            # Normalize to naive local time so old/new formats can be compared safely.
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _load_posts() -> list[dict]:
    if not PERFORMANCE_FILE.exists():
        return []
    with open(PERFORMANCE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("posts", [])


def _today_post_count(now: datetime) -> int:
    today = now.date().isoformat()
    return sum(
        1 for p in _load_posts()
        if str(p.get("postedAt", "")).startswith(today)
        and p.get("tweet_type") != "reply"
    )


def _last_post_at() -> datetime | None:
    latest = None
    for post in _load_posts():
        if post.get("tweet_type") == "reply":
            continue
        dt = _parse_posted_at(post.get("postedAt", ""))
        if not dt:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def decide_should_post(
    now: datetime,
    *,
    min_daily_posts: int,
    max_daily_posts: int,
    min_interval_minutes: int,
    run_interval_minutes: int,
) -> tuple[bool, str]:
    today = now.date().isoformat()
    state = _load_state()

    def _new_state() -> dict:
        return {"date": today, "target_today": random.randint(min_daily_posts, max_daily_posts)}

    state_needs_reset = False
    reset_reason = ""
    if state.get("date") != today:
        state_needs_reset = True
        reset_reason = "日付切替"
    else:
        try:
            target = int(state.get("target_today"))
            if target < min_daily_posts or target > max_daily_posts:
                state_needs_reset = True
                reset_reason = f"target_today={target} が範囲外 ({min_daily_posts}-{max_daily_posts})"
        except (TypeError, ValueError):
            state_needs_reset = True
            reset_reason = "target_today が不正値"

    if state_needs_reset:
        state = _new_state()
        _save_state(state)
        log(f"[gate] 状態を再初期化: {reset_reason}")
        log(f"[gate] 今日の目標投稿数: {state['target_today']}件")

    target_today = int(state.get("target_today", min_daily_posts))
    today_count = _today_post_count(now)
    if today_count >= max_daily_posts:
        return False, f"today_count={today_count} が daily_max={max_daily_posts} に到達"
    if today_count >= target_today:
        return False, f"today_count={today_count} が target_today={target_today} に到達"

    last_posted = _last_post_at()
    if last_posted:
        elapsed = now - last_posted
        min_interval = timedelta(minutes=min_interval_minutes)
        if elapsed < min_interval:
            return False, f"前回投稿から {int(elapsed.total_seconds() // 60)}分 (< {min_interval_minutes}分)"

    remain = target_today - today_count
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    seconds_left = max((day_end - now).total_seconds(), 0)
    slots_left = max(1, int(seconds_left // (run_interval_minutes * 60)) + 1)

    # If we are running out of slots, force post.
    if remain >= slots_left:
        return True, f"強制投稿 remain={remain} slots_left={slots_left}"

    probability = min(1.0, max(0.0, remain / slots_left))
    draw = random.random()
    should_post = draw < probability
    reason = (
        f"抽選 p={probability:.3f}, draw={draw:.3f}, "
        f"remain={remain}, slots_left={slots_left}, today_count={today_count}, target={target_today}"
    )
    return should_post, reason


def load_strategy() -> dict:
    if not STRATEGY_FILE.exists():
        return {}
    try:
        with open(STRATEGY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def build_prompt(persona: str, drop_categories: list[str]) -> str:
    strategy = load_strategy()
    preferred = strategy.get("preferred_categories", [])
    avoid = list(set(drop_categories + strategy.get("avoid_categories", [])))
    guidance = strategy.get("guidance", "")
    updated_at = strategy.get("updated_at", "")

    avoid_note = ""
    if avoid:
        avoid_note = f"\n\n【避けるカテゴリ】\n" + "\n".join(f"- {c}" for c in avoid)

    preferred_note = ""
    if preferred:
        preferred_note = f"\n\n【優先カテゴリ（直近パフォーマンス良好）】\n" + "\n".join(f"- {c}" for c in preferred)

    guidance_note = ""
    if guidance:
        guidance_note = f"\n\n【本日の投稿指針（{updated_at}更新）】\n{guidance}"

    return f"""あなたはホッケというチャトラ猫のXアカウントを運営している。
以下のペルソナに従い、今すぐ投稿するツイートを1件生成せよ。{avoid_note}{preferred_note}{guidance_note}

【ペルソナ定義】
{persona}

【出力形式】
以下のJSONのみ出力すること。説明・前置き・マークダウン記法は一切不要。

{{"text": "ツイート本文", "category": "カテゴリ名"}}

カテゴリは以下から選ぶこと: 脱力系 / 猫写真 / 鋭い一言 / 日常観察 / 時事ネタ / たまに有益

制約:
- 140字以内
- 一人称は「僕」か使わない（「俺」「私」NG）
- 「〜にゃ」NG
- 絵文字は0〜1個
- 短文・体言止め多め
- 意識高い発言・自己啓発・説教NG
"""


def generate_tweet(prompt: str) -> dict | None:
    try:
        result = subprocess.run(
            ["/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        log("ERROR: claude -p タイムアウト")
        return None
    except FileNotFoundError:
        log("ERROR: claude コマンドが見つからない")
        return None

    output = result.stdout.strip()
    if result.returncode != 0:
        log(f"ERROR: claude -p 失敗 (exit={result.returncode}): {result.stderr.strip()}")
        return None

    # JSON部分を抽出
    match = re.search(r'\{[^{}]+\}', output, re.DOTALL)
    if not match:
        log(f"ERROR: JSON抽出失敗。出力: {output[:200]}")
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        log(f"ERROR: JSONパース失敗: {e} / 出力: {output[:200]}")
        return None


def post_tweet(text: str, category: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, str(X_POSTER), "--text", text, "--hook-category", category],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        log("ERROR: x_poster.py タイムアウト")
        return False

    output = f"{result.stdout}\n{result.stderr}".strip()
    if output:
        log(output)

    return "投稿成功:" in output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ホッケ自動投稿")
    parser.add_argument("--auto-decide", action="store_true", help="確率ゲートで投稿可否を判定する")
    parser.add_argument("--min-daily-posts", type=int, default=4, help="1日の目標最小投稿数")
    parser.add_argument("--max-daily-posts", type=int, default=5, help="1日の目標最大投稿数")
    parser.add_argument("--min-interval-minutes", type=int, default=120, help="投稿間隔の最小分数")
    parser.add_argument("--run-interval-minutes", type=int, default=30, help="実行頻度（分）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log("=== auto_post 開始 ===")

    if args.min_daily_posts > args.max_daily_posts:
        log("ERROR: min_daily_posts は max_daily_posts 以下で指定してください")
        sys.exit(1)

    if args.auto_decide:
        should_post, reason = decide_should_post(
            datetime.now(),
            min_daily_posts=args.min_daily_posts,
            max_daily_posts=args.max_daily_posts,
            min_interval_minutes=args.min_interval_minutes,
            run_interval_minutes=args.run_interval_minutes,
        )
        log(f"[gate] {reason}")
        if not should_post:
            log("[gate] 今回は投稿しない")
            log("=== auto_post 完了（skip） ===")
            return

    if not PERSONA_FILE.exists():
        log(f"ERROR: PERSONA.md が見つからない: {PERSONA_FILE}")
        sys.exit(1)

    persona = PERSONA_FILE.read_text(encoding="utf-8")
    drops = get_drop_categories()
    if drops:
        log(f"DROP カテゴリ: {', '.join(drops)}")

    prompt = build_prompt(persona, drops)

    log("claude -p でツイート生成中...")
    tweet = generate_tweet(prompt)
    if not tweet:
        log("ERROR: ツイート生成失敗。終了。")
        sys.exit(1)

    text = tweet.get("text", "").strip()
    category = tweet.get("category", "未分類").strip()

    if not text:
        log("ERROR: textが空。終了。")
        sys.exit(1)

    log(f"生成: [{category}] {text}")

    ok = post_tweet(text, category)
    if ok:
        log("投稿成功")
    else:
        log("ERROR: 投稿失敗")
        sys.exit(1)

    log("=== auto_post 完了 ===")


if __name__ == "__main__":
    main()
