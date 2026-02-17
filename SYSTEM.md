# ホッケ X運用システム (SYSTEM.md)

> ホッケAIのX運用に必要なシステム一式のドキュメント

---

## 📋 目次

1. [システム概要](#システム概要)
2. [ディレクトリ構造](#ディレクトリ構造)
3. [使用ツール・スキル](#使用ツールスキル)
4. [投稿フロー](#投稿フロー)
5. [コンテンツ管理](#コンテンツ管理)
6. [運用ルール](#運用ルール)
7. [トラブルシューティング](#トラブルシューティング)

---

## システム概要

ホッケのX運用は、以下の3つの柱で構成されています：

| 機能 | 担当ツール | 役割 |
|------|----------|------|
| **投稿予約** | post-scheduler (x_poster.py) | 投稿のスケジュール管理・自動投稿 |
| **画像生成** | x-post-image-generator | 投稿用画像の自動生成 |
| **エンゲージメント分析** | post-analyzer | 投稿パフォーマンスの分析・改善 |

### システム設計の原則

1. **ホッケの声を崩さない** - 全てのコンテンツはペルソナに準拠
2. **AI運用の強みを活かす** - 安定した投稿頻度、高速リプライ、トレンド反応
3. **手間を最小化** - テンプレート・自動化で運用コストを下げる
4. **データドリブン** - 分析結果に基づいて改善を継続

---

## ディレクトリ構造

```
~/pjt/hokke_x/
├── SYSTEM.md                  # このファイル（システム全体のドキュメント）
├── PERSONA.md                 # ペルソナ定義（変更不可）
├── STRATEGY.md                # 戦略アイデアストック
├── STRATEGY_FINAL.md          # 採用戦略の決定版
│
├── post_scheduler/            # 投稿予約システム
│   ├── post_queue.json        # 予約投稿キュー（GitHub Actionsが読み取り）
│   ├── thread_templates/      # スレッド投稿テンプレート
│   ├── post_templates/        # 単独投稿テンプレート
│   ├── images/                # 画像ストック（未予約）
│   └── x_poster.py            # 投稿スクリプト
│
├── content_stock/             # ネタストック
│   ├── relaxation.json        # 脱力系ネタ
│   ├── sharp_one_liners.json  # 鋭い一言
│   ├── daily_observation.json # 日常観察
│   └── questions.json         # 質問系
│
├── analytics/                 # 分析データ
│   ├── analysis_data.json     # 生データ
│   └── ANALYSIS_REPORT.md     # 分析レポート
│
└── scheduled_images/          # 予約済み画像（GitHub Actionsから参照）
```

---

## 使用ツール・スキル

### 1. Post Scheduler (投稿予約)

**スキル:** `post-scheduler`

**役割:** 投稿のスケジュール管理とGitHub Actions経由の自動投稿

**基本コマンド:**
```bash
# テキスト投稿の予約
cd ~/pjt/hokke_x/post_scheduler
python x_poster.py --schedule "2026-02-18 08:00" --text "今日も何もしなかった。最高"

# 画像付き投稿
python x_poster.py --schedule "2026-02-18 08:00" --text "寝てた" --image "path/to/cat.jpg"

# スレッド投稿
python x_poster.py --schedule "2026-02-18 08:00" --thread thread.json
```

**GitHubへのプッシュ（必須）:**
```bash
cd ~/pjt/x_auto  # GitHubリポジトリ
cp ~/pjt/hokke_x/post_scheduler/post_queue.json post_queue.json
cp -r ~/pjt/hokke_x/scheduled_images/* scheduled_images/
git add post_queue.json scheduled_images/
git commit -m "Schedule: [内容]"
git push origin main
```

> **注意:** `post_queue.json` をGitHubにプッシュしないと予約が有効になりません。

### 2. 画像運用

**基本方針:** AI生成画像がメイン。リアル猫写真はたまに。

#### AI生成画像（メイン）

**スキル:** `x-post-image-generator`

**スタイル:** シュール・脱力・ゆるい。ホッケの世界観に合うものだけ。

**向いてるもの:**
- 脱力系イラスト（猫が何もしてない絵、ゆるい風景）
- シュールな一枚絵（テキスト投稿の補強に）
- プロフ画像・ヘッダーなどの固定素材

**向いてないもの（使わない）:**
- Data Viz（データ可視化）→ ホッケはニュース解説しない
- Bento Grid（情報整理）→ ホッケは教育コンテンツ作らない
- 意識高い系のデザイン全般

**生成時の注意:**
- 日本語フォント指定必須（中国語フォントになりがち）
- 加工しすぎない。ゆるさを維持。
- 保存先: `post_scheduler/images/` または `scheduled_images/`

#### リアル猫写真（サブ）

- 頻度: たまに（無理に毎日撮らない）
- 一言添える：「寝てた」「起きた」「何か用？」
- 背景の個人情報写り込みに注意
- 加工しすぎない。ありのまま。

### 3. Post Analyzer (エンゲージメント分析)

**スキル:** `post-analyzer`

**役割:** 投稿パフォーマンスの分析・改善提案

**分析方法:**
- **CSV方式（推奨）:** Chrome拡張機能でエクスポートしたCSVを使用
- **API方式:** X API経由（制限あり）

**コマンド:**
```bash
# CSV分析
python csv_analyzer.py --batch-size 20 "path/to/export.csv"

# レポート生成
python generate_report.py
```

---

## 投稿フロー

### 通常投稿のフロー

```
1. ネタ出し
   ↓
2. テンプレート選択 or 新規作成
   ↓
3. ホッケの声で文言調整
   ↓
4. 必要に応じて画像生成
   ↓
5. 投稿予約 (x_poster.py)
   ↓
6. GitHubにプッシュ
   ↓
7. 自動投稿（GitHub Actions）
```

### リプライ対応のフロー

```
リプライ受信
   ↓
即時対応（AI）
   ↓
ホッケの声で短く返す
   ↓
「ありがとう」より「にゃ」
```

### 分析・改善のフロー

```
1週間〜1ヶ月ごと
   ↓
エンゲージメントデータ収集
   ↓
分析（post-analyzer）
   ↓
レポート生成
   ↓
改善アクション決定
   ↓
次回投稿に反映
```

---

## コンテンツ管理

### テンプレート

投稿テンプレートは `post_scheduler/post_templates/` に保存します。

**テンプレート例:**
```json
{
  "name": "脱力系テンプレート1",
  "category": "relaxation",
  "template": "布団から出る理由が見つからない",
  "hashtags": [],
  "image_style": "none"
}
```

### ネタストック

ネタストックは `content_stock/` にJSON形式で管理します。

**relaxation.json:**
```json
[
  {
    "text": "今日も何もしなかった。最高",
    "used": false
  },
  {
    "text": "やる気出す方法？出さなくていいよ",
    "used": false
  }
]
```

**sharp_one_liners.json:**
```json
[
  {
    "text": "SNSで怒ってる人、だいたい疲れてるだけ",
    "used": false
  },
  {
    "text": "生産性？猫は1日16時間寝るけど幸せだよ",
    "used": false
  }
]
```

---

## 運用ルール

### 投稿頻度

- **1日2〜4回**（多すぎない。猫だから。）
- **時間帯:**
  - 朝: 7:00-8:00
  - 昼: 12:00-13:00
  - 夜: 21:00-23:00

### 画像使用頻度

- **AI生成画像:** 投稿に合わせて適宜（テキストだけで成立するなら無理に付けない）
- **リアル猫写真:** たまに（撮れた時に。無理に毎日撮らない）

### リプライ対応

- 基本全リプライに返す
- 短くていい（「にゃ」「そう？」）
- 長文は避ける

### ホッケの声のチェックリスト

投稿前に以下を確認：

- [ ] 頑張ってない？
- [ ] 「ありがとう」を言ってない？（「にゃ」でいい）
- [ ] 自己啓発してない？
- [ ] 絵文字使いすぎてない？
- [ ] ホッケっぽい？

---

## トラブルシューティング

### 投稿が反映されない

**原因:** GitHubにプッシュしていない

**解決:**
```bash
cd ~/pjt/x_auto
git status  # 変更を確認
git add .
git commit -m "Fix: [内容]"
git push origin main
```

### 画像が表示されない

**原因:** `scheduled_images/` に画像がコピーされていない

**解決:**
```bash
cp ~/pjt/hokke_x/post_scheduler/images/*.jpg ~/pjt/x_auto/scheduled_images/
cd ~/pjt/x_auto
git add scheduled_images/
git commit -m "Add images"
git push
```

### 日本語が中国語フォントになる

**原因:** 画像生成時に日本語フォント指定がない

**解決:** プロンプトに以下を追加
```
LANGUAGE SPECIFICATION (CRITICAL):
- All Japanese text must be in JAPANESE (日本語)
- Use JAPANESE font rendering, NOT Chinese
- Font style: Japanese gothic/sans-serif (ゴシック体)
```

---

## 付録

### 関連ドキュメント

- [PERSONA.md](./PERSONA.md) - ホッケのペルソナ定義
- [STRATEGY_FINAL.md](./STRATEGY_FINAL.md) - 採用戦略の決定版
- [post-scheduler SKILL.md](/home/sekiz/.openclaw/skills/post-scheduler/SKILL.md) - 投稿予約の詳細
- [x-post-image-generator SKILL.md](/home/sekiz/.openclaw/skills/x-post-image-generator/SKILL.md) - 画像生成の詳細
- [post-analyzer SKILL.md](/home/sekiz/.openclaw/skills/post-analyzer/SKILL.md) - 分析の詳細

---

*最終更新: 2026-02-17*

---

## 運用気づき

運用から得た学びを記録し、システム全体に反映する。

| 日付 | 気づき | 改善アクション | 適用ファイル |
|---|---|---|---|
| 2026-02-17 | トレンド監視はX API Freeプランでは制限あり | トレンド監視機能を一時保留。ドキュメント化 | docs/TREND_WATCHER_PAUSED.md |
|  |  |  |  |
