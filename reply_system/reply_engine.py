#!/usr/bin/env python3
"""
ホッケ リプライエンジン（検索・判定・生成ライブラリ）

generate_reply_dashboard.py から import して使用する。
API経由の投稿機能は廃止済み（ブラウザ自動化方式に移行）。
"""

import os
import sys
import json
import json as json_module
import subprocess
import re
import shutil
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
NG_FILE = SCRIPT_DIR / "ng_keywords.json"
PERSONA_FILE = PROJECT_DIR / "PERSONA.md"
REPLY_STRATEGY_FILE = SCRIPT_DIR / "reply_strategy.json"

load_dotenv(ENV_FILE)

sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))
from x_api_client import XApiClient


def _load_json(path: Path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


class ReplyEngine:
    def __init__(self):
        self.ng = _load_json(NG_FILE)
        self.persona = self._load_persona()
        self.reply_strategy = self._load_reply_strategy()

        self.bearer_token = os.getenv('X_BEARER_TOKEN')
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN が未設定")

        self.x_api = XApiClient(require_bearer=True)

    def _load_persona(self) -> str:
        if PERSONA_FILE.exists():
            return PERSONA_FILE.read_text(encoding='utf-8')
        return ""

    def _load_reply_strategy(self) -> dict:
        if REPLY_STRATEGY_FILE.exists():
            try:
                with open(REPLY_STRATEGY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    # --- X API 検索 ---

    def search_tweets(self, query: str, max_results: int = 10) -> list:
        """X API v2でツイートを検索"""
        try:
            return self.x_api.search_recent_tweets(query, max_results=max_results)
        except Exception as e:
            print(f"検索エラー ({query}): {e}")
            return {}

    # --- NGフィルタ ---

    def is_ng(self, text: str) -> bool:
        """NGキーワードが含まれているか"""
        ng_words = self.ng.get('skip_keywords', [])
        text_lower = text.lower()
        for word in ng_words:
            if word.lower() in text_lower:
                return True
        return False

    # --- LLM呼び出し ---

    def _call_claude(self, system_prompt: str, user_prompt: str, timeout: int = 45) -> Optional[str]:
        """Claude CLI共通呼び出し"""
        prompt = f"""# System
{system_prompt}

# User
{user_prompt}
"""
        claude_cmd = shutil.which("claude")
        if not claude_cmd:
            fallback = "/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude"
            if Path(fallback).exists():
                claude_cmd = fallback
            else:
                print("  claude コマンドが見つからない")
                return None

        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith("CLAUDE")}

        try:
            result = subprocess.run(
                [claude_cmd, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=clean_env,
            )
        except subprocess.TimeoutExpired:
            print("  Claude呼び出しタイムアウト")
            return None
        except FileNotFoundError:
            print("  claude コマンドが見つからない")
            return None

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            print(f"  Claude実行エラー (exit={result.returncode}): {err[:200]}")
            return None
        return (result.stdout or "").strip()

    def _extract_reply_text(self, raw: str) -> str:
        """Model output sanitization for reply body."""
        text = (raw or "").strip()
        if not text:
            return ""

        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
        text = re.sub(r"^(リプライ|返信|Reply)\s*[:：]\s*", "", text)

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            text = lines[0]

        text = text.strip().strip('"').strip("「").strip("」")
        return text.strip()

    # --- 判定・生成 ---

    def judge_tweet(self, tweet_text: str) -> Optional[str]:
        """ツイートにリプすべきか判断。None=OK, str=スキップ理由"""
        system_prompt = """あなたはSNS投稿の安全性を判断するモデレーターです。
以下のツイートに、猫キャラクターのアカウントがリプライしても問題ないか判断してください。

## スキップすべきケース
- 訃報・お悔やみ・死亡に関する内容
- 深刻な病気・入院・事故の報告
- 炎上中・論争中の話題
- 政治的・宗教的に繊細な内容
- 明らかな宣伝・スパム・勧誘
- 内容が薄すぎてリプしようがない（「あ」「。」だけ等）
- 文脈がわからない（他ツイートへの返信や内輪ネタ等）
- 怒りや悲しみが強すぎて猫がリプすると不謹慎になりそうな内容
- 下ネタ・性的な含意があるツイート（隠語・スラング・ダブルミーニング含む）
- 誤読リスクが高いツイート（字面と真意が異なる可能性がある）

## 出力形式（厳守）
JSON形式で出力。他の文字は一切含めないこと。
リプOK: {"ok": true}
スキップ: {"ok": false, "reason": "簡潔な理由"}"""

        user_prompt = f"このツイートを判断してください:\n\n{tweet_text}"

        raw = self._call_claude(system_prompt, user_prompt, timeout=45)
        if not raw:
            return "LLM呼び出し失敗"

        try:
            m = re.search(r"\{.*?\}", raw, re.DOTALL)
            payload = m.group(0) if m else raw
            result = json_module.loads(payload)
            if result.get("ok"):
                return None
            return result.get("reason", "不明な理由でスキップ")
        except (json_module.JSONDecodeError, TypeError):
            print(f"  判断JSONパース失敗: {raw}")
            return "判断レスポンス不正"

    def generate_reply(self, tweet_text: str, category: str) -> Optional[str]:
        """judge_tweet → リプ生成の2段階。None=スキップ"""
        self._last_skip_reason = None

        skip_reason = self.judge_tweet(tweet_text)
        if skip_reason:
            print(f"  LLM判断: スキップ ({skip_reason})")
            self._last_skip_reason = skip_reason
            return None

        system_prompt = f"""あなたは「ホッケ」というキャラクターです。以下のペルソナ定義に厳密に従ってリプライを生成してください。

{self.persona}

## リプライのルール（ポストとは別の制約）
- 1〜2文で短く返す（最大80文字程度）
- 「すごい」「いいね」「わかる」だけの薄いリプはしない
- 相手のツイート内容に対してホッケらしい視点でコメントする
- 猫の視点から人間を観察するような一言が理想
- リプライ本文のみを出力。説明や前置きは不要。"""

        guidance = self.reply_strategy.get("guidance")
        if guidance:
            system_prompt += f"\n\n## 運用戦略メモ\n{guidance}"

        user_prompt = f"以下のツイートにホッケとしてリプライしてください。\n\nツイート: {tweet_text}"

        reply_raw = self._call_claude(system_prompt, user_prompt, timeout=60)
        reply = self._extract_reply_text(reply_raw or "")
        if not reply:
            return None

        if len(reply) > 140:
            reply = reply[:140]

        ng_phrases = ['頑張', '応援', '素敵', 'ありがとう', '！！', '😊', '💪', '✨']
        for phrase in ng_phrases:
            if phrase in reply:
                print(f"  セルフチェックNG: '{phrase}' を含む")
                return None

        return reply
