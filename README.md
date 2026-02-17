# ホッケ X運用 - クイックスタート

> このREADMEは、ホッケX運用システムのセットアップと基本的な使い方を説明します。

---

## 🚀 まずやること

### 1. システム全体を理解する

[SYSTEM.md](./SYSTEM.md) を読んで、全体像を把握してください。

### 2. ペルソナを確認する

[PERSONA.md](./PERSONA.md) でホッケのキャラクターを確認。
- 脱力、シュール、たまに鋭い
- 頑張らない。偉そうにしない。

### 3. 戦略を確認する

[STRATEGY_FINAL.md](./STRATEGY_FINAL.md) で採用戦略を確認。

---

## 📝 初期投稿をする

### ステップ1: 初期投稿を予約する

```bash
cd ~/pjt/hokke_x/post_scheduler

# 脱力系投稿
python x_poster.py --schedule "2026-02-18 08:00" --text "今日も何もしなかった。最高"

# 鋭い一言
python x_poster.py --schedule "2026-02-18 12:00" --text "SNSで怒ってる人、だいたい疲れてるだけ"

# 日常観察
python x_poster.py --schedule "2026-02-18 21:00" --text "コンビニの新商品、猫には関係ないけど気になる"
```

### ステップ2: GitHubにプッシュする

```bash
cd ~/pjt/x_auto  # GitHubリポジトリ
cp ~/pjt/hokke_x/post_scheduler/post_queue.json post_queue.json
git add post_queue.json
git commit -m "Schedule: Initial posts for ホッケ"
git push origin main
```

### ステップ3: 投稿を確認する

- GitHub Actionsで実行ログを確認
- Xアカウントで投稿を確認

---

## 🐾 日常の運用

### 投稿を作成する

**パターンA: ネタストックから選ぶ**

```bash
# ネタストックを確認
cat ~/pjt/hokke_x/content_stock/relaxation.json

# 選んだネタを予約
python x_poster.py --schedule "2026-02-19 08:00" --text "やる気出す方法？出さなくていいよ"
```

**パターンB: 新規で書く**

```bash
python x_poster.py --schedule "2026-02-19 12:00" --text "何もしてないのに夕方になった。これが才能"
```

**パターンC: 画像付き（猫写真）**

```bash
# 写真を post_scheduler/images/ に配置
cp ~/Pictures/cat_sleeping.jpg ~/pjt/hokke_x/post_scheduler/images/

# 予約
python x_poster.py --schedule "2026-02-19 21:00" --text "本日の業務報告" --image "images/cat_sleeping.jpg"
```

### GitHubにプッシュする

```bash
cd ~/pjt/x_auto
cp ~/pjt/hokke_x/post_scheduler/post_queue.json post_queue.json
cp ~/pjt/hokke_x/scheduled_images/* scheduled_images/
git add post_queue.json scheduled_images/
git commit -m "Schedule: [日付の投稿]"
git push
```

---

## 📊 エンゲージメントを分析する

### 1週間〜1ヶ月ごとに分析

```bash
# Chrome拡張機能でエクスポートしたCSVを使用
cd ~/pjt/hokke_x/analytics
python ~/path/to/csv_analyzer.py --batch-size 20 "hokke_posts_2026-02.csv"

# レポート生成
python ~/path/to/generate_report.py

# レポートを確認
cat ANALYSIS_REPORT.md
```

---

## 📁 ファイルの役割

| ファイル | 役割 |
|---------|------|
| [SYSTEM.md](./SYSTEM.md) | システム全体のドキュメント（必読） |
| [PERSONA.md](./PERSONA.md) | ペルソナ定義（変更不可） |
| [STRATEGY_FINAL.md](./STRATEGY_FINAL.md) | 採用戦略の決定版 |
| `post_scheduler/post_queue.json` | 投稿キュー（GitHub Actionsが読み取り） |
| `content_stock/*.json` | ネタストック |
| `analytics/ANALYSIS_REPORT.md` | 分析レポート |

---

## ⚠️ 注意点

1. **GitHubプッシュ必須** - `post_queue.json` をプッシュしないと予約が有効にならない
2. **画像パス** - 画像は `scheduled_images/` にコピーしてからプッシュ
3. **ホッケの声** - 投稿前に「ホッケっぽいか？」を確認
4. **投稿頻度** - 1日2〜4回（多すぎない）
5. **画像頻度** - 週2〜3枚（無理に毎日撮らない）

---

## 🆘 トラブルシューティング

詳細は [SYSTEM.md](./SYSTEM.md) を参照してください。

**よくある問題:**
- 投稿が反映されない → GitHubにプッシュしていない
- 画像が表示されない → `scheduled_images/` にコピーしていない
- 日本語が中国語フォントになる → プロンプトにフォント指定がない

---

*最終更新: 2026-02-17*
