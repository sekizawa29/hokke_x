#!/usr/bin/env python3
"""
WSL側オーケストレーター: candidates.json を読み込み、
各候補について python.exe win_autogui.py を呼び出してブラウザリプライを自動化する。

Usage:
    python3 orchestrator.py [--dry-run] [--limit 5] [--confirm-each] [--no-confirm]
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPLY_SYSTEM_DIR = SCRIPT_DIR.parent
PROJECT_DIR = REPLY_SYSTEM_DIR.parent
CANDIDATES_FILE = PROJECT_DIR / "dashboard" / "reply_candidates.json"
CONFIG_FILE = SCRIPT_DIR / "config.json"
LOG_FILE = SCRIPT_DIR / "session_log.json"
# reply_log.json スキーマ契約:
#   各エントリは {"target_tweet_id": str, "status": "posted"|"dry_run"|...} を持つ。
#   重複排除は status=="posted" かつ target_tweet_id で判定する。
REPLY_LOG_FILE = REPLY_SYSTEM_DIR / "reply_log.json"

# win_autogui.py の Windows パスを取得
WIN_AUTOGUI_WSL = SCRIPT_DIR / "win_autogui.py"


DEFAULTS = {
    "delay_min_sec": 30,
    "delay_max_sec": 60,
    "page_load_wait_min": 4.0,
    "page_load_wait_max": 6.0,
    "max_per_session": 10,
    "confirm_each": False,
}


def load_config() -> dict:
    """設定ファイルを読み込む"""
    if not CONFIG_FILE.exists():
        return dict(DEFAULTS)
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {**DEFAULTS, **config}
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: config.json 読み込みエラー（デフォルト値使用）: {e}")
        return dict(DEFAULTS)


def load_candidates() -> list[dict]:
    """候補JSONを読み込む"""
    if not CANDIDATES_FILE.exists():
        print(f"ERROR: {CANDIDATES_FILE} が見つかりません", file=sys.stderr)
        print("  先に generate_reply_dashboard.py を実行してください", file=sys.stderr)
        sys.exit(1)

    try:
        candidates = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: {CANDIDATES_FILE} の読み込み失敗: {e}", file=sys.stderr)
        sys.exit(1)

    if not candidates:
        print("候補が0件です")
        sys.exit(0)

    return candidates


def wsl_to_win_path(wsl_path: str) -> str:
    """WSLパスをWindowsパスに変換"""
    result = subprocess.run(
        ["wslpath", "-w", wsl_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"wslpath 変換失敗: {wsl_path} → {result.stderr.strip()}")
    return result.stdout.strip()


def run_autogui(url: str, text: str, dry_run: bool, config: dict) -> dict:
    """python.exe で win_autogui.py を実行"""
    try:
        win_script_path = wsl_to_win_path(str(WIN_AUTOGUI_WSL))
    except RuntimeError as e:
        print(f"    [ERROR] {e}")
        return {"returncode": -1, "stdout": "", "stderr": str(e)}

    cmd = [
        "/mnt/c/Users/sekiz/AppData/Local/Programs/Python/Python310/python.exe",
        win_script_path,
        "--url", url,
        "--text", text,
        "--page-load-min", str(config.get("page_load_wait_min", 4.0)),
        "--page-load-max", str(config.get("page_load_wait_max", 6.0)),
        "--confidence", str(config.get("confidence", 0.8)),
    ]
    chrome_profile = config.get("chrome_profile")
    if chrome_profile:
        cmd.extend(["--chrome-profile", chrome_profile])
    if dry_run:
        cmd.append("--dry-run")

    print(f"  実行: python.exe win_autogui.py {'--dry-run' if dry_run else ''}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        # 出力を表示
        if stdout.strip():
            for line in stdout.strip().split("\n"):
                print(f"    {line}")
        if stderr.strip():
            for line in stderr.strip().split("\n"):
                print(f"    [ERR] {line}")

        return {
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        print("    [TIMEOUT] 120秒タイムアウト")
        return {"returncode": -1, "stdout": "", "stderr": "timeout"}
    except Exception as e:
        print(f"    [ERROR] {e}")
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


MAX_LOG_ENTRIES = 500


def _load_log_entries() -> list[dict]:
    """session_log.json を安全に読み込む"""
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError):
        return []


def _load_reply_log_ids() -> set[str]:
    """reply_engine.py のログ (reply_log.json) から投稿済み tweet_id を収集"""
    if not REPLY_LOG_FILE.exists():
        return set()
    try:
        data = json.loads(REPLY_LOG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return set()
    except (json.JSONDecodeError, OSError):
        return set()
    return {
        e.get("target_tweet_id", "")
        for e in data
        if e.get("status") == "posted"
    } - {""}


def load_replied_ids() -> set[str]:
    """全ログソースから返信済み tweet_id を収集する"""
    # browser_automation の session_log.json
    from_session = {
        e.get("tweet_id", "")
        for e in _load_log_entries()
        if e.get("status") == "success" and not e.get("dry_run")
    } - {""}
    # reply_engine.py の reply_log.json
    from_reply_log = _load_reply_log_ids()
    return from_session | from_reply_log


def save_log(log_entries: list[dict]):
    """セッションログを蓄積保存（既存ログにマージ、上限超過時は古い順に削除）"""
    existing = _load_log_entries()
    merged = existing + log_entries
    # 上限を超えたら古いエントリを削除
    if len(merged) > MAX_LOG_ENTRIES:
        merged = merged[-MAX_LOG_ENTRIES:]
    LOG_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="ブラウザリプライ自動化オーケストレーター")
    parser.add_argument("--dry-run", action="store_true", help="全候補をdry-runで処理")
    parser.add_argument("--limit", type=int, default=None, help="最大処理件数")
    parser.add_argument("--confirm-each", action="store_true", default=None,
                        help="各候補の前に確認プロンプト (デフォルト: config依存)")
    parser.add_argument("--no-confirm", action="store_true", help="確認プロンプトなし")
    args = parser.parse_args()

    config = load_config()
    candidates = load_candidates()

    # 返信済み & 候補内重複を除外
    replied_ids = load_replied_ids()
    seen: set[str] = set()
    unique_candidates = []
    for c in candidates:
        tid = c.get("tweet_id", "")
        if tid and tid not in replied_ids and tid not in seen:
            seen.add(tid)
            unique_candidates.append(c)
    skipped_dupes = len(candidates) - len(unique_candidates)
    # 古い順にソート（generated_at がないものは最優先＝最古扱い）
    unique_candidates.sort(key=lambda c: c.get("generated_at", ""))
    candidates = unique_candidates
    if skipped_dupes:
        print(f"  重複/返信済み除外: {skipped_dupes}件")

    # confirm_each の決定
    if args.no_confirm:
        confirm_each = False
    elif args.confirm_each is not None:
        confirm_each = args.confirm_each
    else:
        confirm_each = config.get("confirm_each", True)

    # 処理上限
    if args.limit is not None:
        max_count = max(0, args.limit)
    else:
        max_count = config.get("max_per_session", 10)
    targets = candidates[:max_count]

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"=== ブラウザリプライ自動化 [{mode}] ===")
    print(f"  候補: {len(candidates)}件 → 処理: {len(targets)}件")
    print(f"  確認: {'あり' if confirm_each else 'なし'}")
    print(f"  待機: {config.get('delay_min_sec', 30)}-{config.get('delay_max_sec', 60)}秒")
    print()

    log_entries = []
    success = 0
    skipped = 0
    failed = 0

    for i, candidate in enumerate(targets):
        username = candidate.get("username", "?")
        tweet_id = candidate.get("tweet_id", "")
        reply_text = candidate.get("reply_text", "")
        tweet_text = candidate.get("tweet_text", "")
        category = candidate.get("category", "")
        url = f"https://x.com/{username}/status/{tweet_id}"

        print(f"--- [{i+1}/{len(targets)}] @{username} ---")
        print(f"  元ツイート: {tweet_text[:80]}...")
        print(f"  リプライ: {reply_text[:80]}...")

        if confirm_each:
            try:
                answer = input("  実行しますか? [Y/n/q] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n中断されました")
                break
            if answer == "q":
                print("  中断")
                break
            if answer == "n":
                print("  スキップ")
                skipped += 1
                log_entries.append({
                    "username": username,
                    "tweet_id": tweet_id,
                    "status": "skipped",
                    "timestamp": datetime.now().isoformat(),
                })
                continue

        result = run_autogui(url, reply_text, args.dry_run, config)

        entry = {
            "username": username,
            "tweet_id": tweet_id,
            "reply_text": reply_text,
            "category": category,
            "dry_run": args.dry_run,
            "returncode": result["returncode"],
            "timestamp": datetime.now().isoformat(),
        }

        if result["returncode"] == 0:
            entry["status"] = "success"
            success += 1
            replied_ids.add(tweet_id)
        else:
            entry["status"] = "failed"
            failed += 1

        log_entries.append(entry)

        # 次の候補まで待機（最後の候補以外）
        if i < len(targets) - 1:
            delay_min = max(0, config.get("delay_min_sec", 30))
            delay_max = max(delay_min, config.get("delay_max_sec", 60))
            delay = random.uniform(delay_min, delay_max)
            print(f"  次の候補まで {delay:.0f}秒待機...")
            time.sleep(delay)

    # ログ保存
    save_log(log_entries)

    # candidates.json からリプ済み分を削除して書き戻し
    if success > 0:
        try:
            all_candidates = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
            remaining = [c for c in all_candidates if c.get("tweet_id", "") not in replied_ids]
            CANDIDATES_FILE.write_text(
                json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  候補更新: {len(all_candidates)} → {len(remaining)}件")
        except (json.JSONDecodeError, OSError):
            pass

    # サマリー
    print()
    print(f"=== 完了 ===")
    print(f"  成功: {success}件")
    print(f"  スキップ: {skipped}件")
    print(f"  失敗: {failed}件")
    print(f"  残り候補: {len(remaining) if success > 0 else len(candidates)}件")
    print(f"  ログ: {LOG_FILE}")


if __name__ == "__main__":
    main()
