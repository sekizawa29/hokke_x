---
name: hokke-image-generator
description: ホッケ（茶トラ猫AI）のペルソナに合わせた画像を生成するスキル。Nano Banana Proを使用。
version: 1.3
updated: 2026-02-24
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
- テキスト埋め込みは原則なし（Meme系は例外：最小限の英語テキストのみ可）。
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

## 画像カテゴリ一覧

| カテゴリ | テンプレート | 方針 |
|---------|------------|------|
| **リアル猫写真** | A〜D | 北海道の家で暮らす茶トラの日常。写実的。 |
| **猫Meme** | E | 共感・あるある系。最小限のテキスト入り。シェアされやすさ重視。 |
| **猫 vs 人間** | F | 猫と人間の生活の対比。分割構図 or 並列。 |
| **シュール猫** | G | 猫が人間っぽいことをしている非現実な絵。皮肉・哲学的。 |

### リアル猫写真の詳細スタイル

| 投稿タイプ | テンプレート | 方針 |
|-----------|------------|------|
| 日常・つぶやき | A. 窓際・室内 | 北海道の家でまったりしてる情景 |
| シュール・脱力 | B. 脱力コント | 飼い主の机周りやストーブ前など、生活感ある場所 |
| 季節・時間帯 | C/D. 光と空気感 | 北海道の光。雪・緑・夕暮れ。猫はいても映り込む程度 |
| ちょっと鋭いネタ | A or B | シンプルな室内の一角。 |

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

### E. 猫Meme（共感・あるある系）

テキストは最小限（英語の短いフレーズ1行が安定。日本語はツイート本文側に書く）。

```json
{
  "image_type": "Internet meme style photo, bold minimal text overlay, high contrast",
  "time_period_and_year": "Contemporary internet culture",
  "mood_and_vibe": "Relatable, dry humor. The kind of image people screenshot and share. Universally understood cat frustration or sarcasm.",
  "subject": "Orange tabby cat with an exaggerated but natural expression — deadpan stare, side-eye, or dramatic yawn. Close-up face shot.",
  "clothing": "neutral",
  "hair": "Orange tabby fur, expressive whiskers",
  "face": "Exaggerated natural expression: suspicious squint, wide-eyed shock, or utterly bored half-closed eyes",
  "accessories": "neutral",
  "action": "A single clear reaction moment — staring at something off-camera, looking back over shoulder, or lying flat with zero motivation",
  "location": "Simple, uncluttered background. Plain wall, floor, or single-color surface. Background should not compete with the cat or text.",
  "lighting": "Clean, even lighting. Enough contrast for text readability. No dramatic shadows.",
  "camera_angle_and_framing": "Tight face close-up or upper body. Cat fills 3/4 of frame. Space left at top or bottom for text overlay.",
  "camera_equipment": "50mm, f/2.8, sharp focus on face, clean background separation",
  "style": "High contrast, slightly saturated. Clean enough for text overlay to read clearly. Internet-native aesthetic.",
  "text_overlay": "1 short line, max 5 words, bold sans-serif, white with black outline. Place at top or bottom with padding.",
  "negative_prompt": "cluttered background, busy scene, multiple cats, blurry face, low contrast, cursive font, long text, Japanese text, watermark"
}
```

**Memeテキストの例:**
- `Monday.` （猫が死んだ目で横たわってる）
- `no.` （何かを拒否してる顔）
- `Working hard` （PCの前で寝落ちしてる）
- `5 more minutes` （布団から出たくない顔）

### F. 猫 vs 人間（対比・比較）

分割構図で猫と人間の生活を対比させる。

```json
{
  "image_type": "Split comparison image, clean editorial layout, two-panel composition",
  "time_period_and_year": "Contemporary",
  "mood_and_vibe": "Wry comparison between cat life and human life. The cat's side always looks better. Understated humor through visual contrast.",
  "subject": "LEFT panel: orange tabby cat in a relaxed, content state. RIGHT panel: implied human stress or effort (hands on keyboard, messy desk, alarm clock — no face needed).",
  "clothing": "neutral",
  "hair": "Orange tabby fur on cat side",
  "face": "Cat: serene, peaceful, smugly comfortable. Human side: no face shown, just hands or objects implying stress.",
  "accessories": "neutral",
  "action": "Cat: sleeping, stretching, or lounging. Human side: typing frantically, staring at screen, holding coffee desperately.",
  "location": "Both panels in same house interior (Hokkaido house vibe). Cat side is warm and cozy. Human side is cluttered desk area.",
  "lighting": "Cat side: warm, golden, inviting. Human side: slightly cooler, harsher monitor glow or overhead fluorescent feel.",
  "camera_angle_and_framing": "Clean vertical split or diagonal divide. Each side clearly readable. Balanced composition.",
  "camera_equipment": "35mm, f/4, both sides in focus, editorial clarity",
  "style": "Clean, magazine-editorial feel. Slight color temperature difference between panels to emphasize contrast.",
  "negative_prompt": "text, labels, arrows, human face visible, messy layout, unclear split, cartoon, illustration style"
}
```

### G. シュール猫（猫が人間っぽいことをしている）

猫が人間の行為を真似ているシュールな絵。写実ベースで違和感を狙う。

```json
{
  "image_type": "Photorealistic surreal photography, uncanny everyday moment",
  "time_period_and_year": "Contemporary, ordinary setting with one surreal element",
  "mood_and_vibe": "Something is slightly off. A cat is doing a distinctly human activity with complete seriousness. Not cute — deadpan absurd.",
  "subject": "Orange tabby cat performing a human activity with natural posture. The cat should look like it genuinely belongs in the situation.",
  "clothing": "neutral — no costumes. The humor comes from the activity, not dress-up.",
  "hair": "Natural orange tabby fur",
  "face": "Completely serious, focused, professional demeanor. No smile, no cuteness.",
  "accessories": "Only what the activity requires — reading glasses perched on nose, tiny coffee mug nearby, laptop-sized-for-cat",
  "action": "ONE clear human activity: sitting at a desk typing, reading a newspaper, attending a video call, staring at a whiteboard, commuting on a train",
  "location": "Realistic setting appropriate for the activity. Office desk, kitchen table, train seat. Hokkaido house interior preferred when possible.",
  "lighting": "Naturalistic, matches the setting. Office lighting for office scene, morning light for kitchen scene.",
  "camera_angle_and_framing": "Medium shot showing the cat and enough context to understand the activity. Cat is central subject.",
  "camera_equipment": "50mm, f/2.8, sharp subject, slightly blurred background",
  "style": "Photorealistic base with one surreal element (the cat doing human things). Everything else completely normal. The mundanity makes it funnier.",
  "negative_prompt": "cartoon, illustration, anthropomorphic cat standing on two legs, cat wearing clothes, costume, exaggerated proportions, fantasy setting, multiple cats, text, logo"
}
```

**シュール猫のシチュエーション例:**
- PCに向かって真剣にタイピングしている猫
- Zoom会議に参加して無表情の猫
- 新聞を広げて朝食のテーブルについている猫
- ホワイトボードの前でプレゼンしている猫
- 確定申告の書類に囲まれている猫

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

1. 投稿テキストのトーンと狙いを判断
2. 画像カテゴリを選択：

| テキストのトーン | 画像カテゴリ | テンプレート |
|----------------|------------|------------|
| 日常観察・つぶやき | リアル猫写真 | A〜D（季節で選択） |
| 脱力系・眠い系 | リアル猫写真 or 猫Meme | B or E |
| 鋭い一言・皮肉 | シュール猫 or 猫 vs 人間 | G or F |
| 飼い主ネタ | 猫 vs 人間 | F |
| 共感狙い・バズ狙い | 猫Meme | E |

3. テキストに合わせてプロンプトを微調整
4. 生成 → 投稿に添付

### hookCategory との対応（エンゲージメント追跡用）

画像付き投稿時は `hookCategory` に画像カテゴリも含めて記録する。

- `猫写真` — リアル猫写真（A〜D）
- `猫Meme` — Meme系（E）
- `猫vs人間` — 対比系（F）
- `シュール猫` — シュール系（G）

---

## 品質チェック

### 全カテゴリ共通
- ホッケのペルソナと合っているか（脱力・シュール・北海道の家感）
- 猫が茶トラであるか
- 意図しないテキスト・ロゴ・ウォーターマークが混入していないか

### リアル猫写真（A〜D）
- **猫がフレームの2/3以上を占めているか**（最重要）
- **背景がボケていて、間取りや家具配置が判別できないか**
- 北海道・年収500万の生活感から外れていないか（豪華すぎ・小綺麗すぎ NG）
- 複数枚並べても間取りの矛盾を感じないか

### 猫Meme（E）
- テキストが読めるか（フォント・コントラスト）
- テキストは英語の短フレーズか（5語以内）
- 猫の表情がテキストの感情と合っているか
- 背景がシンプルでテキストを邪魔していないか

### 猫 vs 人間（F）
- 分割が明確で、両パネルの内容が一目で理解できるか
- 人間の顔が映っていないか（手・後ろ姿・物だけで表現）
- 対比のユーモアが伝わるか

### シュール猫（G）
- 猫が衣装を着ていないか（コスプレNG。状況で語る）
- 二足歩行になっていないか（四足のまま人間の行動をしている）
- 「一見リアル、よく見ると猫がおかしい」のバランスか

## 間取り図の使い方

`docs/Room_1F.png` / `docs/Room_2F.png` に家の間取り図がある。

- `--input-image` で参照画像として渡せる
- 間取り図は**猫がどの部屋にいるかの文脈設定**に使う
- 間取りの再現ではなく、その部屋にありそうな小物・光・空気感をヒントにする
- 背景はボケ処理で曖昧にするため、間取りの正確な再現は不要
