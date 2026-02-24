---
name: hokke-image-generator
description: ホッケ（茶トラ猫AI）のペルソナに合わせた画像を生成するスキル。Nano Banana Proを使用。
version: 1.2
updated: 2026-02-23
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

### 構図の鉄則：猫主役・背景控えめ

**何枚生成しても間取りに違和感を覚えさせないこと**が最優先。

- **猫がフレームの2/3以上を占める**構図にする。猫に寄る。
- 背景は**ボケ処理**で曖昧にする（f/1.4〜f/2.0の浅い被写界深度）。
- 背景に映るのは「なんとなく北海道の家っぽい空気感」程度でOK。
  - 窓の光、フローリングの質感、ストーブのオレンジの灯り、畳の色味 etc.
  - 家具や部屋の全体像は映さない。
- 間取り図は**猫がどの場所にいるかの文脈設定**として参照する。背景の再現素材ではない。
- 広角で部屋全体を見せるワイドショットは原則NG。

#### 良い構図の例
- 猫の顔〜上半身アップ、背景にストーブの灯りがぼんやり
- 窓際で丸くなっている猫、窓の光がボケて差し込む
- 飼い主の机の上で寝ている猫のアップ、ケーブルが少しだけ見える

#### 悪い構図の例
- 部屋の全景が映っていて猫が1/3以下
- 家具の配置や間取りがはっきり分かるワイドショット
- 複数の部屋が同時に見えるような引きの構図

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
  "subject": "Orange tabby cat (茶トラ), relaxed posture, not looking at camera. Close-up, cat fills most of the frame.",
  "clothing": "neutral",
  "hair": "Short dense fur, warm orange and cream tabby stripes",
  "face": "Neutral expression, half-closed eyes, unbothered",
  "accessories": "neutral",
  "action": "Sitting or lying at the window-side hallway, looking outside, tail loosely curled",
  "location": "Interior of an older Japanese house in Hokkaido. Background heavily blurred — only hints of double-pane window light, old wooden floor texture, faded colors.",
  "lighting": "Soft diffused daylight through double-pane window, cool 4500K, subtle shadows on cat's fur. Northern Japan light — not harsh, slightly grey.",
  "camera_angle_and_framing": "Close-up, low angle, cat fills 2/3 of frame. Background is soft bokeh — room details barely discernible.",
  "camera_equipment": "85mm portrait lens, f/1.4, shallow depth of field, heavy background bokeh, slight vignette, fine grain",
  "style": "Muted cool tones, lived-in domestic feel suggested through light and texture only. Not Instagram-pretty.",
  "negative_prompt": "wide shot, full room visible, furniture in focus, posed, looking at camera, luxury interior, new furniture, bright colors, text, logo, studio lighting"
}
```

### B. 脱力コント（生活感・飼い主の机周り）

```json
{
  "image_type": "Candid photography, slightly surreal everyday moment",
  "time_period_and_year": "Contemporary, ordinary weekday feel",
  "mood_and_vibe": "Dry humor. The cat is clearly unimpressed. Something mundane is happening but the cat doesn't care.",
  "subject": "Orange tabby cat, completely unbothered expression. Close-up portrait, cat is the dominant subject.",
  "clothing": "neutral",
  "hair": "Short tabby fur, orange and cream",
  "face": "Deadpan, thousand-yard stare, zero emotion",
  "accessories": "neutral",
  "action": "Sitting next to tangled cables, or near an oil heater, chin resting on paws",
  "location": "Hokkaido house interior. Background out of focus — just hints of cluttered desk, cables, a coffee mug, warm heater glow. All blurred.",
  "lighting": "Neutral indoor lighting, overcast daylight from window, slightly flat, focused on cat's face",
  "camera_angle_and_framing": "Eye-level close-up with cat, cat fills 2/3 of frame, background is blurred bokeh",
  "camera_equipment": "85mm, f/1.8, shallow depth of field, background bokeh",
  "style": "Flat, documentary. Slightly desaturated. Domestic mess hinted at through blurred background only.",
  "negative_prompt": "wide shot, full room visible, furniture layout visible, cute poses, cartoon, exaggerated reactions, luxury items, clean desk, bright colors, dramatic lighting, text"
}
```

### C. 北海道の光と季節感（冬）

```json
{
  "image_type": "Atmospheric close-up photography, mood-driven",
  "time_period_and_year": "Timeless, Hokkaido seasonal moment",
  "mood_and_vibe": "The particular quiet of a Hokkaido winter afternoon. Time moves slowly. Cold outside, warm inside.",
  "subject": "Orange tabby cat close-up, fur lit by cold window light, contemplative",
  "clothing": "neutral",
  "hair": "Fur catching cold window light, individual hairs visible",
  "face": "Calm, slightly squinting, looking toward window",
  "accessories": "neutral",
  "action": "Sitting at window, face and upper body close-up, faint condensation on glass in blurred background",
  "location": "Hokkaido house window. Background is heavily bokeh — just cold white light from window, vague snow outside, warm amber tones from room interior.",
  "lighting": "Flat cold daylight from overcast Hokkaido winter sky on cat's face. Cool 5000K. Faint warm glow from behind (oil heater).",
  "camera_angle_and_framing": "Close-up portrait of cat against window light. Cat fills 2/3 of frame. Window is blurred bright background.",
  "camera_equipment": "85mm, f/1.4, heavy bokeh, film look",
  "style": "Cool blues from window, warm amber from room. Contrast visible on cat's fur. Film grain.",
  "negative_prompt": "wide shot, full room visible, garden detail in focus, busy composition, luxury interior, southern Japan scenery, cherry blossoms, text, logo"
}
```

### D. 夏（北海道の短い夏）

```json
{
  "image_type": "Candid lifestyle close-up photography, summer mood",
  "time_period_and_year": "Contemporary Hokkaido summer, brief and precious",
  "mood_and_vibe": "Unusually warm day for Hokkaido. The cat is mildly bothered by the heat but managing.",
  "subject": "Orange tabby cat close-up, slightly sprawled, not looking at camera",
  "clothing": "neutral",
  "hair": "Short tabby fur looking slightly ruffled, warm light on fur",
  "face": "Mild discomfort, narrowed eyes, close-up expression",
  "accessories": "neutral",
  "action": "Lying flat, chin on floor, face close to camera. Breeze from open window suggested by fur movement.",
  "location": "Hokkaido house interior, summer. Background blurred — just bright open window light, hint of green outside, maybe edge of electric fan. All soft bokeh.",
  "lighting": "Bright summer daylight, warm 5500K, natural shadows on cat's face",
  "camera_angle_and_framing": "Very low angle, face-level with cat on floor, close-up. Cat fills 2/3 of frame. Background is bright bokeh.",
  "camera_equipment": "85mm, f/1.4, shallow depth of field, slight overexposure",
  "style": "Warm but not glamorous. Hokkaido summer light on cat's fur is the focus.",
  "negative_prompt": "wide shot, full room visible, AC unit, luxury interior, posed cat, cute expression, text, logo"
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

- **猫がフレームの2/3以上を占めているか**（最重要）
- **背景がボケていて、間取りや家具配置が判別できないか**
- テキスト・ロゴが混入していないか
- 北海道・年収500万の生活感から外れていないか（豪華すぎ・小綺麗すぎ NG）
- ホッケのペルソナと合っているか（脱力・シュール・北海道の家感）
- 複数枚並べても間取りの矛盾を感じないか

## 間取り図の使い方

`docs/Room_1F.png` / `docs/Room_2F.png` に家の間取り図がある。

- `--input-image` で参照画像として渡せる
- 間取り図は**猫がどの部屋にいるかの文脈設定**に使う
- 間取りの再現ではなく、その部屋にありそうな小物・光・空気感をヒントにする
- 背景はボケ処理で曖昧にするため、間取りの正確な再現は不要
