---
name: hokke-image-generator
description: ホッケ（茶トラ猫AI）のペルソナに合わせた画像を生成するスキル。Nano Banana Proを使用。
version: 1.1
updated: 2026-02-20
---

# hokke-image-generator

ホッケのX投稿用画像を生成する。ペルソナに沿ったビジュアルを Nano Banana Pro (Gemini) で生成。

---

## 家ペルソナ（固定設定・必ず参照）

ホッケが住む家の設定。画像生成時はこの設定を軸にプロンプトを組む。

- **場所:** 北海道の地方都市近郊（札幌ではない）
- **家:** 築30年前後の一軒家。2階建て3LDK。
- **年収感:** 500万円前後。ニトリ家具・古めの家電・手入れが雑な庭。
- **暖房:** FF式灯油ストーブ（冬は必須）。窓は二重窓。冬に結露する。
- **床:** フローリングと古びた畳が混在。
- **ホッケの定位置:** 和室に面した窓際の廊下スペース（縁側的に使ってる）。
- **飼い主エリア:** リビング隅のPC机コーナー。ケーブルが散らかってる。コーヒーマグあり。
- **庭:** そこそこ広いが手入れは適当。錆びた物置あり。

### 季節ごとの外の様子

| 季節 | 外の様子 |
|------|---------|
| 冬（11〜3月） | 雪が積もってる。静か。白い。 |
| 春（4〜5月） | 雪解けでぬかるんでる。急に緑が戻る。 |
| 夏（6〜8月） | 短い。涼しい。窓全開。扇風機。 |
| 秋（9〜10月） | 落ち葉。急に寒くなる。 |

---

## 基本方針

- 説明しすぎない。雰囲気で語る。
- ごちゃごちゃしない。余白を大事にする。
- テキスト埋め込みは原則なし。
- 「なんかいいな」と思わせる画像が正解。
- 裕福すぎる家・小綺麗すぎるインテリアにしない。

---

## スタイル選択

| 投稿タイプ | スタイル | 方針 |
|-----------|---------|------|
| 日常・つぶやき | 窓際・室内 | 北海道の家でまったりしてる情景 |
| シュール・脱力 | 脱力コント | 飼い主の机周りやストーブ前など、生活感ある場所 |
| 季節・時間帯 | 光と空気感 | 北海道の光。雪・緑・夕暮れ。猫はいても映り込む程度 |
| ちょっと鋭いネタ | ミニマル | シンプルな室内の一角。 |

---

## プロンプトテンプレート

### A. 窓際・室内（基本）

```json
{
  "image_type": "Lifestyle photography, warm everyday moment, film grain aesthetic",
  "time_period_and_year": "Contemporary, timeless casual feel",
  "mood_and_vibe": "Quiet northern Japan afternoon. Slow, unhurried, slightly cold outside, warm inside.",
  "subject": "Orange tabby cat (茶トラ), relaxed posture, not looking at camera",
  "clothing": "neutral",
  "hair": "Short dense fur, warm orange and cream tabby stripes",
  "face": "Neutral expression, half-closed eyes, unbothered",
  "accessories": "neutral",
  "action": "Sitting or lying at the window-side hallway, looking outside, tail loosely curled",
  "location": "Interior of an older Japanese house in Hokkaido. Double-pane windows with slight condensation. Old wooden floor, faded tatami visible in adjacent room. Low winter light coming through.",
  "lighting": "Soft diffused daylight through double-pane window, cool 4500K, subtle shadows. Northern Japan light — not harsh, slightly grey.",
  "camera_angle_and_framing": "Low angle, candid, cat fills 1/3 of frame, room and window dominant",
  "camera_equipment": "35mm film camera feel, f/2.0, slight vignette, fine grain",
  "style": "Muted cool tones, aged wood, faded fabric, lived-in domestic feel. Not Instagram-pretty.",
  "negative_prompt": "posed, looking at camera, luxury interior, new furniture, bright colors, text, logo, studio lighting"
}
```

### B. 脱力コント（生活感・飼い主の机周り）

```json
{
  "image_type": "Candid photography, slightly surreal everyday moment",
  "time_period_and_year": "Contemporary, ordinary weekday feel",
  "mood_and_vibe": "Dry humor. The cat is clearly unimpressed. Something mundane is happening but the cat doesn't care.",
  "subject": "Orange tabby cat, completely unbothered expression",
  "clothing": "neutral",
  "hair": "Short tabby fur, orange and cream",
  "face": "Deadpan, thousand-yard stare, zero emotion",
  "accessories": "neutral",
  "action": "Sitting next to tangled cables on a desk, or near a noisy oil heater, or on top of a pile of unfolded laundry",
  "location": "Hokkaido house interior. Living room corner with a cluttered PC desk — multiple cables, a cold coffee mug, random papers. FF oil heater visible in background. NITORI-style furniture.",
  "lighting": "Neutral indoor lighting, overcast daylight from double-pane window, slightly flat",
  "camera_angle_and_framing": "Eye-level with cat, environment visible, cat center-left",
  "camera_equipment": "Standard zoom lens, f/4, nothing fancy",
  "style": "Flat, documentary. Slightly desaturated. Lived-in messiness is the point.",
  "negative_prompt": "cute poses, cartoon, exaggerated reactions, luxury items, clean desk, bright colors, dramatic lighting, text"
}
```

### C. 北海道の光と季節感（冬）

```json
{
  "image_type": "Atmospheric photography, mood-driven, minimal subject",
  "time_period_and_year": "Timeless, Hokkaido seasonal moment",
  "mood_and_vibe": "The particular quiet of a Hokkaido winter afternoon. Time moves slowly. Cold outside, warm inside.",
  "subject": "Orange tabby cat silhouette or partial view, not the main subject",
  "clothing": "neutral",
  "hair": "Fur catching cold window light",
  "face": "Not visible or in shadow",
  "accessories": "neutral",
  "action": "Sitting at double-pane window watching snowfall outside, breath slightly fogging the glass",
  "location": "Hokkaido house window interior. Snow-covered garden visible outside — modest yard, an old rusted storage shed in the corner, sparse trees. Inside: wooden window frame, old curtain.",
  "lighting": "Flat cold daylight from overcast Hokkaido winter sky. Cool 5000K. Interior slightly warm from oil heater.",
  "camera_angle_and_framing": "Cat in silhouette against window, snow visible outside, wide enough to feel the room",
  "camera_equipment": "50mm, f/1.8, bokeh background",
  "style": "Cool blues outside, warm amber inside. High contrast between cold window and warm room. Film look.",
  "negative_prompt": "busy composition, cute expression, luxury interior, southern Japan scenery, cherry blossoms, text, logo"
}
```

### D. 夏（北海道の短い夏）

```json
{
  "image_type": "Candid lifestyle photography, summer mood",
  "time_period_and_year": "Contemporary Hokkaido summer, brief and precious",
  "mood_and_vibe": "Unusually warm day for Hokkaido. Windows wide open. Electric fan running. The cat is mildly bothered by the heat but managing.",
  "subject": "Orange tabby cat, slightly sprawled, not looking at camera",
  "clothing": "neutral",
  "hair": "Short tabby fur looking slightly ruffled",
  "face": "Mild discomfort, narrowed eyes",
  "accessories": "neutral",
  "action": "Lying flat on cool wooden floor near open window, electric fan visible in background",
  "location": "Hokkaido house interior, summer. Windows fully open — no AC unit visible. Electric fan (扇風機) on floor. Green garden visible outside through open window. Modest interior.",
  "lighting": "Bright summer daylight, warm 5500K, natural shadows",
  "camera_angle_and_framing": "Low angle looking up slightly, cat sprawled across frame, fan and window in background",
  "camera_equipment": "35mm film, f/2.8, slight overexposure",
  "style": "Warm but not glamorous. The particular flatness of a Hokkaido summer day.",
  "negative_prompt": "AC unit, luxury interior, posed cat, cute expression, text, logo"
}
```

---

## 実行方法

```bash
GEMINI_API_KEY=$(grep GEMINI_API_KEY /home/sekiz/pjt/x_auto/.env | cut -d= -f2) \
uv run ~/.nvm/versions/node/v24.13.0/lib/node_modules/openclaw/skills/nano-banana-pro/scripts/generate_image.py \
  --prompt '<JSON>' \
  --filename "$(date +%Y-%m-%d-%H-%M-%S)-hokke.png" \
  --resolution 2K
```

生成後は `MEDIA:` 行のパスを確認して投稿する。

---

## 投稿との組み合わせ

1. 投稿テキストのトーンを判断（日常 / シュール / 冬 / 夏）
2. 今の季節を確認してテンプレートを選択（A〜D）
3. テキストに合わせてプロンプトを微調整（場所・行動・状況）
4. 生成 → 投稿に添付

---

## 品質チェック

- 猫が主役になりすぎていないか（雰囲気が主役）
- テキスト・ロゴが混入していないか
- 北海道・年収500万の生活感から外れていないか（豪華すぎ・小綺麗すぎ NG）
- ホッケのペルソナと合っているか（脱力・シュール・北海道の家感）
