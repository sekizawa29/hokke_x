#!/usr/bin/env python3
"""
横展開アカウント案出しランナー
15分間隔cronで4ラウンド実行 → 最終ペルソナ作成
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from notifications.discord_notifier import DiscordNotifier
from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env")

STATE_FILE = PROJECT_DIR / "scripts" / "brainstorm_state.json"
OUTPUT_DIR = PROJECT_DIR / "scripts" / "brainstorm_rounds"
FINAL_PERSONA_DIR = PROJECT_DIR / "scripts" / "brainstorm_persona"

TOTAL_ROUNDS = 4


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"current_round": 0, "started_at": None, "completed": False}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def notify_discord(title: str, description: str, color: int = 0x5865F2):
    try:
        notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_POST")
        notifier.send_embed(
            title=title,
            description=description[:4000],
            color=color,
            username="横展開ブレスト",
        )
    except Exception as e:
        print(f"Discord通知失敗: {e}", file=sys.stderr)


def run_codex(prompt: str) -> str:
    """Codex CLIを実行して結果を返す"""
    try:
        result = subprocess.run(
            ["/home/sekiz/.nvm/versions/node/v24.13.0/bin/codex", "exec", "--skip-git-repo-check", prompt],
            capture_output=True, text=True, timeout=180,
            cwd=str(PROJECT_DIR),
        )
        output = result.stdout
        # codex exec の出力からヘッダーとフッターを除去
        lines = output.split("\n")
        content_lines = []
        in_content = False
        for line in lines:
            if line.startswith("codex"):
                in_content = True
                continue
            if in_content:
                if line.startswith("tokens used"):
                    break
                content_lines.append(line)
        return "\n".join(content_lines).strip() if content_lines else output
    except subprocess.TimeoutExpired:
        return "[ERROR] Codex タイムアウト (180秒)"
    except Exception as e:
        return f"[ERROR] Codex 実行失敗: {e}"


# --- Round Prompts ---

ROUND_PROMPTS = {
    1: """X(Twitter)日本語圏で自動運用アカウントを横展開する。以下の条件で案を5つ出してほしい。

前提:
- LLM（Claude）がペルソナに基づき自動生成、cron15-30分間隔で投稿・リプライ
- 画像生成（Gemini API）も自動可能
- 目的: インプレッション最大化 → 独自コンテンツ誘導

今回の視点: 「キャラクター駆動」
- 情報提供型ではなく、キャラクターで惹きつけるアカウント
- フォロワーがキャラに愛着を持ち、継続的にエンゲージする設計
- 既存の「猫AI」キャラとは被らないこと
- LLMが一貫してキャラを演じ続けられること

各案について以下を答えて:
1. キャラ設定（名前案・性格・口調・世界観）
2. なぜインプが取れるか
3. 投稿例3つ
4. リプライ先の層
5. 将来の集客導線
6. リスク""",

    2: """X(Twitter)日本語圏で自動運用アカウントを新規立ち上げる。以下の視点で案を5つ。

前提:
- LLM自動生成 + cron完結（人間介入なし）
- 画像生成可能
- 目的: インプ最大化 → 集客

今回の視点: 「エンゲージメント構造」
- RT・引用・リプライ・保存が自然に発生する投稿形式
- 参加型・対話型・シリーズ型など「1投稿で終わらない」設計
- 日本Xでバズりやすい構造パターンを活用

各案について:
1. 投稿フォーマット（テンプレート）
2. エンゲージメントが発生する仕組み
3. 具体的な投稿例3つ
4. ペルソナの方向性
5. リプライ戦略
6. LLM自動生成との相性
7. 1日の投稿スケジュール案""",

    3: """X(Twitter)横展開アカウントの案を精査する。以下の観点で5案出してほしい。

前提:
- LLM + cron自動運用（人間の日常介入なし）
- 画像自動生成可能
- 既に猫AIキャラアカウントを運用中

今回の視点: 「実装容易性 × 収益導線」
- 既存システム（ペルソナベースのツイート生成、キーワードリプライ、パフォーマンス追跡）をそのまま流用できる
- ファクトチェック不要で品質が安定する
- 最終的にマネタイズ可能な導線が明確
- 競合が少ない or 差別化が容易

各案について:
1. なぜ実装が簡単か（既存コードのどこを変えるだけか）
2. ファクトチェックリスクの有無
3. 具体的なマネタイズ手段（3つ以上）
4. 競合分析（類似アカウントの有無）
5. 3ヶ月後の想定フォロワー数とインプレッション
6. ペルソナ概要
7. 投稿例3つ""",
}


def run_round(round_num: int) -> str:
    """指定ラウンドを実行し、結果を保存"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if round_num <= 3:
        prompt = ROUND_PROMPTS[round_num]
        result = run_codex(prompt)
    else:
        # Round 4: 統合・最終選定
        # 過去ラウンドの結果を読み込み
        prev_results = []
        for i in range(1, 4):
            f = OUTPUT_DIR / f"round_{i}.md"
            if f.exists():
                prev_results.append(f"## ラウンド{i}の結果\n{f.read_text()}")

        consolidated = "\n\n---\n\n".join(prev_results)

        prompt = f"""以下は3ラウンドにわたるブレインストーミングの結果。これを統合して最終的なアカウント案を2つに絞り込んでほしい。

【選定基準】（優先度順）
1. LLM自動運用との相性（cron完結、ファクトチェック不要）
2. インプレッション獲得力（日本X市場）
3. キャラクターの魅力（フォロー継続率）
4. マネタイズ導線の明確さ
5. 既存システムとの実装互換性

【出力形式】
各案について:
- アカウント名案（@xxx）
- 一言コンセプト
- 選定理由（なぜこの2つか）
- キャラ設定詳細（性格、口調、世界観、一人称、禁止事項）
- 投稿カテゴリ（5つ程度）
- 投稿例（各カテゴリ1つずつ）
- リプライ戦略
- 画像生成戦略
- 1日の運用フロー
- マネタイズロードマップ（3/6/12ヶ月）

---

{consolidated}"""

        result = run_codex(prompt)

    # 結果を保存
    output_file = OUTPUT_DIR / f"round_{round_num}.md"
    output_file.write_text(result, encoding="utf-8")

    return result


def summarize_for_discord(round_num: int, result: str) -> str:
    """Discord通知用に要約"""
    # 最初の500文字程度を抽出
    lines = result.split("\n")
    summary_lines = []
    char_count = 0
    for line in lines:
        if char_count > 800:
            summary_lines.append("...")
            break
        summary_lines.append(line)
        char_count += len(line)
    return "\n".join(summary_lines)


def main():
    state = load_state()

    if state.get("completed"):
        print("全ラウンド完了済み。リセットするには brainstorm_state.json を削除してください。")
        return

    current = state["current_round"] + 1

    if current > TOTAL_ROUNDS:
        print("全ラウンド完了済み。")
        state["completed"] = True
        save_state(state)
        return

    if current == 1:
        state["started_at"] = datetime.now().isoformat()

    now = datetime.now().strftime("%H:%M")

    # Discord: 開始通知
    notify_discord(
        f"ブレスト Round {current}/{TOTAL_ROUNDS} 開始",
        f"時刻: {now}\n視点: {_round_label(current)}",
        color=0x3498DB,
    )

    print(f"=== Round {current}/{TOTAL_ROUNDS}: {_round_label(current)} ===")

    # 実行
    result = run_round(current)

    # Discord: 結果通知
    summary = summarize_for_discord(current, result)
    if current < TOTAL_ROUNDS:
        notify_discord(
            f"ブレスト Round {current}/{TOTAL_ROUNDS} 完了",
            f"{summary}\n\n次回: 15分後 (Round {current+1}: {_round_label(current+1)})",
            color=0x2ECC71,
        )
    else:
        notify_discord(
            "ブレスト全ラウンド完了!",
            f"最終選定結果:\n{summary}\n\n詳細: scripts/brainstorm_rounds/round_4.md",
            color=0xE74C3C,
        )

    # State更新
    state["current_round"] = current
    if current >= TOTAL_ROUNDS:
        state["completed"] = True
        state["completed_at"] = datetime.now().isoformat()
    save_state(state)

    print(f"Round {current} 完了。結果: scripts/brainstorm_rounds/round_{current}.md")


def _round_label(n: int) -> str:
    labels = {
        1: "キャラクター駆動の案出し",
        2: "エンゲージメント構造の案出し",
        3: "実装容易性×収益導線の案出し",
        4: "最終統合・ペルソナ作成",
    }
    return labels.get(n, f"Round {n}")


if __name__ == "__main__":
    main()
