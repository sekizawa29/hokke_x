---
name: hokke-fetch-candidates
description: リプライ候補ツイートを検索・取得するスキル。generate_reply_dashboard.py を実行してリプライ対象を収集する。「リプライ候補取得」「対象ツイート検索」「候補を集めて」「fetch candidates」と言われたとき、またはリプライ作業の前に候補が必要なときに使う。
version: 1.0
updated: 2026-02-26
---

# リプライ候補取得スキル

X上のツイートを検索し、ホッケがリプライすべき候補を収集する。

## 手順

### 1. 既存候補の確認（必須）

実行前に必ず既存の候補数を確認する。これをスキップしてはいけない。

```bash
python3 -c "
import json
from pathlib import Path
f = Path('dashboard/reply_candidates.json')
if f.exists():
    d = json.loads(f.read_text())
    print(f'既存候補: {len(d)}件')
else:
    print('既存候補: 0件（ファイルなし）')
"
```

- **10件以上ある場合** → 「既に十分な候補があります（N件）。追加取得しますか？」とユーザーに確認する。明示的に追加を求められた場合のみ Step 2 に進む
- **10件未満の場合** → Step 2 に進む

### 2. 候補の取得

```bash
cd ~/pjt/hokke_x
python3 reply_system/generate_reply_dashboard.py --queries 2
```

- `--queries`: 検索するキーワード数（デフォルト3、通常は2で十分）
- `--per-query`: キーワードあたりの検索件数（デフォルト10）
- 検索キーワードは `reply_system/search_config.json` の7カテゴリ28語からランダムに選ばれる
- 既存候補との重複は `tweet_id` で自動排除される

### 3. 結果の確認

取得後、候補数とカテゴリ内訳を報告する。

```bash
python3 -c "
import json
from pathlib import Path
from collections import Counter
f = Path('dashboard/reply_candidates.json')
d = json.loads(f.read_text())
cats = Counter(c.get('category', '不明') for c in d)
print(f'合計: {len(d)}件')
for cat, n in cats.most_common():
    print(f'  {cat}: {n}件')
"
```

## 注意事項

- このスキルは候補の「取得」のみ行う。実際のリプライ投稿は `hokke-reply-browser` スキルまたは `orchestrator.py` で行う
- 検索にはX APIを使用するため、レート制限に注意（短時間に何度も実行しない）
- 候補は `dashboard/reply_candidates.json` に追記保存される（上書きではない）
