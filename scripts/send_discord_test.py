#!/usr/bin/env python3
"""
Send a Discord test notification without running post/reply jobs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notifications.discord_notifier import DiscordNotifier


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send Discord test message")
    p.add_argument("--env", default="DISCORD_WEBHOOK_REPLY", help="Webhook env name")
    p.add_argument("--title", default="ホッケ 通知テスト", help="Embed title")
    p.add_argument("--description", default="テスト通知です。処理本体は実行していません。", help="Embed description")
    p.add_argument("--username", default="Hokke Notify Bot", help="Webhook username")
    p.add_argument("--status", default="TEST", help="Status label")
    return p.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    try:
        notifier = DiscordNotifier.from_env(args.env)
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    fields = [
        {"name": "Status", "value": f"`{args.status}`", "inline": True},
        {"name": "Webhook Env", "value": f"`{args.env}`", "inline": True},
        {"name": "Time", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
    ]

    res = notifier.send_embed(
        title=args.title,
        description=args.description,
        color=0x3498DB,
        fields=fields,
        username=args.username,
    )
    if not res.ok:
        print(f"[error] send failed: {res.error}", file=sys.stderr)
        return 1

    print(f"[ok] status={res.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
