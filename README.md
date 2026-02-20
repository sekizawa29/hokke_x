# ホッケ X運用 - クイックスタート

> このREADMEは、ホッケX運用システムのセットアップと基本的な使い方を説明します。

---

## まずやること

1. [SYSTEM.md](./SYSTEM.md) を読む  
2. [PERSONA.md](./PERSONA.md) でキャラ確認  
3. [STRATEGY_FINAL.md](./STRATEGY_FINAL.md) で方針確認

---

## 投稿運用（リアルタイム）

このプロジェクトは現在、**予約投稿 (`--schedule`) を使わない**運用です。  
投稿は「実行時に生成して即投稿」します。

### 単発で今すぐ投稿

```bash
cd ~/pjt/hokke_x
python3 x_cli.py post --text "何もしてないのに夕方になった。これが才能" --hook-category "脱力系"
```

### 自動実行（推奨）

`auto_post.py --auto-decide` が、投稿可否をその場で判定して即投稿します。

```bash
cd ~/pjt/hokke_x
python3 post_scheduler/auto_post.py \
  --auto-decide \
  --min-daily-posts 4 \
  --max-daily-posts 5 \
  --min-interval-minutes 120 \
  --run-interval-minutes 30
```

---

## 日常の運用

### パターンA: ネタストックから投稿

```bash
cat ~/pjt/hokke_x/content_stock/relaxation.json
python3 x_cli.py post --text "やる気出す方法？出さなくていいよ" --hook-category "脱力系"
```

### パターンB: 新規で投稿

```bash
python3 x_cli.py post --text "SNSで怒ってる人、だいたい疲れてるだけ" --hook-category "鋭い一言"
```

### パターンC: 画像付き投稿

```bash
python3 x_cli.py post --text "本日の業務報告" --hook-category "猫写真" --image "post_scheduler/images/cat_sleeping.jpg"
```

---

## エンゲージメント分析

```bash
cd ~/pjt/hokke_x/analytics
python ~/path/to/csv_analyzer.py --batch-size 20 "hokke_posts_2026-02.csv"
python ~/path/to/generate_report.py
cat ANALYSIS_REPORT.md
```

---

## ファイルの役割

| ファイル | 役割 |
|---------|------|
| [SYSTEM.md](./SYSTEM.md) | システム全体のドキュメント（必読） |
| [PERSONA.md](./PERSONA.md) | ペルソナ定義（変更不可） |
| [STRATEGY_FINAL.md](./STRATEGY_FINAL.md) | 採用戦略の決定版 |
| `post_scheduler/auto_post.py` | リアルタイム自動投稿 |
| `x_cli.py` | 投稿・リプライの共通入口 |
| `content_stock/*.json` | ネタストック |
| `analytics/ANALYSIS_REPORT.md` | 分析レポート |

---

## 注意点

1. **予約投稿は使わない** - `x_poster.py --schedule` は当面非推奨
2. **ホッケの声** - 投稿前に「ホッケっぽいか？」を確認
3. **投稿頻度** - 1日4〜5件
4. **最小投稿間隔** - 120分

---

## トラブルシューティング

- 投稿が出ない  
  `post_scheduler/auto_post.log` の `[gate]` ログを確認（抽選スキップ/間隔制限/上限到達）
- 画像が出ない  
  画像パスが存在するか確認
- 日本語が中国語フォントになる  
  画像生成プロンプトに日本語フォント指定を入れる

---

*最終更新: 2026-02-20*
