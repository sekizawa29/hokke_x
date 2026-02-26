# ホッケ X運用システム (SYSTEM.md)

> ホッケAIのX運用に必要なシステム一式のドキュメント

---

## システム概要

ホッケのX運用は、以下の3つの柱で構成:

| 機能 | 担当ツール | 役割 |
|------|----------|------|
| **リアルタイム投稿** | `x_cli.py`, `post_scheduler/auto_post.py` | 実行時生成→即投稿 |
| **画像生成** | x-post-image-generator | 投稿用画像の自動生成 |
| **エンゲージメント分析** | post-analyzer | 投稿パフォーマンスの分析・改善 |

### 設計原則

1. ホッケの声を崩さない
2. 投稿・リプライの実行を自動化して運用負荷を下げる
3. コストと成果を可視化する
4. 分析結果を次の運用に反映する

---

## ディレクトリ構造

```text
~/pjt/hokke_x/
├── SYSTEM.md
├── PERSONA.md
├── STRATEGY.md
├── STRATEGY_FINAL.md
├── x_cli.py                        # 投稿共通入口
├── post_scheduler/
│   ├── auto_post.py                # リアルタイム自動投稿
│   ├── auto_post_state.json        # 日次目標状態（git管理外）
│   ├── auto_post.log               # 投稿ログ
│   ├── x_poster.py                 # 即時投稿実行
│   ├── x_api_client.py             # X API共通クライアント
│   └── cost_logger.py              # API課金イベント記録
├── reply_system/
│   ├── reply_engine.py             # 検索・判定・生成ライブラリ
│   ├── generate_reply_dashboard.py # 候補生成（cron用）
│   ├── search_config.json          # 検索キーワード設定
│   ├── reply_strategy.json         # リプライ戦略
│   ├── ng_keywords.json            # NGキーワード
│   ├── reply_log.json              # リプライログ（重複排除用）
│   └── browser_automation/
│       ├── orchestrator.py         # ブラウザ自動化オーケストレーター
│       ├── win_autogui.py          # Windows側GUI自動化
│       ├── config.json             # タイミング・件数設定
│       └── session_log.json        # セッションログ
├── notifications/
│   └── discord_notifier.py         # Discord通知共通モジュール
├── analytics/
│   ├── x_api_usage.jsonl           # API利用ログ
│   └── daily_cost_report.py        # 日次コスト集計/通知
└── content_stock/
```

---

## 使用ツール・スキル

### 1. リアルタイム投稿

**スキル:** `hokke-post`
**役割:** 投稿文を生成し、`x_cli.py` 経由で即時投稿

**基本コマンド:**
```bash
cd ~/pjt/hokke_x
python3 x_cli.py post --text "今日も何もしなかった。最高" --hook-category "脱力系"
```

### 2. 自動投稿（確率ゲート）

`auto_post.py --auto-decide` は、以下で投稿可否を判定:
- 1日目標投稿数: 4〜5件（ランダム）
- 最小間隔: 120分
- 残り枠に応じた確率抽選

```bash
cd ~/pjt/hokke_x
python3 post_scheduler/auto_post.py \
  --auto-decide \
  --min-daily-posts 4 \
  --max-daily-posts 5 \
  --min-interval-minutes 120 \
  --run-interval-minutes 30
```

### 3. リプライ運用（ブラウザ自動化方式）

**スキル:** `hokke-reply-browser`

**フロー:**
1. `generate_reply_dashboard.py` で候補を事前生成（cron推奨）
2. `orchestrator.py` でブラウザ自動化リプライを実行（手動）

```bash
cd ~/pjt/hokke_x
# 候補生成
python3 reply_system/generate_reply_dashboard.py

# ブラウザ自動化実行
python3 reply_system/browser_automation/orchestrator.py
python3 reply_system/browser_automation/orchestrator.py --dry-run
```

### 4. 日次コスト通知（Discord）

```bash
cd ~/pjt/hokke_x
python3 analytics/daily_cost_report.py --yesterday --notify-discord
```

必要な環境変数:
- `DISCORD_WEBHOOK_COST`

---

## 投稿フロー

### 通常投稿

```text
1. ネタ出し
2. 文面生成
3. auto_postのゲート判定
4. 投稿実行（x_cli.py post）
5. hook_performance.json に記録
6. 後日エンゲージメント分析
```

### リプライ（ブラウザ自動化）

```text
1. generate_reply_dashboard.py で候補生成 + reply_candidates.json に蓄積
2. orchestrator.py でブラウザ操作リプライ実行
3. session_log.json / reply_log.json に記録
4. reply_candidates.json から処理済みを除去
```

---

## 運用ルール

### 投稿

- 目標: 1日4〜5件
- 最小間隔: 120分
- 実行頻度: 30分おき
- 固定時刻投稿は避ける

### リプライ

- 1セッション最大10件、90〜180秒間隔
- 政治・宗教・炎上系はスキップ
- 攻撃的にならない

### 画像

- 無理に毎回付けない
- AI画像は世界観優先
- 個人情報の写り込み注意

---

## トラブルシューティング

### 投稿されない

原因候補:
- ゲート抽選でスキップ
- 最小間隔未満
- 日次上限到達
- 生成失敗

確認先:
- `post_scheduler/auto_post.log`

### コスト通知が来ない

確認:
- `DISCORD_WEBHOOK_COST` が有効か
- `analytics/cost_notify.log` のエラー内容

### 課金が想定より高い

確認:
- `analytics/x_api_usage.jsonl`
- `python3 analytics/daily_cost_report.py --yesterday --json`

---

## 明示的な非推奨

- `x_poster.py --schedule` を使った予約投稿
- `post_queue.json` をGitHub pushして実行する運用

現在はリアルタイム投稿を標準とする。

---

*最終更新: 2026-02-26*
