# ホッケ ダッシュボード開発進捗

## 概要

ホッケ運用システムのダッシュボード。ローカルサーバーでエラーなく閲覧できることが目標。
自律開発: cron で30分毎に `claude -p` を実行し、議論→実装→検証のサイクルで進める。

## 技術スタック

- Backend: Python + FastAPI (uvicorn), uv で管理
- Frontend: Jinja2 テンプレート + 静的CSS（JSは最小限）
- データソース: 既存のJSONファイル群を読み取り専用で参照

## データソース

| ファイル | 内容 |
|---|---|
| `hook_performance.json` | 投稿パフォーマンス（imp, likes, diagnosis等） |
| `post_scheduler/strategy.json` | 現在の投稿戦略（preferred/avoid/guidance） |
| `post_scheduler/auto_post_state.json` | 今日の投稿状態（target, consecutive_skips） |
| `post_scheduler/auto_post.log` | 直近の自動投稿ログ |
| `reply_system/reply_log.json` | リプライ履歴 |
| `reply_system/reply_strategy.json` | リプライ戦略 |

## フェーズとタスク

タスクは議論の結果に基づいて修正・追加・削除してよい。変更時は変更理由をセッションログに記録する。

### Phase 1: 設計・基盤 [完了]
- [x] 1-1. ダッシュボードに何を表示すべきか、ペルソナ議論で設計を固める
- [x] 1-2. FastAPI アプリ骨格 (`dashboard/app.py`)
- [x] 1-3. データローダー (`dashboard/data_loader.py`)
- [x] 1-4. 構文チェック + Codex レビュー

### Phase 2: API エンドポイント [完了]
- [x] 2-1. `/api/data` にタイムスタンプ追加 + テンプレート未作成時のフォールバック
- [x] 2-2. サーバー起動 + curl 動作確認
- [x] 2-3. Codex レビュー（3-2 に統合）

### Phase 3: フロントエンド [完了]
- [x] 3-1. ダッシュボード全セクション実装（HTML+CSS、6セクション一括）
- [x] 3-2. Codex レビュー（2-3 と統合）

### Phase 4: 結合・検証 [完了]
- [x] 4-1. サーバー起動 + 全ページアクセス確認
- [x] 4-2. エラーハンドリング（データファイル欠損時のフォールバック）
- [x] 4-3. Codex 最終レビュー
- [x] 4-4. 起動スクリプト作成

### Phase 5: ポスト完了レビュー [完了]
- [x] 5-1. _EMPTY_DATA の shallow copy を deepcopy に修正（リクエスト間汚染防止）
- [x] 5-2. load_auto_post_state() の型正規化（date/target_today/consecutive_skips）
- [x] 5-3. strategy/reply_strategy の配列フィールドを list[str] に正規化
- [x] 5-4. load_recent_posts() で impressions/likes を None|数値 に正規化

### Phase 6: 第2回ポスト完了レビュー [完了]
- [x] 6-1. reply_summary.recent の date/target_user/category/status を _ensure_str で正規化

### Phase 7: 第3回ポスト完了レビュー [完了]
- [x] 7-1. _load_text() を _load_tail() に置き換え（ログ肥大時のメモリ/応答時間対策）

## セッションログ

| # | 日時 | 実施内容 | 議論のハイライト | タスク変更 |
|---|---|---|---|---|
| 1 | 2026-02-25 | 1-1 設計議論, 1-2 app.py, 1-3 data_loader.py, 構文チェック+データ読み込み検証 | 運用者: 今日の状態・直近パフォーマンス・戦略が最重要。デザイナー: 1ページ6セクション構成。批評家: リプライのposted率表示を追加、ログパースは正規表現でエラー行のみに絞る。 | なし |
| 2 | 2026-02-25 | 1-4 構文チェック+Codexレビュー（2ラウンド）, 2-1 タイムスタンプ+フォールバック, 2-2 サーバー動作確認 | Codex指摘: async→def変更、重複読込解消、例外範囲拡大、型ガード追加、ログパスサニタイズ。2回目で_load_textのValueError漏れ・postsの型保証・reply_log要素型未検証を追加修正。Phase2議論: エンドポイントは既に十分、タイムスタンプとテンプレートフォールバックのみ追加。 | Phase 2 タスク粒度を調整: 2-1はタイムスタンプ+フォールバックに変更、2-3はPhase3後にまとめて実施 |
| 3 | 2026-02-25 | 3-1 フロントエンド全セクション実装（HTML+CSS）、Noneハンドリング修正 | エンジニア: Jinja2+CSS1ファイルで十分、JS不要。運用者: 投稿目標・直近投稿・エラーをページ上部に。デザイナー: 6セクション構成（サマリカード→直近投稿→カテゴリ統計→戦略2列→リプライ→エラー）。批評家: エラー0件のポジティブ表示、テキスト50文字truncate、3-1/3-2統合を提案。実装後にJinja2のdefaultフィルタがNoneに効かない問題を発見し`or`演算子+`is not none`テストで修正。 | 3-1と3-2を統合（設計と実装を分けるメリットが薄いため）。3-3を3-2に変番しCodexレビューは2-3と統合。 |
| 4 | 2026-02-25 | 3-2/2-3 Codexレビュー（2ラウンド）+ 修正、4-1 サーバー起動+全ページ確認 | Codex1回目: 修正必須4件（CSSインジェクション・型前提・スライス例外・ログ露出）+推奨6件。批評家: 修正必須4件+ログ最適化を対応、Pydantic/キャッシュ/HTML意味構造は見送り。Codex2回目: Authorization:Bearerマスク漏れ・_safe_numberのNaN/inf/bool通過を追加指摘、hookCategoryのstr()正規化は設計判断として見送り。4-1: GET / と /api/data が両方200 OK、全データ正常表示を確認。 | なし |
| 5 | 2026-02-25 | 4-2 エラーハンドリング, 4-3 Codex最終レビュー, 4-4 起動スクリプト | エンジニア: app.pyにトップレベルtry-exceptが無く500リスクあり→_load_data_safe()追加。運用者: 白画面が最悪、何か表示されれば原因特定可。Codex最終レビュー: Must Fix3件中、認証なし→localhost限定で対応不要、秘密情報マスク→JSON形式対応追加、戻り値型チェック→isinstance追加。Nice to Have4件中、未使用import除去のみ対応。4-4: scripts/start.sh作成（host=127.0.0.1固定、PORT環境変数対応）。全Phase完了。 | なし |
| 6 | 2026-02-25 | Phase5 ポスト完了レビュー: 構文チェック・サーバーテスト・Codexレビュー2ラウンド | Codex1回目: Must Fix5件（deepcopy不足・型未正規化3件・shallow copy汚染）、Nice to Have4件、Info2件。対応: Must Fix4件修正（認証なしはlocalhost限定で見送り、ログマスキングは既対応で見送り）。Codex2回目: 残存必須指摘なし、全修正承認。 | Phase 5 追加（レビュー修正4件） |
| 7 | 2026-02-25 | Phase6 第2回レビュー: 構文チェック・サーバーテスト・Codexレビュー | Codex: Must Fix0件。Nice to Have5件（reply_summary.recent型正規化不足・defaultフィルタNone問題・ログ秘匿Regex部分置換・モバイル非対応・同期I/O）。対応: reply_summary.recentの5フィールドを_ensure_strで正規化。見送り: ログ秘匿化改善・モバイルレスポンシブ・キャッシュ（localhost単独利用のため不要）。 | Phase 6 追加（レビュー修正1件） |
| 8 | 2026-02-26 | Phase7 第3回レビュー: 構文チェック・サーバーテスト・Codexレビュー | Codex: Must Fix1件（_load_textがログ全体をread_text、末尾200行しか使わない→肥大時問題）。Nice to Have3件（defaultフィルタNone・モバイル非対応・毎リクエスト全件走査）。Info1件（エラーパターン限定的）。対応: _load_text→_load_tail置き換え（seek末尾64KB読み）。見送り: defaultフィルタ（data_loaderで型正規化済み）・モバイル・キャッシュ・エラーパターン拡張（全てlocalhost単独利用で影響軽微）。 | Phase 7 追加（レビュー修正1件） |
