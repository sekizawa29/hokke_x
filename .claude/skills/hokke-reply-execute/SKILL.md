---
name: hokke-reply-execute
description: ホッケ(@cat_hokke)のリプライ一括実行スキル。orchestrator.py を使ってreply_candidates.jsonの候補に対しブラウザ自動化でリプライを投稿する。「リプライ実行」「リプライ投稿して」「候補にリプライして」「reply execute」と言われたときに使う。
version: 1.0
updated: 2026-02-26
---

# リプライ一括実行スキル

reply_candidates.json にある候補ツイートに対し、orchestrator.py（pyautogui）でブラウザ操作リプライを自動実行する。

## 前提条件

- Windows側でChromeが開いていること（pyautoguiがブラウザを操作する）
- `dashboard/reply_candidates.json` に候補があること（なければ `hokke-fetch-candidates` スキルで先に取得する）

## 手順

### 1. 候補の確認（必須）

実行前に必ず候補数を確認する。

```bash
python3 -c "
import json
from pathlib import Path
f = Path('dashboard/reply_candidates.json')
if not f.exists():
    print('候補ファイルなし。hokke-fetch-candidates で取得してください')
else:
    d = json.loads(f.read_text())
    print(f'候補: {len(d)}件')
    for i, c in enumerate(d[:5]):
        print(f'  [{i+1}] @{c.get(\"username\",\"?\")} ({c.get(\"category\",\"?\")}) - {c.get(\"tweet_text\",\"\")[:60]}...')
    if len(d) > 5:
        print(f'  ... 他{len(d)-5}件')
"
```

- 候補が0件なら `hokke-fetch-candidates` スキルで取得を促す
- 件数と内容をユーザーに報告し、何件実行するか確認する

### 2. 実行

ユーザーが指定した件数で実行する。件数指定がなければ確認する。

```bash
cd ~/pjt/hokke_x
python3 reply_system/browser_automation/orchestrator.py --no-confirm --limit <件数>
```

- `--limit`: 処理件数（ユーザー指定）
- `--no-confirm`: 各候補の確認プロンプトをスキップ
- `--dry-run`: テスト実行（実際には投稿しない）。ユーザーが求めた場合に使う
- 待機時間は90-180秒/件。5件で約10分かかる

### 3. 結果の報告

実行後、成功/失敗を一覧で報告する。

報告に含める内容:
- 各候補の相手ユーザー名、リプライ内容、成功/失敗
- 失敗があった場合はエラー理由（画像認識エラー等）
- 残り候補数

### 4. 失敗候補の対応

失敗した候補がある場合:
- ツイートURLをユーザーに共有する（`https://x.com/{username}/status/{tweet_id}`）
- リンク切れ（削除済みツイート）の場合、ユーザーの指示があれば候補から削除する:

```bash
python3 -c "
import json
from pathlib import Path
f = Path('dashboard/reply_candidates.json')
d = json.loads(f.read_text())
d = [c for c in d if c.get('tweet_id') != '<tweet_id>']
f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(f'削除完了。残り{len(d)}件')
"
```

## 注意事項

- 短時間に大量実行するとXの制限を受ける可能性がある。1セッション10件以内が目安
- 候補は古い順（generated_at順）に処理される
- 成功した候補は自動的にreply_candidates.jsonから除外される
