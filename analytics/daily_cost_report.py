#!/usr/bin/env python3
"""
Daily cost report from analytics/x_api_usage.jsonl.
"""

import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR))
from notifications.discord_notifier import DiscordNotifier

LOG_FILE = Path(__file__).resolve().parent / "x_api_usage.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="X API日次コスト集計")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--yesterday", action="store_true", help="昨日を対象にする")
    parser.add_argument("--json", action="store_true", help="JSONで出力")
    parser.add_argument("--notify-discord", action="store_true", help="Discordに通知する")
    parser.add_argument("--discord-env", default="DISCORD_WEBHOOK_COST", help="Webhook URLを読む環境変数名")
    parser.add_argument("--discord-username", default="X Cost Reporter", help="Discord表示名")
    return parser.parse_args()


def target_date(args: argparse.Namespace) -> str:
    if args.date:
        return args.date
    if args.yesterday:
        return (date.today() - timedelta(days=1)).isoformat()
    return date.today().isoformat()


def load_records(day: str) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    rows = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("date") == day:
                rows.append(rec)
    return rows


def summarize(rows: list[dict]) -> dict:
    by_type = defaultdict(lambda: {"units": 0, "cost": 0.0, "events": 0})
    by_endpoint = defaultdict(lambda: {"units": 0, "cost": 0.0, "events": 0})
    total = 0.0
    for r in rows:
        usage_type = r.get("usage_type", "unknown")
        endpoint = r.get("endpoint", "unknown")
        units = int(r.get("units", 0) or 0)
        cost = float(r.get("estimated_cost_usd", 0.0) or 0.0)

        by_type[usage_type]["units"] += units
        by_type[usage_type]["cost"] += cost
        by_type[usage_type]["events"] += 1

        by_endpoint[endpoint]["units"] += units
        by_endpoint[endpoint]["cost"] += cost
        by_endpoint[endpoint]["events"] += 1
        total += cost

    return {
        "events": len(rows),
        "estimated_total_usd": round(total, 6),
        "by_type": {k: {"units": v["units"], "events": v["events"], "cost": round(v["cost"], 6)} for k, v in by_type.items()},
        "by_endpoint": {k: {"units": v["units"], "events": v["events"], "cost": round(v["cost"], 6)} for k, v in by_endpoint.items()},
    }


def build_discord_message(result: dict) -> str:
    def _short(s: str, n: int = 64) -> str:
        return s if len(s) <= n else s[: n - 1] + "…"

    lines = [
        "**X API 日次コストレポート**",
        f"`date` {result['date']}",
        "",
        f"**推定合計**: `${result['estimated_total_usd']:.6f}`",
        f"**イベント数**: `{result['events']}`",
        "",
    ]

    by_type_sorted = sorted(result["by_type"].items(), key=lambda x: x[1]["cost"], reverse=True)[:5]
    lines.append("**by_type 上位5**")
    if by_type_sorted:
        for i, (usage_type, v) in enumerate(by_type_sorted, 1):
            lines.append(
                f"{i}. `{usage_type}`  `${v['cost']:.6f}`  (units=`{v['units']}`, events=`{v['events']}`)"
            )
    else:
        lines.append("- _データなし（この日のAPI利用ログなし）_")

    lines.append("")
    by_ep_sorted = sorted(result["by_endpoint"].items(), key=lambda x: x[1]["cost"], reverse=True)[:5]
    lines.append("**by_endpoint 上位5**")
    if by_ep_sorted:
        for i, (endpoint, v) in enumerate(by_ep_sorted, 1):
            lines.append(
                f"{i}. `{_short(endpoint)}`  `${v['cost']:.6f}`  (units=`{v['units']}`, events=`{v['events']}`)"
            )
    else:
        lines.append("- _データなし（この日のAPI利用ログなし）_")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    day = target_date(args)
    rows = load_records(day)
    result = summarize(rows)
    result["date"] = day
    result["log_file"] = str(LOG_FILE)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"X API日次推定コスト: {day}")
    print(f"イベント数: {result['events']}")
    print(f"推定合計: ${result['estimated_total_usd']:.6f}")
    print("")
    print("[by_type]")
    for usage_type, v in sorted(result["by_type"].items(), key=lambda x: x[1]["cost"], reverse=True):
        print(f"- {usage_type}: ${v['cost']:.6f} (units={v['units']}, events={v['events']})")

    print("")
    print("[by_endpoint]")
    for endpoint, v in sorted(result["by_endpoint"].items(), key=lambda x: x[1]["cost"], reverse=True):
        print(f"- {endpoint}: ${v['cost']:.6f} (units={v['units']}, events={v['events']})")

    if args.notify_discord:
        message = build_discord_message(result)
        notifier = DiscordNotifier.from_env(args.discord_env)
        send_result = notifier.send(message, username=args.discord_username)
        if send_result.ok:
            print("")
            print(f"[notify] Discord送信成功 (status={send_result.status_code})")
        else:
            print("")
            print(f"[notify] Discord送信失敗: {send_result.error}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
