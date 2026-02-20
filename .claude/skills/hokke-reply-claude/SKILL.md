---
name: hokke-reply-claude
description: ホッケ(@cat_hokke)のClaude直接リプライスキル。DeepSeekではなくClaude自身がリプライ文を生成して投稿する。インタラクティブ実行向け。
version: 1.0
updated: 2026-02-19
---

# ホッケ Claude直接リプライスキル

**テキスト生成はClaude自身が行う。anthropicパッケージ・DeepSeek API不要。**

---

## 手順

### 1. ターゲット発見（任意）

新規ターゲットを補充したい場合のみ実行：

```bash
cd ~/pjt/hokke_x
python3 x_cli.py reply discover
```

### 2. ツイート候補を取得

```bash
cd ~/pjt/hokke_x
python3 x_cli.py reply candidates
```

JSON出力例：
```json
{
  "today_count": 3,
  "daily_limit": 10,
  "remaining": 7,
  "candidates": [
    {
      "username": "xxx",
      "user_id": "123",
      "category": "脱力系",
      "tweet_id": "456",
      "tweet_text": "今日も疲れた"
    }
  ]
}
```

`remaining: 0` または `error: daily_limit_reached` の場合は終了。

### 3. Claudeがリプライ文を生成

candidates の各ツイートに対してPERSONA.mdのルールに従い生成する。

**リプライのルール:**
- 1〜2文、最大80文字
- 一人称は「僕」か使わない（「俺」「私」NG）
- 「〜にゃ」NG
- 絵文字は0〜1個
- 「すごい」「わかる」だけの薄いリプはしない
- 相手のツイートを受けてホッケ視点で一言
- 攻撃的にならない。でも媚びない。

**スキップ判断（以下はリプライしない）:**
- 政治・宗教・炎上系
- 勧誘・スパム系
- リプライしても意味がない内容（URL貼っただけ等）

### 4. 投稿 + ログ記録

候補1件ずつ以下を実行：

```bash
cd ~/pjt/hokke_x
python3 x_cli.py reply post-claude \
  --tweet-id "<tweet_id>" \
  --username "<username>" \
  --tweet-text "<tweet_text>" \
  --reply-text "<生成したリプライ>" \
  --category "<category>"
```

### 5. 結果報告

全件完了後、以下の形式で報告：

```
【ホッケ Claudeリプライ】

X件投稿 / Y件スキップ

【リプ例】
@username → "リプライ内容"
（最大3件）

【気づき】
（ペルソナのブレや改善点があれば）
```

---

## 注意

- 1日の上限は `config.json` の `daily_reply_limit`（現在10件）
- 既にリプ済みのアカウントは `python3 x_cli.py reply candidates` が自動除外
- スキップしたツイートはログに記録不要（投稿しなかったものは残さない）
