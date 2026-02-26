"""ホッケ運用データの読み込み・集計モジュール"""

import json
import math
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # hokke_x/

DATA_PATHS = {
    "hook_performance": BASE_DIR / "hook_performance.json",
    "strategy": BASE_DIR / "post_scheduler" / "strategy.json",
    "auto_post_state": BASE_DIR / "post_scheduler" / "auto_post_state.json",
    "auto_post_log": BASE_DIR / "post_scheduler" / "auto_post.log",
    "reply_log": BASE_DIR / "reply_system" / "reply_log.json",
    "reply_strategy": BASE_DIR / "reply_system" / "reply_strategy.json",
}

_SANITIZE_RE = re.compile(r"/[\w/.-]+")
_SECRET_RE = re.compile(
    r"""(?x)
    (?:                                          # キーワード
        token | key | secret | password |
        auth\w* | credential | bearer
    )
    \s*                                          # 任意の空白
    (?:                                          # 区切り文字パターン
        [=:]                                     #   key=val / key: val
      | "\s*:\s*"                                #   "token": "val" (JSON形式)
    )
    \s*"?                                        # 任意のクォート
    \S+(?:\s+\S+)?                               # 値
    """,
    re.IGNORECASE,
)


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_tail(path: Path, max_bytes: int = 64_000) -> str:
    """ファイル末尾を読む。ログ肥大時のメモリ/応答時間を抑える。"""
    try:
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # 途中の行を捨てる
            return f.read()
    except OSError:
        return ""


def load_auto_post_state() -> dict:
    data = _load_json(DATA_PATHS["auto_post_state"])
    if not isinstance(data, dict):
        return {"date": "不明", "target_today": 0, "consecutive_skips": 0}
    data["date"] = _ensure_str(data.get("date")) or "不明"
    data["target_today"] = int(_safe_number(data.get("target_today", 0)))
    data["consecutive_skips"] = int(_safe_number(data.get("consecutive_skips", 0)))
    return data


def _parse_perf_data(data: dict | list | None) -> list[dict]:
    if not isinstance(data, dict) or "posts" not in data:
        return []
    posts = data["posts"]
    if not isinstance(posts, list):
        return []
    return [p for p in posts if isinstance(p, dict)]


def _safe_number(val: object) -> int | float:
    """数値を安全に取り出す。非数値・NaN・inf・boolは0を返す。"""
    if isinstance(val, bool):
        return 0
    if isinstance(val, (int, float)) and math.isfinite(val):
        return val
    return 0


def _ensure_str(val: object) -> str:
    """文字列を保証する。None は空文字、非文字列は str() 変換。"""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return str(val)


def load_recent_posts(posts: list[dict], n: int = 10) -> list[dict]:
    result = []
    for p in posts[-n:]:
        p = dict(p)  # shallow copy
        for key in ("postedAt", "text"):
            p[key] = _ensure_str(p.get(key))
        for key in ("impressions", "likes"):
            raw = p.get(key)
            p[key] = _safe_number(raw) if raw is not None else None
        result.append(p)
    return result


def load_category_stats(posts: list[dict]) -> list[dict]:
    if not posts:
        return []

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for p in posts:
        cat = p.get("hookCategory", "不明")
        if not isinstance(cat, str):
            cat = "不明"
        by_cat[cat].append(p)

    stats = []
    for cat, cat_posts in sorted(by_cat.items()):
        imps = [_safe_number(p.get("impressions", 0)) for p in cat_posts]
        likes = [_safe_number(p.get("likes", 0)) for p in cat_posts]
        avg_imp = sum(imps) / len(imps) if imps else 0
        avg_likes = sum(likes) / len(likes) if likes else 0
        stats.append({
            "category": cat,
            "count": len(cat_posts),
            "avg_imp": round(avg_imp, 1),
            "avg_likes": round(avg_likes, 1),
        })
    stats.sort(key=lambda x: x["avg_imp"], reverse=True)
    return stats


def _normalize_strategy(data: dict | None, default_guidance: str = "データなし") -> dict:
    """戦略dictのフィールドを型正規化する。"""
    if not isinstance(data, dict):
        return {"preferred_categories": [], "avoid_categories": [], "guidance": default_guidance}
    for key in ("preferred_categories", "avoid_categories"):
        raw = data.get(key)
        if isinstance(raw, list):
            data[key] = [_ensure_str(x) for x in raw]
        else:
            data[key] = []
    data["guidance"] = _ensure_str(data.get("guidance")) or default_guidance
    return data


def load_strategy() -> dict:
    return _normalize_strategy(_load_json(DATA_PATHS["strategy"]))


def load_reply_strategy() -> dict:
    return _normalize_strategy(_load_json(DATA_PATHS["reply_strategy"]))


def load_reply_summary() -> dict:
    data = _load_json(DATA_PATHS["reply_log"])
    if not isinstance(data, list):
        return {"total": 0, "posted": 0, "posted_rate": 0, "recent": []}

    valid = [r for r in data if isinstance(r, dict)]
    total = len(valid)
    posted = sum(1 for r in valid if r.get("status") == "posted")
    rate = max(0.0, min(100.0, round(posted / total * 100, 1))) if total else 0.0
    recent_raw = valid[-5:]
    recent_raw.reverse()
    recent = []
    for r in recent_raw:
        r = dict(r)
        for key in ("reply_text", "date", "target_user", "category", "status"):
            r[key] = _ensure_str(r.get(key))
        recent.append(r)
    return {"total": total, "posted": posted, "posted_rate": rate, "recent": recent}


def _parse_log(log_text: str) -> tuple[list[str], str | None]:
    """ログテキストからエラー行と最終投稿時刻を抽出する。"""
    if not log_text:
        return [], None

    lines = log_text.strip().splitlines()[-200:]
    error_lines = []
    for l in lines:
        if re.search(r"(ERROR|Traceback|Error:)", l):
            sanitized = _SANITIZE_RE.sub("[path]", l)
            sanitized = _SECRET_RE.sub("[REDACTED]", sanitized)
            error_lines.append(sanitized)

    matches = re.findall(
        r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] 投稿成功",
        "\n".join(lines),
    )
    last_post = matches[-1] if matches else None

    return error_lines, last_post


def load_all_dashboard_data() -> dict:
    perf_data = _load_json(DATA_PATHS["hook_performance"])
    posts = _parse_perf_data(perf_data)

    log_text = _load_tail(DATA_PATHS["auto_post_log"])
    log_errors, last_post_time = _parse_log(log_text)

    return {
        "auto_post_state": load_auto_post_state(),
        "last_post_time": last_post_time,
        "recent_posts": load_recent_posts(posts, 10),
        "category_stats": load_category_stats(posts),
        "strategy": load_strategy(),
        "reply_strategy": load_reply_strategy(),
        "reply_summary": load_reply_summary(),
        "log_errors": log_errors,
    }
