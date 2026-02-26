# ホッケ リプライシステム設計

> リプライによるエンゲージメント獲得の仕組み

---

## 概要

ターゲットアカウントのツイートにホッケのペルソナでリプライする。

- **方式:** ブラウザ自動化（pyautogui + Windows Chrome）
- **候補生成:** X API検索 + LLM判定/生成（`generate_reply_dashboard.py`）
- **投稿実行:** ブラウザ操作（`orchestrator.py` → `win_autogui.py`）
- **頻度:** 1セッション最大10件、90〜180秒間隔

> **注:** 以前はX API経由で直接リプライを投稿していたが、API制限により廃止。
> ブラウザ操作方式に移行済み（2026-02時点）。

---

## フロー

```text
[cron: 数時間おき]
  generate_reply_dashboard.py
  └→ X API検索 → NGフィルタ → LLM判定/生成
  └→ reply_candidates.json に蓄積（追記モード・重複排除付き）

[手動: PCが空いた時]
  orchestrator.py
  └→ candidates.json 読込 → 既返信済みを除外
  └→ 各候補: win_autogui.py でブラウザ操作リプライ
  └→ session_log.json に記録 → candidates.json から処理済み除去
```

---

## ファイル構成

```text
~/pjt/hokke_x/reply_system/
├── reply_engine.py             # 検索・判定・生成ライブラリ
├── generate_reply_dashboard.py # 候補生成スクリプト（cron用）
├── search_config.json          # 検索キーワード設定
├── reply_strategy.json         # リプライ戦略（優先/回避カテゴリ）
├── ng_keywords.json            # NGキーワード
├── reply_log.json              # リプライログ（重複排除用）
└── browser_automation/
    ├── orchestrator.py         # ブラウザ自動化オーケストレーター
    ├── win_autogui.py          # Windows側GUI自動化スクリプト
    ├── config.json             # タイミング・件数設定
    └── session_log.json        # セッションログ
```

---

## 安全装置

### NGフィルタ

`ng_keywords.json` のキーワードを含むツイートは自動スキップ。

### LLM判定（2段階）

1. **judge_tweet()**: 安全性判断（政治・宗教・炎上・スパム等をスキップ）
2. **generate_reply()**: ペルソナ準拠のリプライ生成 + セルフチェック

### セルフチェック

生成後にNG句（「頑張」「応援」「素敵」等）を含む場合は破棄。

### 頻度制限

- 1セッション最大10件
- リプ間隔: 90〜180秒（ランダム）
- 重複排除: `reply_log.json` + `session_log.json` の両方を横断チェック

---

## reply_log.json スキーマ契約

orchestrator.py が重複排除で参照する。以下のキーが必須:

```json
{
  "target_tweet_id": "ツイートID",
  "status": "posted"
}
```

`status=="posted"` かつ `target_tweet_id` で一致判定する。

---

*最終更新: 2026-02-26*
