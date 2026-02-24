# X API コスト最適化メモ

## 現状コスト（2026-02-21 実績）

| 種別 | 費用 | 内容 |
|------|------|------|
| user_read | $0.68 | `GET /2/tweets/search/recent` + `includes.users` |
| post_read | $0.35 | `GET /2/tweets/search/recent` (通常検索) |
| content_create | $0.24 | リプライ投稿21件 + 通常投稿3件 |
| **合計** | **$1.27** | |

コストの81%（$1.03）がツイート検索。最大の要因は `includes.users` 付き検索。

---

## 課題：`includes.users` の削除

### 現在の使用箇所

**`discover_targets()`**
- `username` → 自分除外・ターゲットリストに保存
- `followers_count` → フォロワー数フィルタ

**`run_reply_session()`**
- `username` → スキップカテゴリ判定・当日リプ済みチェック・ログ記録
- `followers_count` → min/max_followers フィルタ

### 削除した場合の弊害

1. **フォロワーフィルタが効かなくなる**（最大の問題）
   - ボット・フォロワー0・超大手有名人へのリプライが混入するリスク

2. **スキップカテゴリ判定が壊れる**
   - 現在 `username` ベースで判定しているため、`author_id` ベースに変換が必要

### 推奨対応案：ターゲットリスト限定リプライ

- `discover_targets()` で事前収集した `author_id` と検索結果をマッチング
- リスト外の `author_id` はスキップ
- 効果：`includes.users` 不要 かつ フォロワー品質も担保
- 削減額：約 $0.68/日

### 対応ステータス

- [ ] `run_reply_session()` をターゲットリスト限定に変更
- [ ] スキップカテゴリ判定を `author_id` ベースに変換
- [ ] `includes.users` パラメータを検索から除去
