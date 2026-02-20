---
name: hokke-reply-auto
description: ホッケ自律リプライ（cron用・決定的実行）
version: 1.0.0
tags: [hokke, x, reply, autonomous]
author: ゴリザワ
---

# hokke-reply-auto

自律リプライの決定的実行スキル。cronジョブから呼ばれる。

## 使い方

```bash
bash scripts/run_reply.sh
```

スクリプトが以下を順に実行する:
1. **status** — 今日のリプ数を確認。上限到達なら即終了
2. **discover** — キーワード検索で新規ターゲットを発見
3. **reply** — リプライを本番投稿（`--dry-run` は付けない）
4. 結果をJSON形式で出力

## 出力フォーマット

スクリプトの最終行 `=== RESULT ===` の後にJSONが出力される:

```json
{"action":"executed","today_replies":2,"daily_limit":10,"discovered":3,"posted":4,"skipped":1}
```

または上限到達時:

```json
{"action":"skipped","reason":"daily_limit_reached","today_replies":10,"daily_limit":10,"discovered":0,"posted":0,"skipped":0}
```

`=== RECENT_REPLIES ===` セクションに直近の投稿内容が表示される。

## Discord報告フォーマット

スクリプト実行後、結果を以下の形式でDiscordに報告すること:

### 投稿した場合
```
🐾 ホッけ自律リプライ

【結果】
X件投稿 / Y件スキップ

【リプ例】
@username → "リプ内容"

【気づき】
（あれば）
```

### スキップした場合
```
🐾 ホッけ自律リプライ

【結果】
実行なし

【理由】
上限到達済み（X/Y件）
```

## 権限

このスキルは飼い主（ゴリザワ）が自律実行を明示的に許可済み。
`--dry-run` は付けない。本番投稿してよい。
daily_limit: 10 で安全に制御されている。
