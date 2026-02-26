#!/usr/bin/env python3
"""
手動リプライ/引用ツイート用ダッシュボード生成

検索→フィルタ→LLMリプライ生成→HTML出力
ブラウザで開いてワンクリックでX投稿画面へ
"""

import sys
import json
import random
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import quote as url_quote

sys.stdout.reconfigure(line_buffering=True)

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR / "post_scheduler"))

from x_api_client import XApiClient
from reply_engine import ReplyEngine

SEARCH_CONFIG = SCRIPT_DIR / "search_config.json"
OUTPUT_DIR = PROJECT_DIR / "dashboard"
OUTPUT_FILE = OUTPUT_DIR / "reply_candidates.html"


def generate_candidates(max_queries: int = 3, per_query: int = 10) -> list[dict]:
    """キーワード検索→フィルタ→リプライ生成"""
    config = json.loads(SEARCH_CONFIG.read_text(encoding="utf-8"))
    engine = ReplyEngine()

    keywords = config.get("search_keywords", {})
    query_pool = [(cat, kw) for cat, kws in keywords.items() for kw in kws]
    random.shuffle(query_pool)
    queries = query_pool[:max_queries]

    # 既にリプライ済みのtweet_idを収集（reply_log.json + session_log.json）
    replied_ids: set[str] = set()
    reply_log_file = SCRIPT_DIR / "reply_log.json"
    session_log_file = SCRIPT_DIR / "browser_automation" / "session_log.json"
    for log_path, id_key, status_val in [
        (reply_log_file, "target_tweet_id", "posted"),
        (session_log_file, "tweet_id", "success"),
    ]:
        if log_path.exists():
            try:
                data = json.loads(log_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    replied_ids |= {
                        e.get(id_key, "") for e in data
                        if e.get("status") == status_val
                    } - {""}
            except (json.JSONDecodeError, OSError):
                pass
    if replied_ids:
        print(f"  既リプライ済み: {len(replied_ids)}件を除外対象")

    candidates = []
    seen: set[str] = set()

    for qi, (category, query) in enumerate(queries):
        print(f"[{qi+1}/{len(queries)}] 検索中: '{query}' ({category})")
        try:
            result = engine.search_tweets(query, max_results=per_query)
        except Exception as e:
            print(f"  検索エラー: {e}")
            continue

        tweets = result.get("data", []) or []
        users = {u["id"]: u for u in result.get("includes", {}).get("users", []) or []}

        for tweet in tweets:
            tweet_id = str(tweet.get("id", ""))
            if not tweet_id or tweet_id in seen or tweet_id in replied_ids:
                continue
            seen.add(tweet_id)

            author_id = tweet.get("author_id", "")
            user = users.get(author_id, {})
            username = user.get("username", "")
            display_name = user.get("name", username)
            followers = user.get("public_metrics", {}).get("followers_count", 0)

            if not username or username == "cat_hokke":
                continue

            tweet_text = tweet.get("text", "")
            if engine.is_ng(tweet_text):
                print(f"  NG: @{username}")
                continue

            # generate_reply は内部で judge_tweet + 生成 + セルフチェックを行う
            reply = engine.generate_reply(tweet_text, category)
            if not reply:
                print(f"  スキップ: @{username}")
                continue

            candidates.append({
                "tweet_id": tweet_id,
                "username": username,
                "display_name": display_name,
                "followers": followers,
                "tweet_text": tweet_text,
                "reply_text": reply,
                "category": category,
                "query": query,
            })
            print(f"  ✓ @{username}: {reply[:50]}...")

    return candidates


def build_html(candidates: list[dict]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    data_json = json.dumps(candidates, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ホッケ リプライ候補 ({timestamp})</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: #15202b; color: #e7e9ea;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  padding: 16px; max-width: 680px; margin: 0 auto;
}}
h1 {{
  font-size: 20px; padding: 12px 0; border-bottom: 1px solid #38444d;
  margin-bottom: 16px;
}}
.meta {{ color: #8899a6; font-size: 13px; margin-bottom: 16px; }}
.card {{
  background: #192734; border: 1px solid #38444d; border-radius: 12px;
  padding: 16px; margin-bottom: 12px;
}}
.card.done {{ opacity: 0.4; }}
.card-header {{
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}}
.username {{ color: #1d9bf0; font-weight: bold; font-size: 15px; }}
.username a {{ color: inherit; text-decoration: none; }}
.username a:hover {{ text-decoration: underline; }}
.badge {{
  background: #253341; color: #8899a6; font-size: 11px;
  padding: 2px 8px; border-radius: 10px;
}}
.tweet-text {{
  font-size: 14px; line-height: 1.5; margin-bottom: 12px;
  white-space: pre-wrap; word-break: break-word;
}}
.reply-label {{ color: #8899a6; font-size: 12px; margin-bottom: 4px; }}
textarea {{
  width: 100%; background: #253341; color: #e7e9ea; border: 1px solid #38444d;
  border-radius: 8px; padding: 10px; font-size: 14px; resize: vertical;
  min-height: 60px; font-family: inherit; line-height: 1.4;
}}
textarea:focus {{ outline: none; border-color: #1d9bf0; }}
.actions {{
  display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;
  align-items: center;
}}
.btn {{
  padding: 8px 16px; border-radius: 20px; border: none; cursor: pointer;
  font-size: 14px; font-weight: bold; transition: opacity 0.2s;
}}
.btn:hover {{ opacity: 0.85; }}
.btn-reply {{ background: #1d9bf0; color: #fff; }}
.btn-quote {{ background: #00ba7c; color: #fff; }}
.btn-skip {{
  background: transparent; color: #8899a6; border: 1px solid #38444d;
}}
.toast {{
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: #1d9bf0; color: #fff; padding: 10px 20px; border-radius: 8px;
  font-size: 14px; display: none; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}}
.char-count {{ color: #8899a6; font-size: 12px; margin-left: auto; }}
.empty {{
  text-align: center; padding: 40px; color: #8899a6;
}}
</style>
</head>
<body>

<h1>🐟 ホッケ リプライ候補</h1>
<div class="meta">
  生成: {timestamp} ／ {len(candidates)}件の候補
</div>

<div id="cards"></div>
<div class="toast" id="toast"></div>

<script>
const candidates = {data_json};

const cardsEl = document.getElementById('cards');
const toastEl = document.getElementById('toast');

if (candidates.length === 0) {{
  cardsEl.innerHTML = '<div class="empty">候補が見つかりませんでした</div>';
}}

candidates.forEach((c, i) => {{
  const card = document.createElement('div');
  card.className = 'card';
  card.id = 'card-' + i;
  card.innerHTML = `
    <div class="card-header">
      <span class="username">
        <a href="https://x.com/${{c.username}}" target="_blank" rel="noopener">
          @${{c.username}}
        </a>
      </span>
      <span class="badge">${{c.category}}</span>
    </div>
    <div class="tweet-text">${{escapeHtml(c.tweet_text)}}</div>
    <div class="reply-label">生成リプライ:</div>
    <textarea id="reply-${{i}}">${{escapeHtml(c.reply_text)}}</textarea>
    <div class="actions">
      <button class="btn btn-reply" onclick="doReply(${{i}})">リプライする</button>
      <button class="btn btn-quote" onclick="doQuote(${{i}})">引用する</button>
      <button class="btn btn-skip" onclick="doSkip(${{i}})">スキップ</button>
      <span class="char-count" id="count-${{i}}">${{c.reply_text.length}}文字</span>
    </div>
  `;
  cardsEl.appendChild(card);

  // 文字数カウント
  document.getElementById('reply-' + i).addEventListener('input', (e) => {{
    document.getElementById('count-' + i).textContent = e.target.value.length + '文字';
  }});
}});

function escapeHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

function getReplyText(idx) {{
  return document.getElementById('reply-' + idx).value.trim();
}}

function showToast(msg) {{
  toastEl.textContent = msg;
  toastEl.style.display = 'block';
  setTimeout(() => {{ toastEl.style.display = 'none'; }}, 2500);
}}

function doReply(idx) {{
  const c = candidates[idx];
  const text = getReplyText(idx);
  if (!text) return;

  const intentUrl = 'https://x.com/intent/tweet?in_reply_to=' + c.tweet_id + '&text=' + encodeURIComponent(text);
  window.open(intentUrl, '_blank');

  document.getElementById('card-' + idx).classList.add('done');
}}

function doQuote(idx) {{
  const c = candidates[idx];
  const text = getReplyText(idx);
  if (!text) return;

  const tweetUrl = 'https://x.com/' + c.username + '/status/' + c.tweet_id;
  const intentUrl = 'https://x.com/intent/tweet?text=' + encodeURIComponent(text + ' ' + tweetUrl);
  window.open(intentUrl, '_blank');

  document.getElementById('card-' + idx).classList.add('done');
}}

function doSkip(idx) {{
  document.getElementById('card-' + idx).classList.add('done');
}}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="手動リプライ用ダッシュボード生成")
    parser.add_argument("--queries", type=int, default=3, help="検索クエリ数 (default: 3)")
    parser.add_argument("--per-query", type=int, default=10, help="クエリあたり検索数 (default: 10)")
    args = parser.parse_args()

    print("=== リプライ候補ダッシュボード生成 ===\n")
    new_candidates = generate_candidates(max_queries=args.queries, per_query=args.per_query)

    OUTPUT_DIR.mkdir(exist_ok=True)
    json_file = OUTPUT_DIR / "reply_candidates.json"

    # 既存の未使用候補を読み込んでマージ（古い順を維持）
    existing = []
    existing_ids: set[str] = set()
    if json_file.exists():
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = data
                existing_ids = {c.get("tweet_id", "") for c in existing}
        except (json.JSONDecodeError, OSError):
            pass

    # 新規候補のうち既存にないものだけ追加（既存=古い順が先）
    added = 0
    for c in new_candidates:
        tid = c.get("tweet_id", "")
        if tid and tid not in existing_ids:
            c["generated_at"] = datetime.now().isoformat()
            existing.append(c)
            existing_ids.add(tid)
            added += 1

    merged = existing

    # JSON出力
    json_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # HTML は全候補で生成
    html = build_html(merged)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    print(f"\n完了: 新規{added}件追加 / 合計{len(merged)}件の候補")
    print(f"HTML: {OUTPUT_FILE}")
    print(f"JSON: {json_file}")


if __name__ == "__main__":
    main()
