#!/usr/bin/env python3
"""
ホッケ 自動投稿スクリプト
cronから実行。claude -p でツイートを生成してx_poster.pyで投稿する。
投稿判断・画像判断もLLMに委譲（ハードリミットで制約付き）。
"""

import fcntl
import json
import os
import subprocess
import sys
import re
import random
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import IO

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
PERSONA_FILE = PROJECT_DIR / "PERSONA.md"
PERFORMANCE_FILE = PROJECT_DIR / "hook_performance.json"
LOG_FILE = SCRIPT_DIR / "auto_post.log"
X_POSTER = SCRIPT_DIR / "x_poster.py"
STATE_FILE = SCRIPT_DIR / "auto_post_state.json"
STRATEGY_FILE = SCRIPT_DIR / "strategy.json"
IMAGE_TEMPLATES_FILE = SCRIPT_DIR / "image_templates.json"
LOCK_FILE = SCRIPT_DIR / "auto_post.lock"
GENERATE_IMAGE_SCRIPT = Path(
    os.path.expanduser(
        "~/.nvm/versions/node/v24.13.0/lib/node_modules/openclaw/skills/nano-banana-pro/scripts/generate_image.py"
    )
)
GEMINI_API_KEY_ENV_FILE = Path("/home/sekiz/pjt/x_auto/.env")

MAX_CONSECUTIVE_SKIPS = 4
SOFT_DEADLINE_HOUR = 20


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    # Avoid duplicate lines when stdout is redirected to the same log file by cron.
    if getattr(sys.stdout, "isatty", lambda: False)():
        print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
    try:
        with open(PERFORMANCE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log(f"[warn] hook_performance.json がdict以外: {type(data).__name__}")
            return []
        return data.get("posts", [])
    except (OSError, json.JSONDecodeError) as e:
        log(f"[warn] hook_performance.json 読み込み失敗: {e}")
        return []


def _today_post_count(now: datetime) -> int:
    today = now.date().isoformat()
    return sum(
        1 for p in _load_posts()
        if str(p.get("postedAt", "")).startswith(today)
        and p.get("tweet_type") != "reply"
    )


def _today_image_post_count(now: datetime) -> int:
    """今日の画像付き投稿数をカウント"""
    today = now.date().isoformat()
    return sum(
        1 for p in _load_posts()
        if str(p.get("postedAt", "")).startswith(today)
        and p.get("tweet_type") != "reply"
        and p.get("has_image") is True
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


# --- Lock file ---

def _acquire_lock() -> IO | None:
    """fcntl.flock による排他ロック。取得失敗時は None"""
    lock_fd = None
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (OSError, IOError):
        if lock_fd is not None:
            lock_fd.close()
        return None


def _release_lock(lock: IO) -> None:
    try:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    except (OSError, IOError):
        pass


# --- Consecutive skips management ---

def _increment_consecutive_skips() -> None:
    state = _load_state()
    state["consecutive_skips"] = state.get("consecutive_skips", 0) + 1
    _save_state(state)
    log(f"[skip] consecutive_skips={state['consecutive_skips']}")


def _reset_consecutive_skips() -> None:
    state = _load_state()
    if state.get("consecutive_skips", 0) > 0:
        state["consecutive_skips"] = 0
        _save_state(state)


# --- Hard gates ---

def check_hard_gates(
    now: datetime, *,
    min_daily_posts: int, max_daily_posts: int,
    min_interval_minutes: int, run_interval_minutes: int,
) -> tuple[str, dict]:
    """
    返り値: ("skip", info) / ("ask_llm", info) / ("force_post", info)
    info = {"remain", "slots_left", "target_today", "today_count",
            "last_posted_minutes_ago", "consecutive_skips"}
    """
    today = now.date().isoformat()
    state = _load_state()

    # State initialization / reset
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
        state = {
            "date": today,
            "target_today": random.randint(min_daily_posts, max_daily_posts),
            "consecutive_skips": 0,
        }
        _save_state(state)
        log(f"[gate] 状態を再初期化: {reset_reason}")
        log(f"[gate] 今日の目標投稿数: {state['target_today']}件")

    target_today = int(state.get("target_today", min_daily_posts))
    today_count = _today_post_count(now)
    consecutive_skips = state.get("consecutive_skips", 0)

    last_posted = _last_post_at()
    last_posted_minutes_ago = None
    if last_posted:
        last_posted_minutes_ago = int((now - last_posted).total_seconds() // 60)

    remain = max(0, target_today - today_count)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    seconds_left = max((day_end - now).total_seconds(), 0)
    slots_left = max(1, int(seconds_left // (run_interval_minutes * 60)) + 1)

    info = {
        "remain": remain,
        "slots_left": slots_left,
        "target_today": target_today,
        "today_count": today_count,
        "last_posted_minutes_ago": last_posted_minutes_ago,
        "consecutive_skips": consecutive_skips,
    }

    # 1. max_daily_posts 到達
    if today_count >= max_daily_posts:
        return "skip", {**info, "reason": f"daily_max到達 ({today_count}/{max_daily_posts})"}

    # 2. target_today 到達
    if today_count >= target_today:
        return "skip", {**info, "reason": f"target到達 ({today_count}/{target_today})"}

    # 3. min_interval 未経過
    if last_posted_minutes_ago is not None and last_posted_minutes_ago < min_interval_minutes:
        return "skip", {**info, "reason": f"間隔不足 ({last_posted_minutes_ago}分 < {min_interval_minutes}分)"}

    # 4. remain >= slots_left → 強制投稿
    if remain >= slots_left:
        return "force_post", {**info, "reason": f"スロット不足 remain={remain} slots={slots_left}"}

    # 5. consecutive_skips >= MAX
    if consecutive_skips >= MAX_CONSECUTIVE_SKIPS:
        return "force_post", {**info, "reason": f"連続スキップ上限 ({consecutive_skips}回)"}

    # 6. soft deadline 超過 かつ remain > 0
    if now.hour >= SOFT_DEADLINE_HOUR and remain > 0:
        return "force_post", {**info, "reason": f"soft_deadline超過 ({now.hour}時, remain={remain})"}

    # 7. それ以外 → LLMに判断委譲
    return "ask_llm", {**info, "reason": "LLM判断"}


# --- Image eligibility ---

def is_image_eligible(strategy: dict, now: datetime) -> bool:
    """日次上限チェックのみ。True なら LLM に判断を委ねる"""
    try:
        max_per_day = int(strategy.get("max_image_posts_per_day", 1))
    except (TypeError, ValueError):
        max_per_day = 1
    image_count_today = _today_image_post_count(now)
    return image_count_today < max_per_day


def _recent_post_texts(limit: int = 7) -> list[tuple[str, str]]:
    """直近の投稿(reply除く)からカテゴリとテキストを返す"""
    posts = [p for p in _load_posts() if p.get("tweet_type") != "reply"]
    posts.sort(key=lambda p: p.get("postedAt", ""), reverse=True)
    return [(p.get("hookCategory", ""), p.get("text", "")) for p in posts[:limit]]


def load_strategy() -> dict:
    if not STRATEGY_FILE.exists():
        return {}
    try:
        with open(STRATEGY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


# --- Timing context for LLM ---

def _build_timing_context(now: datetime, gate_info: dict, image_eligible: bool, *, run_interval_minutes: int = 30) -> str:
    """hook_performance.json から直近14日間のデータを集計し、LLMに渡す構造化コンテキストを返す"""
    lines = []

    # 現在の状況
    remain = gate_info["remain"]
    slots_left = gate_info["slots_left"]
    today_count = gate_info["today_count"]
    target_today = gate_info["target_today"]
    last_min = gate_info["last_posted_minutes_ago"]

    lines.append("【現在の状況】")
    lines.append(f"- 現在時刻: {now.strftime('%H:%M')} (JST)")
    lines.append(f"- 今日の投稿: {today_count}/{target_today}件済み（残り{remain}件）")
    if last_min is not None:
        last_h = last_min // 60
        last_m = last_min % 60
        if last_h > 0:
            lines.append(f"- 最後の投稿: {last_h}時間{last_m}分前")
        else:
            lines.append(f"- 最後の投稿: {last_m}分前")
    else:
        lines.append("- 最後の投稿: 今日はまだなし")

    # 残りスロット列挙
    interval = run_interval_minutes
    slot_times = []
    remainder = now.minute % interval
    t = now + timedelta(minutes=interval - remainder if remainder else interval)
    today = now.date()
    while t.date() == today and t.hour <= 23:
        slot_times.append(t.strftime("%H:%M"))
        t += timedelta(minutes=interval)
    if slot_times:
        lines.append(f"- 残りの実行スロット: {', '.join(slot_times[:10])}{'...' if len(slot_times) > 10 else ''}（{slots_left}スロット）")

    # 画像枠
    if image_eligible:
        lines.append("- 画像枠: あり（LLMが判断可能）")
    else:
        lines.append("- 画像枠: なし（日次上限到達）")

    # 直近14日間のパフォーマンスデータ
    posts = _load_posts()
    cutoff = (now - timedelta(days=14)).isoformat()
    recent_posts = [
        p for p in posts
        if p.get("engagementFetchedAt")
        and p.get("tweet_type") != "reply"
        and p.get("hookCategory") not in ("リプライ", "未分類")
        and str(p.get("postedAt", "")) >= cutoff
    ]

    if recent_posts:
        # 時間帯別パフォーマンス
        from collections import defaultdict
        hour_stats: dict[int, list[int]] = defaultdict(list)
        for p in recent_posts:
            posted_at = _parse_posted_at(p.get("postedAt", ""))
            if posted_at:
                imp = p.get("impressions") or 0
                hour_stats[posted_at.hour].append(imp)

        if hour_stats:
            lines.append("")
            lines.append("【時間帯別パフォーマンス（直近14日）】")
            # imp平均でソート（降順）
            sorted_hours = sorted(
                hour_stats.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True,
            )
            for hour, imps in sorted_hours:
                avg = sum(imps) / len(imps)
                n = len(imps)
                note = ""
                if n <= 2:
                    note = "データ少"
                elif avg >= 30:
                    note = "好調"
                elif avg < 15:
                    note = "低調"
                marker = " ← 現在" if hour == now.hour else ""
                lines.append(f"- {hour:02d}時台: avg imp {avg:.0f} (n={n}{', ' + note if note else ''}){marker}")

        # カテゴリ別パフォーマンス
        cat_stats: dict[str, list[int]] = defaultdict(list)
        for p in recent_posts:
            cat = p.get("hookCategory", "未分類")
            imp = p.get("impressions") or 0
            cat_stats[cat].append(imp)

        if cat_stats:
            lines.append("")
            lines.append("【カテゴリ別パフォーマンス（直近14日）】")
            sorted_cats = sorted(
                cat_stats.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True,
            )
            for cat, imps in sorted_cats:
                avg = sum(imps) / len(imps)
                n = len(imps)
                lines.append(f"- {cat}: avg imp {avg:.0f} (n={n})")

    return "\n".join(lines)


# --- Image pipeline helpers ---

def _load_image_templates() -> dict | None:
    """image_templates.json を読み込む。失敗時は None"""
    if not IMAGE_TEMPLATES_FILE.exists():
        log("[image] image_templates.json が見つからない")
        return None
    try:
        with open(IMAGE_TEMPLATES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log(f"[image] image_templates.json 読み込み失敗: {e}")
        return None


def _customize_template(template_prompt: dict, image_hint: str | None) -> dict:
    """LLM が返した image_hint でテンプレートの特定フィールドを差し替える"""
    if not image_hint:
        return template_prompt

    prompt = dict(template_prompt)

    # Meme系: text_overlay を差し替え
    if "text_overlay" in prompt:
        prompt["text_overlay"] = f"Bold white text with black outline: \"{image_hint}\""
    else:
        # 非Meme系: action フィールドを拡張
        prompt["action"] = f"{prompt.get('action', '')}. Context hint: {image_hint}"

    return prompt


def _image_hook_category(image_category: str, text_category: str) -> str:
    """画像カテゴリに基づいて hookCategory を決定"""
    templates_data = _load_image_templates()
    if templates_data:
        mapping = templates_data.get("image_category_to_hook_category", {})
        if image_category in mapping:
            return mapping[image_category]
    return text_category


def _get_gemini_api_key() -> str | None:
    """GEMINI_API_KEY を環境変数 or .env ファイルから取得"""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if GEMINI_API_KEY_ENV_FILE.exists():
        try:
            for line in GEMINI_API_KEY_ENV_FILE.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
    return None


def generate_image(image_category: str, image_hint: str | None) -> str | None:
    """Nano Banana Pro で画像生成。成功時はファイルパスを返す。失敗時は None"""
    # プリフライトチェック
    if not GENERATE_IMAGE_SCRIPT.exists():
        log(f"[image] generate_image.py が見つからない: {GENERATE_IMAGE_SCRIPT}")
        return None

    gemini_key = _get_gemini_api_key()
    if not gemini_key:
        log("[image] GEMINI_API_KEY が見つからない")
        return None

    templates_data = _load_image_templates()
    if not templates_data:
        return None

    template = templates_data.get("templates", {}).get(image_category)
    if not template:
        log(f"[image] テンプレート '{image_category}' が見つからない")
        return None

    # テンプレートのプロンプトをカスタマイズ
    prompt_dict = _customize_template(template["prompt"], image_hint)
    prompt_json = json.dumps(prompt_dict, ensure_ascii=False)

    filename = datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + f"-hokke-{image_category.lower()}.png"

    log(f"[image] 画像生成開始: category={image_category}, hint={image_hint}")

    env = os.environ.copy()
    env["GEMINI_API_KEY"] = gemini_key

    try:
        result = subprocess.run(
            [
                "uv", "run", str(GENERATE_IMAGE_SCRIPT),
                "--prompt", prompt_json,
                "--filename", filename,
                "--resolution", "2K",
            ],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired:
        log("[image] generate_image.py タイムアウト (90s)")
        return None
    except FileNotFoundError:
        log("[image] uv コマンドが見つからない")
        return None

    output = result.stdout.strip()
    if result.returncode != 0:
        log(f"[image] 生成失敗 (exit={result.returncode}): {result.stderr.strip()[:200]}")
        return None

    # MEDIA: 行からファイルパスを抽出
    for line in output.splitlines():
        if line.startswith("MEDIA:"):
            image_path = line.split("MEDIA:", 1)[1].strip()
            if Path(image_path).exists():
                log(f"[image] 生成成功: {image_path}")
                _log_image_cost(image_category)
                return image_path
            else:
                log(f"[image] 出力ファイルが見つからない: {image_path}")
                return None

    log(f"[image] MEDIA行が見つからない。出力: {output[:200]}")
    return None


def _log_image_cost(image_category: str) -> None:
    """画像生成コストをログに記録"""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from cost_logger import log_api_usage
        log_api_usage(
            "image_generate",
            units=1,
            endpoint="gemini/nano-banana-pro",
            context="auto_post.generate_image",
            metadata={"image_category": image_category},
        )
    except Exception as e:
        log(f"[image] コストログ記録失敗（無視）: {e}")


# --- Prompt building ---

def build_prompt(
    persona: str, *,
    strategy: dict,
    timing_context: str,
    allow_skip: bool,
    image_eligible: bool,
    force_image: bool,
) -> str:
    preferred = strategy.get("preferred_categories", [])
    avoid = strategy.get("avoid_categories", [])
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

    recent_note = ""
    recent = _recent_post_texts()
    if recent:
        lines = [f"- [{cat or '未分類'}] {txt}" for cat, txt in recent]
        recent_note = "\n\n【直近の投稿（同じテーマ・同じ切り口は避け、別の話題にすること）】\n" + "\n".join(lines)

    # タイミングコンテキスト
    timing_block = f"\n\n{timing_context}"

    # 投稿判断ブロック
    skip_block = ""
    if allow_skip:
        skip_block = """

【投稿判断】
以下を踏まえ、今投稿すべきかを判断せよ。
- 残り投稿数と残りスロット数のバランス
- 現在の時間帯のパフォーマンス傾向
- ゴールデンタイム（21-23時）に温存すべきか、今消化すべきか
投稿しない場合: {"post_now": false, "reason": "理由"} のみ出力。
投稿する場合: 以下の出力形式に従う。"""

    # 画像判断ブロック
    image_block = ""
    if force_image:
        image_block = """

【画像付き投稿モード（強制）】
今回は画像を必ず付けよ。以下を追加で出力すること:
- "image_category": 画像カテゴリを A〜G から1つ選ぶ
  - A: 窓際・室内（まったり日常）
  - B: 脱力コント（飼い主の机周り・生活感）
  - C: 北海道の光と季節感（冬）
  - D: 夏（北海道の短い夏）
  - E: 猫Meme（共感・あるある系。英語の短いフレーズ付き）
  - F: 猫 vs 人間（対比・比較の分割構図）
  - G: シュール猫（猫が人間っぽいことをしている）
- "image_hint": 画像のカスタマイズヒント（Eの場合は英語テキスト例: "Monday.", それ以外は状況描写）

テキストと画像が補完し合うように。テキストで画像の説明はしない（見ればわかるので）。"""
    elif image_eligible:
        image_block = """

【画像オプション】
画像を付けるかは自分で判断せよ。判断基準:
- テキストだけで十分な鋭い一言・皮肉 → 画像不要
- 情景描写・脱力系・共感ネタ → 画像で効果アップ
- 1日の画像枠は貴重。最も効果的なタイミングで使え
画像を付ける場合のみ以下を追加で出力:
- "image_category": 画像カテゴリを A〜G から1つ選ぶ
  - A: 窓際・室内（まったり日常）
  - B: 脱力コント（飼い主の机周り・生活感）
  - C: 北海道の光と季節感（冬）
  - D: 夏（北海道の短い夏）
  - E: 猫Meme（共感・あるある系。英語の短いフレーズ付き）
  - F: 猫 vs 人間（対比・比較の分割構図）
  - G: シュール猫（猫が人間っぽいことをしている）
- "image_hint": 画像のカスタマイズヒント（Eの場合は英語テキスト例: "Monday.", それ以外は状況描写）

テキストと画像が補完し合うように。テキストで画像の説明はしない（見ればわかるので）。"""

    # 探索予算（force_post 時は除外 = allow_skip=False かつ force ケース）
    explore_block = ""
    if allow_skip:
        explore_block = """

【探索】
5回に1回程度、普段と違うカテゴリ・切り口を試せ。
ただしスロット残り僅かの場合は安全な選択をすること。"""

    # 出力形式
    has_image_option = force_image or image_eligible
    if allow_skip:
        output_format = """以下のJSONのみ出力すること。説明・前置き・マークダウン記法は一切不要。

投稿する場合:
{"post_now": true, "text": "ツイート本文", "category": "カテゴリ名"}
"""
        if has_image_option:
            output_format += """画像付きの場合:
{"post_now": true, "text": "ツイート本文", "category": "カテゴリ名", "image_category": "E", "image_hint": "Monday."}
"""
        output_format += """投稿しない場合:
{"post_now": false, "reason": "理由"}"""
    else:
        output_format = '{"text": "ツイート本文", "category": "カテゴリ名"}'
        if has_image_option:
            output_format += '\n画像付きの場合:\n{"text": "ツイート本文", "category": "カテゴリ名", "image_category": "E", "image_hint": "Monday."}'

    categories = "脱力系 / 猫写真 / 鋭い一言 / 日常観察 / 時事ネタ / たまに有益"
    if has_image_option:
        categories += " / 猫Meme / 猫vs人間 / シュール猫"

    return f"""あなたはホッケというチャトラ猫のXアカウントを運営している。
以下のペルソナに従い、ツイートを生成せよ。{avoid_note}{preferred_note}{guidance_note}{recent_note}{timing_block}{skip_block}{image_block}{explore_block}

【ペルソナ定義】
{persona}

【出力形式】
{output_format}

カテゴリは以下から選ぶこと: {categories}

制約:
- 140字以内
- 一人称は「僕」か使わない（「俺」「私」NG）
- 「〜にゃ」NG
- 絵文字は0〜1個
- 短文・体言止め多め
- 意識高い発言・自己啓発・説教NG
"""


def generate_tweet(prompt: str) -> dict | None:
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            ["/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        latency = time.monotonic() - t0
        log(f"ERROR: claude -p タイムアウト (latency={latency:.1f}s)")
        return None
    except FileNotFoundError:
        log("ERROR: claude コマンドが見つからない")
        return None

    latency = time.monotonic() - t0
    output = result.stdout.strip()
    if result.returncode != 0:
        log(f"ERROR: claude -p 失敗 (exit={result.returncode}, latency={latency:.1f}s): {result.stderr.strip()}")
        return None

    # JSON部分を抽出（フラットなオブジェクトのみ対応）
    match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
    if not match:
        log(f"ERROR: JSON抽出失敗 (parse_success=false, latency={latency:.1f}s)。出力: {output[:200]}")
        return None

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError as e:
        log(f"ERROR: JSONパース失敗 (parse_success=false, latency={latency:.1f}s): {e} / 出力: {output[:200]}")
        return None

    # post_now フィールド対応
    post_now = parsed.get("post_now", True)
    if post_now is False:
        reason = parsed.get("reason", "理由なし")
        log(f"[llm] post_now=false, reason=\"{reason}\", latency={latency:.1f}s")
        return None

    # text は投稿時に必須
    if not parsed.get("text"):
        log(f"ERROR: text が空 (latency={latency:.1f}s)。パース結果: {parsed}")
        return None

    # ログ出力
    category = parsed.get("category", "未分類")
    image_cat = parsed.get("image_category", "")
    log(f"[llm] post_now=true, category={category}, image={'true(' + image_cat + ')' if image_cat else 'false'}, latency={latency:.1f}s")

    return parsed


def post_tweet(text: str, category: str, image_path: str | None = None) -> bool:
    cmd = [sys.executable, str(X_POSTER), "--text", text, "--hook-category", category]
    if image_path:
        cmd.extend(["--image", image_path])

    try:
        result = subprocess.run(
            cmd,
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

    return "投稿成功:" in output or "画像付き投稿成功:" in output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ホッケ自動投稿")
    parser.add_argument("--auto-decide", action="store_true", help="LLMにスキップ判断を許可する")
    parser.add_argument("--min-daily-posts", type=int, default=4, help="1日の目標最小投稿数")
    parser.add_argument("--max-daily-posts", type=int, default=5, help="1日の目標最大投稿数")
    parser.add_argument("--min-interval-minutes", type=int, default=120, help="投稿間隔の最小分数")
    parser.add_argument("--run-interval-minutes", type=int, default=30, help="実行頻度（分）")
    parser.add_argument("--force-image", action="store_true", help="画像付き投稿を強制（手動テスト用。日次上限は遵守）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log("=== auto_post 開始 ===")

    if args.min_daily_posts > args.max_daily_posts:
        log("ERROR: min_daily_posts は max_daily_posts 以下で指定してください")
        sys.exit(1)

    if args.run_interval_minutes <= 0:
        log("ERROR: run_interval_minutes は1以上で指定してください")
        sys.exit(1)

    now = datetime.now()

    # 0. ロックファイル（cron重複実行防止）
    lock = _acquire_lock()
    if not lock:
        log("[lock] 別プロセス実行中。スキップ。")
        return

    try:
        # 1. ハードゲート
        gate_result, gate_info = check_hard_gates(
            now,
            min_daily_posts=args.min_daily_posts,
            max_daily_posts=args.max_daily_posts,
            min_interval_minutes=args.min_interval_minutes,
            run_interval_minutes=args.run_interval_minutes,
        )
        log(f"[gate] {gate_result}: {gate_info.get('reason', '')}")
        if gate_result == "skip":
            log("=== auto_post 完了（skip） ===")
            return

        # 2. コンテキスト構築
        if not PERSONA_FILE.exists():
            log(f"ERROR: PERSONA.md が見つからない: {PERSONA_FILE}")
            sys.exit(1)

        strategy = load_strategy()
        if strategy:
            log(f"[strategy] 優先: {strategy.get('preferred_categories', [])}, 回避: {strategy.get('avoid_categories', [])}")

        image_eligible = is_image_eligible(strategy, now)
        if args.force_image and not image_eligible:
            log("[image-gate] --force-image だが日次上限到達。画像なしで続行。")
        force_image = args.force_image and image_eligible

        allow_skip = (args.auto_decide and gate_result != "force_post")
        timing_ctx = _build_timing_context(now, gate_info, image_eligible, run_interval_minutes=args.run_interval_minutes)

        log(f"[context] gate={gate_result}, allow_skip={allow_skip}, image_eligible={image_eligible}, force_image={force_image}")

        # 3. プロンプト構築 & LLM呼び出し（1回で全決定）
        persona = PERSONA_FILE.read_text(encoding="utf-8")
        prompt = build_prompt(
            persona,
            strategy=strategy,
            timing_context=timing_ctx,
            allow_skip=allow_skip,
            image_eligible=image_eligible,
            force_image=force_image,
        )

        log("claude -p でツイート生成中...")
        tweet = generate_tweet(prompt)

        if not tweet:
            # LLMスキップ or パース失敗
            _increment_consecutive_skips()
            log("=== auto_post 完了（LLMスキップ） ===")
            return

        text = tweet["text"].strip()
        category = tweet.get("category", "未分類").strip()

        if not text:
            log("ERROR: textが空。終了。")
            _increment_consecutive_skips()
            return

        # 4. 画像生成（LLMが判断した場合のみ）
        image_path = None
        image_category = tweet.get("image_category", "").strip()

        if image_category and image_eligible:
            image_hint = tweet.get("image_hint", "").strip() or None
            log(f"[image] カテゴリ={image_category}, ヒント={image_hint}")
            image_path = generate_image(image_category, image_hint)
            if image_path:
                category = _image_hook_category(image_category, category)
            else:
                log("[image] 画像生成失敗 → テキストのみで投稿")
        elif image_category and not image_eligible:
            log("[image] LLMが画像を選択したが日次上限到達 → テキストのみで投稿")

        log(f"生成: [{category}] {text}" + (f" [画像: {image_path}]" if image_path else ""))

        # 5. 投稿
        ok = post_tweet(text, category, image_path)
        if ok:
            # 6. 投稿成功時のみ consecutive_skips リセット
            _reset_consecutive_skips()
            log("投稿成功")
        else:
            _increment_consecutive_skips()
            log("ERROR: 投稿失敗")
            sys.exit(1)

        log("=== auto_post 完了 ===")
    finally:
        _release_lock(lock)


if __name__ == "__main__":
    main()
