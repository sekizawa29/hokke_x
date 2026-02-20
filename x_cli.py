#!/usr/bin/env python3
"""
Unified command entrypoint for X operations used by .claude skills.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from notifications.discord_notifier import DiscordNotifier
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def run(cmd: list[str], cwd: Path) -> int:
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


def run_capture(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _build_reply_notify_summary(output: str, rc: int, dry_run: bool) -> dict:
    m = re.search(r"結果:\s*(\d+)件投稿,\s*(\d+)件スキップ", output)
    posted = int(m.group(1)) if m else 0
    skipped = int(m.group(2)) if m else 0
    mode = "DRY-RUN" if dry_run else "PROD"

    notes: list[str] = []
    if "今日の上限に到達済み" in output:
        notes.append("日次上限到達")
    if "稼働時間外のためスキップ" in output:
        notes.append("稼働時間外")
    if "連続スキップ上限に到達" in output:
        notes.append("連続スキップ上限で停止")
    if "連続失敗上限に到達" in output:
        notes.append("連続失敗上限で停止")
    if "検索エラー" in output:
        notes.append("検索エラーあり")

    if rc != 0:
        status = "FAILED"
    elif posted > 0:
        status = "SUCCESS"
    elif skipped > 0:
        status = "SKIPPED"
    else:
        status = "DONE"

    return {
        "mode": mode,
        "posted": posted,
        "skipped": skipped,
        "exit_code": rc,
        "status": status,
        "notes": notes,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _notify_reply_result(output: str, rc: int, dry_run: bool) -> None:
    webhook_env = os.getenv("DISCORD_WEBHOOK_REPLY", "").strip()
    if not webhook_env:
        return
    try:
        notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_REPLY")
    except ValueError:
        return

    summary = _build_reply_notify_summary(output=output, rc=rc, dry_run=dry_run)
    color_map = {
        "SUCCESS": 0x2ECC71,
        "SKIPPED": 0xF1C40F,
        "DONE": 0x3498DB,
        "FAILED": 0xE74C3C,
    }
    notes_text = " / ".join(summary["notes"]) if summary["notes"] else "-"
    log_tail = "\n".join(output.splitlines()[-8:]).strip()
    if len(log_tail) > 900:
        log_tail = log_tail[-900:]

    fields = [
        {"name": "Status", "value": f"`{summary['status']}`", "inline": True},
        {"name": "Mode", "value": f"`{summary['mode']}`", "inline": True},
        {"name": "Exit Code", "value": f"`{summary['exit_code']}`", "inline": True},
        {"name": "Posted", "value": f"`{summary['posted']}`", "inline": True},
        {"name": "Skipped", "value": f"`{summary['skipped']}`", "inline": True},
        {"name": "Time", "value": summary["timestamp"], "inline": True},
        {"name": "Notes", "value": notes_text[:1024], "inline": False},
    ]
    if log_tail:
        fields.append({"name": "Log Tail", "value": f"```{log_tail}```", "inline": False})

    res = notifier.send_embed(
        title="ホッケ リプライ実行結果",
        description="定期実行のサマリーです。",
        color=color_map.get(summary["status"], 0x5865F2),
        fields=fields,
        username="Hokke Reply Bot",
    )
    if not res.ok:
        print(f"[notify] Discord送信失敗: {res.error}", file=sys.stderr)


def _notify_reply_exception(error: Exception, dry_run: bool) -> None:
    webhook_env = os.getenv("DISCORD_WEBHOOK_REPLY", "").strip()
    if not webhook_env:
        return
    try:
        notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_REPLY")
    except ValueError:
        return
    mode = "DRY-RUN" if dry_run else "PROD"
    fields = [
        {"name": "Status", "value": "`FAILED`", "inline": True},
        {"name": "Mode", "value": f"`{mode}`", "inline": True},
        {"name": "Time", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
        {"name": "Error", "value": f"```{str(error)[:900]}```", "inline": False},
    ]
    res = notifier.send_embed(
        title="ホッケ リプライ実行エラー",
        description="実行中に例外が発生しました。",
        color=0xE74C3C,
        fields=fields,
        username="Hokke Reply Bot",
    )
    if not res.ok:
        print(f"[notify] Discord送信失敗: {res.error}", file=sys.stderr)


def handle_post(args: argparse.Namespace) -> int:
    cmd = [sys.executable, str(ROOT / "post_scheduler" / "x_poster.py")]
    if args.verify:
        cmd.append("--verify")
    if args.text is not None:
        cmd += ["--text", args.text]
    if args.image:
        cmd += ["--image", args.image]
    if args.reply_to:
        cmd += ["--reply-to", args.reply_to]
    if args.thread:
        cmd += ["--thread", args.thread]
    if args.schedule:
        cmd += ["--schedule", args.schedule]
    if args.hook_category:
        cmd += ["--hook-category", args.hook_category]
    return run(cmd, ROOT)


def handle_reply(args: argparse.Namespace) -> int:
    if args.reply_action == "candidates":
        cmd = [sys.executable, str(ROOT / "reply_system" / "fetch_candidates.py")]
        return run(cmd, ROOT / "reply_system")

    if args.reply_action == "post-claude":
        cmd = [
            sys.executable,
            str(ROOT / "reply_system" / "post_claude_reply.py"),
            "--tweet-id", args.tweet_id,
            "--username", args.username,
            "--tweet-text", args.tweet_text,
            "--reply-text", args.reply_text,
            "--category", args.category,
        ]
        return run(cmd, ROOT / "reply_system")

    cmd = [sys.executable, str(ROOT / "reply_system" / "reply_engine.py")]
    if args.reply_action == "discover":
        cmd += ["discover"]
    elif args.reply_action == "run":
        cmd += ["reply"]
        if args.dry_run:
            cmd.append("--dry-run")
    elif args.reply_action == "status":
        cmd += ["status"]
    elif args.reply_action == "add-target":
        cmd += [
            "add-target",
            "--username", args.username,
            "--user-id", args.user_id,
            "--category", args.category,
        ]
    else:
        return 2

    if args.reply_action == "run" and args.notify_discord:
        try:
            rc, out, err = run_capture(cmd, ROOT / "reply_system")
        except Exception as e:
            _notify_reply_exception(e, dry_run=args.dry_run)
            print(f"[run] reply実行エラー: {e}", file=sys.stderr)
            return 1
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        _notify_reply_result(output=f"{out}\n{err}".strip(), rc=rc, dry_run=args.dry_run)
        return rc

    return run(cmd, ROOT / "reply_system")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified X operation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    post = sub.add_parser("post", help="post/tweet operations")
    post.add_argument("--text", type=str)
    post.add_argument("--image", type=str)
    post.add_argument("--verify", action="store_true")
    post.add_argument("--reply-to", type=str)
    post.add_argument("--thread", type=str)
    post.add_argument("--schedule", type=str)
    post.add_argument("--hook-category", type=str, default="未分類")
    post.set_defaults(func=handle_post)

    reply = sub.add_parser("reply", help="reply operations")
    rsub = reply.add_subparsers(dest="reply_action", required=True)

    rsub.add_parser("discover")

    run_p = rsub.add_parser("run")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--notify-discord", action="store_true")

    rsub.add_parser("status")

    add_t = rsub.add_parser("add-target")
    add_t.add_argument("--username", required=True)
    add_t.add_argument("--user-id", required=True)
    add_t.add_argument("--category", default="その他")

    rsub.add_parser("candidates")

    pc = rsub.add_parser("post-claude")
    pc.add_argument("--tweet-id", required=True)
    pc.add_argument("--username", required=True)
    pc.add_argument("--tweet-text", required=True)
    pc.add_argument("--reply-text", required=True)
    pc.add_argument("--category", default="不明")

    reply.set_defaults(func=handle_reply)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    rc = args.func(args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
