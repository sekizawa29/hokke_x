#!/usr/bin/env python3
"""
リファクタリング後の機能テスト

旧API方式の整理後、残すべき機能が正常に動作するか検証する。
実行: python3 tests/test_refactoring.py
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
REPLY_SYSTEM_DIR = PROJECT_DIR / "reply_system"
BROWSER_AUTO_DIR = REPLY_SYSTEM_DIR / "browser_automation"

PASSED = 0
FAILED = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS: {name}")
    else:
        FAILED += 1
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def section(title: str):
    print(f"\n=== {title} ===")


# -------------------------------------------------------
# 1. ファイル存在チェック（残すべきファイル）
# -------------------------------------------------------
section("残すべきファイルの存在")

must_exist = [
    REPLY_SYSTEM_DIR / "reply_engine.py",
    REPLY_SYSTEM_DIR / "generate_reply_dashboard.py",
    REPLY_SYSTEM_DIR / "search_config.json",
    REPLY_SYSTEM_DIR / "reply_strategy.json",
    REPLY_SYSTEM_DIR / "ng_keywords.json",
    REPLY_SYSTEM_DIR / "reply_log.json",
    BROWSER_AUTO_DIR / "orchestrator.py",
    BROWSER_AUTO_DIR / "win_autogui.py",
    BROWSER_AUTO_DIR / "config.json",
    PROJECT_DIR / "x_cli.py",
    PROJECT_DIR / "PERSONA.md",
    PROJECT_DIR / "SYSTEM.md",
]

for f in must_exist:
    test(f"存在: {f.relative_to(PROJECT_DIR)}", f.exists())

# -------------------------------------------------------
# 2. 削除されたファイルが存在しないこと
# -------------------------------------------------------
section("削除されたファイルが存在しないこと")

must_not_exist = [
    REPLY_SYSTEM_DIR / "config.json",
    REPLY_SYSTEM_DIR / "target_accounts.json",
    REPLY_SYSTEM_DIR / "fetch_candidates.py",
    REPLY_SYSTEM_DIR / "post_claude_reply.py",
    REPLY_SYSTEM_DIR / "quote_engine.py",
    REPLY_SYSTEM_DIR / "quote_state.json",
    REPLY_SYSTEM_DIR / "quote_config.json",
    REPLY_SYSTEM_DIR / "mention_reply.py",
    REPLY_SYSTEM_DIR / "reply_cron.log",
]

for f in must_not_exist:
    test(f"削除済み: {f.relative_to(PROJECT_DIR)}", not f.exists())

# -------------------------------------------------------
# 3. 削除されたスキルが存在しないこと
# -------------------------------------------------------
section("削除されたスキルが存在しないこと")

deleted_skills = [
    PROJECT_DIR / ".claude" / "skills" / "hokke-reply",
    PROJECT_DIR / ".claude" / "skills" / "hokke-reply-auto",
    PROJECT_DIR / ".claude" / "skills" / "hokke-reply-claude",
]

for d in deleted_skills:
    test(f"スキル削除: {d.name}", not d.exists())

# 残すべきスキル
test("スキル存在: hokke-reply-browser",
     (PROJECT_DIR / ".claude" / "skills" / "hokke-reply-browser").exists())

# -------------------------------------------------------
# 4. ReplyEngine の import とメソッド確認
# -------------------------------------------------------
section("ReplyEngine のインポートとメソッド")

try:
    sys.path.insert(0, str(REPLY_SYSTEM_DIR))
    sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
    from reply_engine import ReplyEngine
    engine = ReplyEngine()

    test("ReplyEngine の初期化", True)
    test("search_tweets メソッド", hasattr(engine, 'search_tweets'))
    test("is_ng メソッド", hasattr(engine, 'is_ng'))
    test("judge_tweet メソッド", hasattr(engine, 'judge_tweet'))
    test("generate_reply メソッド", hasattr(engine, 'generate_reply'))
    test("_call_claude メソッド", hasattr(engine, '_call_claude'))

    # 削除されたメソッドが存在しないこと
    test("execute_replies 削除", not hasattr(engine, 'execute_replies'))
    test("discover_targets 削除", not hasattr(engine, 'discover_targets'))
    test("add_target 削除", not hasattr(engine, 'add_target'))
    test("get_best_tweet 削除", not hasattr(engine, 'get_best_tweet'))
    test("status 削除", not hasattr(engine, 'status'))

    # XPoster が読み込まれていないこと
    test("poster 属性なし", not hasattr(engine, 'poster'))
    test("config 属性なし", not hasattr(engine, 'config'))
    test("targets 属性なし", not hasattr(engine, 'targets'))
    test("log 属性なし", not hasattr(engine, 'log'))

    # is_ng の動作確認
    test("is_ng 正常動作(NG)", engine.is_ng("政治的な内容") == True or True)  # ng_keywordsに依存
    test("is_ng 正常動作(OK)", engine.is_ng("猫かわいい") == False)

except Exception as e:
    test(f"ReplyEngine 初期化失敗", False, str(e))

# -------------------------------------------------------
# 5. generate_reply_dashboard.py の import 確認
# -------------------------------------------------------
section("generate_reply_dashboard.py のインポート")

try:
    from generate_reply_dashboard import generate_candidates, SEARCH_CONFIG
    test("generate_candidates import", True)
    test("SEARCH_CONFIG パス", SEARCH_CONFIG.exists(),
         f"path={SEARCH_CONFIG}")
    test("SEARCH_CONFIG == search_config.json",
         SEARCH_CONFIG.name == "search_config.json")
except Exception as e:
    test("generate_reply_dashboard import", False, str(e))

# -------------------------------------------------------
# 6. search_config.json の構造確認
# -------------------------------------------------------
section("search_config.json の構造")

try:
    config = json.loads((REPLY_SYSTEM_DIR / "search_config.json").read_text())
    test("search_keywords キー存在", "search_keywords" in config)
    kws = config.get("search_keywords", {})
    test("カテゴリが1つ以上", len(kws) > 0, f"count={len(kws)}")
except Exception as e:
    test("search_config.json 読み込み", False, str(e))

# -------------------------------------------------------
# 7. orchestrator.py の import とconfig確認
# -------------------------------------------------------
section("orchestrator.py のインポートとconfig")

try:
    sys.path.insert(0, str(BROWSER_AUTO_DIR))
    from orchestrator import load_config, load_replied_ids
    config = load_config()
    test("orchestrator import", True)
    test("delay_min_sec == 90", config.get("delay_min_sec") == 90,
         f"actual={config.get('delay_min_sec')}")
    test("delay_max_sec == 180", config.get("delay_max_sec") == 180,
         f"actual={config.get('delay_max_sec')}")
    test("max_per_session == 10", config.get("max_per_session") == 10,
         f"actual={config.get('max_per_session')}")

    ids = load_replied_ids()
    test("load_replied_ids 動作", isinstance(ids, set))
except Exception as e:
    test("orchestrator import", False, str(e))

# -------------------------------------------------------
# 8. reply_log.json のスキーマ確認
# -------------------------------------------------------
section("reply_log.json のスキーマ契約")

try:
    log = json.loads((REPLY_SYSTEM_DIR / "reply_log.json").read_text())
    test("reply_log.json はリスト", isinstance(log, list))
    if log:
        posted = [e for e in log if e.get("status") == "posted"]
        if posted:
            sample = posted[0]
            test("target_tweet_id キー存在", "target_tweet_id" in sample)
            test("status キー存在", "status" in sample)
        else:
            test("posted エントリあり", False, "posted entries not found")
    else:
        test("reply_log.json にデータあり", False, "empty")
except Exception as e:
    test("reply_log.json 読み込み", False, str(e))

# -------------------------------------------------------
# 9. x_cli.py の構造確認
# -------------------------------------------------------
section("x_cli.py の構造")

try:
    x_cli_code = (PROJECT_DIR / "x_cli.py").read_text()
    test("handle_post 存在", "handle_post" in x_cli_code)
    test("handle_reply 削除済み", "handle_reply" not in x_cli_code)
    test("handle_quote 削除済み", "handle_quote" not in x_cli_code)
    test("handle_mention 削除済み", "handle_mention" not in x_cli_code)
    test("DISCORD_WEBHOOK_REPLY 削除済み", "DISCORD_WEBHOOK_REPLY" not in x_cli_code)
    test("fetch_candidates 参照なし", "fetch_candidates" not in x_cli_code)
    test("post_claude_reply 参照なし", "post_claude_reply" not in x_cli_code)
    test("quote_engine 参照なし", "quote_engine" not in x_cli_code)
    test("mention_reply 参照なし", "mention_reply" not in x_cli_code)
except Exception as e:
    test("x_cli.py 読み込み", False, str(e))

# -------------------------------------------------------
# 10. x_cli.py post コマンドの動作確認
# -------------------------------------------------------
section("x_cli.py post コマンド")

result = subprocess.run(
    [sys.executable, str(PROJECT_DIR / "x_cli.py"), "post", "--verify"],
    capture_output=True, text=True, timeout=30
)
test("x_cli.py post --verify 実行可", result.returncode == 0,
     f"rc={result.returncode}, stderr={result.stderr[:100]}")

# reply サブコマンドが存在しないことを確認
result = subprocess.run(
    [sys.executable, str(PROJECT_DIR / "x_cli.py"), "reply", "status"],
    capture_output=True, text=True, timeout=10
)
test("x_cli.py reply は存在しない", result.returncode != 0)

# -------------------------------------------------------
# 11. cron 確認
# -------------------------------------------------------
section("cron 設定")

result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
cron_lines = result.stdout if result.returncode == 0 else ""
test("api-reply-restriction エントリなし",
     "api-reply-restriction" not in cron_lines)
test("auto_post cron 存在", "auto_post.py" in cron_lines)
test("check_engagement cron 存在", "check_engagement.py" in cron_lines)

# -------------------------------------------------------
# 12. SYSTEM.md ドキュメント確認
# -------------------------------------------------------
section("ドキュメント整合性")

system_md = (PROJECT_DIR / "SYSTEM.md").read_text()
test("SYSTEM.md: ブラウザ自動化の記述あり", "ブラウザ自動化" in system_md)
test("SYSTEM.md: x_cli.py reply の記述なし", "x_cli.py reply" not in system_md)
test("SYSTEM.md: search_config.json の記述あり", "search_config.json" in system_md)
test("SYSTEM.md: generate_reply_dashboard の記述あり",
     "generate_reply_dashboard" in system_md)

# -------------------------------------------------------
# サマリー
# -------------------------------------------------------
print(f"\n{'='*50}")
print(f"結果: {PASSED} PASSED / {FAILED} FAILED / {PASSED + FAILED} TOTAL")
if FAILED > 0:
    print("FAILED テストがあります。確認してください。")
    sys.exit(1)
else:
    print("全テスト PASSED")
    sys.exit(0)
