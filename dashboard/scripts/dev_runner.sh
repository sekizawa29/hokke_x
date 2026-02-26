#!/bin/bash
# ホッケ ダッシュボード自律開発ランナー
# cron から15分毎に実行。claude -p で議論→実装→検証のサイクルを回す。
# 全タスク完了後はレビューモードに移行し、改善点を探す。

set -euo pipefail

# cron 環境用 PATH 設定
export PATH="/home/sekiz/.nvm/versions/node/v24.13.0/bin:/home/sekiz/.local/bin:$PATH"

PROJECT_DIR="/home/sekiz/pjt/hokke_x"
DASHBOARD_DIR="${PROJECT_DIR}/dashboard"
PROGRESS_FILE="${DASHBOARD_DIR}/PROGRESS.md"
LOG_FILE="${DASHBOARD_DIR}/scripts/dev_runner.log"
LOCK_FILE="${DASHBOARD_DIR}/scripts/dev_runner.lock"
DONE_FILE="${DASHBOARD_DIR}/scripts/dev_runner.done"
REVIEW_COUNT_FILE="${DASHBOARD_DIR}/scripts/review_count"
CLAUDE_CMD="/home/sekiz/.nvm/versions/node/v24.13.0/bin/claude"
MAX_REVIEWS=3

# ログ関数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 完了済みチェック（即終了、ロック不要）
if [ -f "$DONE_FILE" ]; then
    exit 0
fi

# ロック取得（重複実行防止、最大20分で自動解放）
exec 200>"$LOCK_FILE"
if ! flock -w 1200 200; then
    log "SKIP: 別プロセスが20分以上占有。ロック強制解放を検討"
    exit 0
fi

log "=== dev_runner 開始 ==="

# 進捗ファイル存在チェック
if [ ! -f "$PROGRESS_FILE" ]; then
    log "ERROR: PROGRESS.md が見つからない"
    exit 1
fi

# claude -p 存在チェック
if [ ! -x "$CLAUDE_CMD" ]; then
    log "ERROR: claude コマンドが見つからない: $CLAUDE_CMD"
    exit 1
fi

# CLAUDECODE 環境変数を除去（ネスト起動ブロック回避）
unset CLAUDECODE 2>/dev/null || true

# --- モード判定 ---
MODE="dev"
REVIEW_COUNT=0
if ! grep -q '\- \[ \]' "$PROGRESS_FILE"; then
    REVIEW_COUNT=$(cat "$REVIEW_COUNT_FILE" 2>/dev/null) || REVIEW_COUNT=0
    REVIEW_COUNT=$((REVIEW_COUNT + 0))  # 数値保証

    if [ "$REVIEW_COUNT" -ge "$MAX_REVIEWS" ]; then
        log "レビュー${MAX_REVIEWS}回完了。改善点なし。開発完了。"
        touch "$DONE_FILE"

        # 完了通知
        cd "$PROJECT_DIR"
        /usr/bin/python3 -c "
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from notifications.discord_notifier import DiscordNotifier
try:
    n = DiscordNotifier.from_env('DISCORD_WEBHOOK_POST')
    n.send_embed(
        title='Dashboard dev_runner 完了',
        description='全タスク＋レビュー${MAX_REVIEWS}回完了。開発終了。',
        color=0x57F287,
        username='dev_runner',
    )
except Exception as e:
    print(f'Discord通知失敗: {e}', file=sys.stderr)
" 2>&1 | while read -r line; do log "[discord] $line"; done

        log "=== dev_runner 完了（最終） ==="
        exit 0
    fi

    MODE="review"
    log "モード: レビュー ($((REVIEW_COUNT + 1))/${MAX_REVIEWS}回目)"
fi

PROGRESS_CONTENT=$(cat "$PROGRESS_FILE")

# --- プロンプト構築 ---

if [ "$MODE" = "dev" ]; then
    # ===== 開発モード =====
    read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
あなたはホッケ運用ダッシュボードの開発チームです。
1人で複数の視点を持ち、議論しながら開発を進めてください。

# あなたの中にいるペルソナ

実装の前に、以下のペルソナを順番に「発言」させて議論すること。
全員が発言した後に、結論を出して実装に進む。

## エンジニア（実装担当）
- コードの構造、エラーハンドリング、パフォーマンスを重視
- 「これは動くか？壊れないか？」を考える

## 運用者（ホッケ運用の当事者）
- 毎日このダッシュボードを見る人の立場
- 「一目で何がわかるべきか？何が要らないか？」を考える
- ホッケの運用データ（投稿数、エンゲージメント、戦略）に詳しい

## デザイナー（情報設計担当）
- 情報の優先順位、レイアウト、視認性を重視
- 「どの情報を最も目立たせるべきか？」を考える
- 過度な装飾は不要。データが主役

## 批評家（品質ゲート）
- 全員の意見を聞いた後に問題点を指摘する
- 「この設計で見落としていることはないか？」を考える
- Codex レビューの結果を解釈する役割も担う

# 議論のルール

1. 実装に入る前に、必ず4ペルソナの議論を行う
2. 議論は簡潔に。各ペルソナ2-3文ずつ
3. 議論の結果、タスクの内容・順序を変更してもよい
   - タスクを分割する、統合する、追加する、削除する — すべてOK
   - 変更した場合は PROGRESS.md を更新し、セッションログに変更理由を記録
4. 議論の結論が出たら実装に進む

# 進捗ドキュメント
PROMPT_HEREDOC

    PROMPT="${PROMPT}

${PROGRESS_CONTENT}

$(cat << 'RULES_HEREDOC'

# 作業ディレクトリ
/home/sekiz/pjt/hokke_x

# ダッシュボードディレクトリ構造
dashboard/
  app.py          — FastAPI メインアプリ
  data_loader.py  — データ読み込みモジュール
  templates/      — HTMLテンプレート
  static/         — CSS/JS
  scripts/        — 開発用スクリプト
  PROGRESS.md     — この進捗ドキュメント

# 作業手順

## セッションの流れ
1. PROGRESS.md を読み、次の未完了タスクを特定する
2. そのタスクについてペルソナ議論を行う
3. 議論の結論に基づいて実装する（1-2タスクまで）
4. 検証する（構文チェック、動作確認）
5. PROGRESS.md を更新する

## 検証ルール
- コードを書いたら必ず構文チェック:
  cd /home/sekiz/pjt/hokke_x/dashboard && uv run python -c "import py_compile; py_compile.compile('ファイルパス', doraise=True)"
- タスク名に「Codex レビュー」がある場合は必ず実行:
  codex exec --skip-git-repo-check "レビュー内容"
  Codex の指摘は「批評家」ペルソナが解釈し、対応を決める
- API実装後はサーバー起動して確認:
  cd /home/sekiz/pjt/hokke_x/dashboard && uv run uvicorn app:app --port 8099 &
  sleep 3 && curl http://localhost:8099/
  kill %1
- エラーが出たら修正を最優先

## PROGRESS.md 更新ルール
- 完了タスクの [ ] を [x] に変更
- セッションログに以下を記録:
  - セッション番号（連番）
  - 日時
  - 実施内容
  - 議論のハイライト（どのペルソナがどんな意見を出し、どう結論したか）
  - タスク変更があればその内容と理由

## ペース
- 1セッション1-2タスク。急がない
- 議論に時間を使ってよい。深く考えることが品質に繋がる

# データソースのパス（読み取り専用で参照）
- /home/sekiz/pjt/hokke_x/hook_performance.json
- /home/sekiz/pjt/hokke_x/post_scheduler/strategy.json
- /home/sekiz/pjt/hokke_x/post_scheduler/auto_post_state.json
- /home/sekiz/pjt/hokke_x/post_scheduler/auto_post.log
- /home/sekiz/pjt/hokke_x/reply_system/reply_log.json
- /home/sekiz/pjt/hokke_x/reply_system/reply_strategy.json

# 技術要件
- Python 3.12+, FastAPI, uvicorn, Jinja2（全て uv で管理済み）
- dashboard/ に pyproject.toml と .venv がある
- Python実行: cd /home/sekiz/pjt/hokke_x/dashboard && uv run python ...
- uvicorn起動: cd /home/sekiz/pjt/hokke_x/dashboard && uv run uvicorn app:app --port 8099
- フロントエンドは Jinja2 テンプレート + 静的CSS
- JS は最小限（fetch API 程度）
- PC閲覧のみ（レスポンシブ不要）

# 絶対守ること
- 既存の運用ファイル（auto_post.py 等）は変更しない
- データファイルは読み取り専用
- ダッシュボードは dashboard/ ディレクトリ内で完結させる
RULES_HEREDOC
)"

else
    # ===== レビューモード =====
    read -r -d '' PROMPT << 'REVIEW_HEREDOC' || true
あなたはホッケ運用ダッシュボードの品質レビュアーです。
全開発タスクが完了したダッシュボードの品質チェック・改善を行います。

# レビュー観点（優先順）

1. **動作確認**: サーバーを起動し、全エンドポイント (/, /api/data) をテスト。HTTPステータスとレスポンス内容を確認
2. **ランタイムエラー**: 実際にデータを読み込んで例外が出ないか。データファイルが空・欠損の場合の挙動
3. **コード品質**: 不要なimport、未使用変数、重複コード、型の不整合
4. **セキュリティ**: 入力サニタイズ、パストラバーサル、情報漏洩リスク
5. **UI/UX**: テンプレートの表示崩れ、データの読みやすさ、重要情報の視認性
6. **エッジケース**: 空リスト、None値、異常に長い文字列、数値の境界値

# 作業手順

1. dashboard/ 内の全ソースファイルを読む（app.py, data_loader.py, templates/, static/）
2. 構文チェックを実行:
   cd /home/sekiz/pjt/hokke_x/dashboard && uv run python -c "import py_compile; py_compile.compile('app.py', doraise=True); py_compile.compile('data_loader.py', doraise=True)"
3. サーバーを起動してエンドポイントをテスト:
   cd /home/sekiz/pjt/hokke_x/dashboard && uv run uvicorn app:app --port 8099 &
   sleep 3 && curl -s -o /dev/null -w '%{http_code}' http://localhost:8099/
   curl -s http://localhost:8099/api/data | head -c 500
   kill %1
4. Codex にレビューを依頼:
   codex exec --skip-git-repo-check "dashboard/ の全ファイルをレビュー。バグ、セキュリティ問題、改善点を指摘して"
5. 上記の結果を総合判断

# 結果の記録

## 問題が見つかった場合
- 修正を実装する
- PROGRESS.md に新しいPhaseとして追加:
  ### Phase N: ポスト完了レビュー
  - [ ] 具体的なタスク名
- タスクを完了したら [x] にする
- セッションログに記録

## 問題がない場合
- PROGRESS.md のセッションログに「レビュー完了、改善点なし」と記録
- 新しいタスクは追加しない

# 作業ディレクトリ
/home/sekiz/pjt/hokke_x

# ダッシュボードファイル
- dashboard/app.py — FastAPI メインアプリ
- dashboard/data_loader.py — データ読み込みモジュール
- dashboard/templates/dashboard.html — HTMLテンプレート
- dashboard/static/style.css — スタイルシート
- dashboard/scripts/start.sh — 起動スクリプト
- dashboard/PROGRESS.md — 進捗ドキュメント

# データソースのパス（読み取り専用で参照）
- /home/sekiz/pjt/hokke_x/hook_performance.json
- /home/sekiz/pjt/hokke_x/post_scheduler/strategy.json
- /home/sekiz/pjt/hokke_x/post_scheduler/auto_post_state.json
- /home/sekiz/pjt/hokke_x/post_scheduler/auto_post.log
- /home/sekiz/pjt/hokke_x/reply_system/reply_log.json
- /home/sekiz/pjt/hokke_x/reply_system/reply_strategy.json

# 技術要件
- Python 3.12+, FastAPI, uvicorn, Jinja2（全て uv で管理済み）
- Python実行: cd /home/sekiz/pjt/hokke_x/dashboard && uv run python ...

# 絶対守ること
- 既存の運用ファイル（auto_post.py 等）は変更しない
- データファイルは読み取り専用
- ダッシュボードは dashboard/ ディレクトリ内で完結させる
- 過度なリファクタリングは不要。実際の問題のみ修正する
REVIEW_HEREDOC

    PROMPT="${PROMPT}

# 現在の進捗

${PROGRESS_CONTENT}"

fi

# claude -p 実行（15分タイムアウト、stdin を /dev/null に固定）
log "claude -p 実行開始 (mode=${MODE})"
RESULT=$(timeout 900 "$CLAUDE_CMD" -p "$PROMPT" --allowedTools "Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch,Task" < /dev/null 2>&1) || true
EXIT_CODE=$?

RESULT_FILE=$(mktemp)
trap "rm -f '$RESULT_FILE'" EXIT

if [ "$EXIT_CODE" -eq 124 ]; then
    log "ERROR: claude -p タイムアウト (15分超過)"
    STATUS="timeout"
    echo "タイムアウト（15分超過）" > "$RESULT_FILE"
else
    # 結果をログに記録（先頭1000文字）
    RESULT_PREVIEW=$(echo "$RESULT" | head -c 1000)
    log "claude -p 完了 (exit=$EXIT_CODE): ${RESULT_PREVIEW}"
    # Discord用に先頭800文字をファイルに保存（embed field上限1024）
    echo "$RESULT" | head -c 800 > "$RESULT_FILE"
    if [ "$EXIT_CODE" -eq 0 ]; then
        STATUS="ok"
    else
        STATUS="error (exit=$EXIT_CODE)"
    fi
fi

# --- レビューモード: 新規タスク検出 ---
if [ "$MODE" = "review" ]; then
    if grep -q '\- \[ \]' "$PROGRESS_FILE"; then
        # レビューで新規タスクが追加された → カウントリセット
        echo 0 > "$REVIEW_COUNT_FILE"
        log "レビューで新規タスク発見。次回実行で対応。"
        STATUS="review_found_issues"
    else
        # 改善点なし → カウント加算
        REVIEW_COUNT=$((REVIEW_COUNT + 1))
        echo "$REVIEW_COUNT" > "$REVIEW_COUNT_FILE"
        log "レビュー完了。改善点なし (${REVIEW_COUNT}/${MAX_REVIEWS})"
        STATUS="review_clean"
    fi
fi

log "=== dev_runner 完了 ==="

# --- Discord 通知 ---
COMPLETED=$(grep -c '\- \[x\]' "$PROGRESS_FILE" 2>/dev/null) || COMPLETED=0
REMAINING=$(grep -c '\- \[ \]' "$PROGRESS_FILE" 2>/dev/null) || REMAINING=0

cd "$PROJECT_DIR"
/usr/bin/python3 -c "
import sys, pathlib
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from notifications.discord_notifier import DiscordNotifier
try:
    mode = '${MODE}'
    status = '${STATUS}'
    review_count = '${REVIEW_COUNT}'
    max_reviews = '${MAX_REVIEWS}'

    # claude -p の出力をファイルから読み込み（クォート問題回避）
    summary = pathlib.Path('${RESULT_FILE}').read_text(encoding='utf-8').strip()
    if len(summary) > 900:
        summary = summary[:900] + '…'
    if not summary:
        summary = '(出力なし)'

    if mode == 'review':
        if status == 'review_found_issues':
            desc = 'レビューで改善点を発見。次回修正予定。'
            color = 0xFEE75C  # yellow
        else:
            desc = f'レビュー {review_count}/{max_reviews} 回目完了。改善点なし。'
            color = 0x57F287  # green
        title = 'Dashboard レビュー'
    else:
        desc = f'status: {status}'
        color = 0x57F287 if status == 'ok' else 0xED4245
        title = 'Dashboard dev_runner'

    n = DiscordNotifier.from_env('DISCORD_WEBHOOK_POST')
    n.send_embed(
        title=title,
        description=desc,
        color=color,
        fields=[
            {'name': '完了', 'value': '${COMPLETED} タスク', 'inline': True},
            {'name': '残り', 'value': '${REMAINING} タスク', 'inline': True},
            {'name': 'モード', 'value': mode, 'inline': True},
            {'name': '進捗サマリ', 'value': summary, 'inline': False},
        ],
        username='dev_runner',
    )
except Exception as e:
    print(f'Discord通知失敗: {e}', file=sys.stderr)
" 2>&1 | while read -r line; do log "[discord] $line"; done
