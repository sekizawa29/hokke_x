# 通知実装ガイド

## 方針

Discord通知は共通モジュール `notifications/discord_notifier.py` を使う。
新しい通知処理を追加する時は、Webhookへの直接実装を各所に書かず、このモジュール経由に統一する。

## 共通モジュールの使い方

```python
from notifications.discord_notifier import DiscordNotifier

notifier = DiscordNotifier.from_env("DISCORD_WEBHOOK_COST")
res = notifier.send("通知本文", username="X Cost Reporter")
if not res.ok:
    raise RuntimeError(res.error)
```

## 日次コスト通知

```bash
# 昨日分をDiscordへ通知
python3 analytics/daily_cost_report.py --yesterday --notify-discord
```

必要な環境変数:
- `DISCORD_WEBHOOK_COST`

## 投稿通知

`x_poster.py`（`x_cli.py post` 経由含む）は投稿成功時にDiscord通知を送る。
未設定なら通知はスキップし、投稿処理は継続する。

必要な環境変数:
- `DISCORD_WEBHOOK_POST`

## リプライ通知

`x_cli.py reply run --notify-discord` は実行結果をEmbed形式でDiscord通知する。
`exit_code != 0` の失敗結果も通知対象。さらに実行ラッパー側の例外発生時もエラー通知する。
通知失敗でもリプライ実行結果は保持される。

```bash
python3 x_cli.py reply run --notify-discord
```

必要な環境変数:
- `DISCORD_WEBHOOK_REPLY`

## 通知単体テスト

ジョブ本体（投稿/リプライ）を実行せずに通知だけ確認したい場合は以下を使う。

```bash
python3 scripts/send_discord_test.py --env DISCORD_WEBHOOK_REPLY
```
