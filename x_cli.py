#!/usr/bin/env python3
"""
Unified command entrypoint for X operations used by .claude skills.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def run(cmd: list[str], cwd: Path) -> int:
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    rc = args.func(args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
