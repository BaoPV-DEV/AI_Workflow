# Character spec (cast/<id>.json)

One JSON file per character. `scripts/hero3d/make_character.py` validates it and builds the 3D character with
`build_character.py`: a MakeHuman CC0 body, generated clothes, procedural strand hair, and Blender Cycles renders.

## 1. Schema

```json
{
  "id": "mia",                       // letters/digits/_ ; folder name of the sprites
  "name": "Mia",
  "role": "Field botanist shrunk to ant size in her garden",
  "why": "one line: how the look serves the topic (setting, contrast with backgrounds, genre cue)",
  "seed": 7,                         // hair/brow randomness; change for a different look with the same spec
  "body": {
    "gender": 0.0,                   // 0 female … 1 male (in-between allowed)
    "age_years": 29,                 // 1–90 (or "age": 0–1, MakeHuman scale)
    "muscle": 0.55, "weight": 0.42,  // 0–1, 0.5 = average
    "height": 0.5,                   // 0–1, 0.5 = average for gender/age
    "proportions": 0.75,             // 0.5 neutral, 1 idealised, 0 uncommon
    "ethnicity": {"asian": 0.5, "caucasian": 0.3, "african": 0.2},   // MakeHuman's three blend poles
    "targets": {"nose/nose-scale-horiz-incr.target.gz": 0.4}         // optional extra MPFB targets (path under data/targets)
  },
  "skin":  {"tone": "#c99a7c", "blush": 0.6, "lips": "#a4605a"},
  "eyes":  {"iris": "#4a3020"},
  "hair":  {"style": "ponytail", "color": "#2a1a10", "length": 1.0, "density": 1.0, "part": 0.025, "hairline": 0.0},
  "brows": true, "brow_color": "#20140c",
  "outfit": {
    "top":    {"type": "field jacket", "length": "hip", "sleeves": "long", "collar": "high", "hood": false,
               "material": "nylon", "color": "#55623f", "looseness": 0.012, "zip": true, "seams": true,
               "flare": 0.16, "stripes": [{"z": 0.45, "w": 0.02, "color": "#e0e0e0"}]},
    "bottom": {"type": "pants", "material": "canvas", "color": "#c2ae8a", "looseness": 0.02},
    "shoes":  {"type": "hiking", "color": "#4a3020", "sole": "#1a1410"},
    "extras": [{"type": "backpack", "color": "#b8412c", "size": 0.85}]
  },
  "renders": [["idle", "back", "golden"], ["fall", "back", "golden"]],   // [anim, view, light] sets the storyboard needs
  "frames": {"walk": 24},            // optional per-animation frame counts
  "lights": {"lab": {"key": ["#e8f4ff", 140, [0.3, 0.8, 0.9]], "rim_l": ["#80d0ff", 260], "rim_r": ["#ffffff", 120], "world": "#101418"}},
  "render": {"res": 960, "samples": 32, "subdiv": 2, "motion_blur": true}
}
```

`type` on the top and bottom is a free label (field jacket, lab coat, hoodie). The shape comes from `length`, `sleeves`, `collar`, `hood` and `material`.

## 2. Values

| Field | Values |
|---|---|
| hair.style | none, bald, buzz, short, messy, bob, long, wavy, curly, afro, ponytail, bun |
| top.length | crop, waist, hip, thigh, knee, calf. Thigh and longer use one A-line skirt piece: coats, dresses, lab coats |
| top.sleeves | none, cap, short, elbow, 3q, long |
| top.collar | crew, high, v, none (ignored when `hood: true`) |
| bottom.type | pants, jeans, cropped, capri, shorts, short_shorts, leggings, skirt (+ `length`, `flare`) |
| shoes.type | boots, ankle_boots, hiking, sneakers, shoes, sandals, barefoot |
| extras.type | backpack, glasses, beanie, cap, scarf |
| material | pvc, rubber, cotton, denim, wool, knit, leather, nylon, canvas, silk, suede, plastic, metal |
| anim | idle, walk, run, arms_up, push, fall, wave, point, look_up, crouch, celebrate, talk |
| view | back, back34, side, side_l, front34, front34_l, front, low_back |
| light | studio, day, overcast, golden, neon, water, night, interior, fire, + your own in `lights` |

Colours are hex strings (sRGB) or `[r, g, b]` linear 0–1.

## 3. Designing for a topic

1. **Setting first.** Take the job, era and climate from the topic, e.g. lab → lab coat and glasses; ocean → wetsuit (leggings plus a long-sleeve top in rubber); history → wool and linen.
2. **Contrast.** The main outfit colour must stand out against the dominant scene colour (complementary or far apart in value). Examples: green garden → red/yellow/orange; blue night → yellow/white; desert → teal/blue.
3. **One signature item.** A recognisable hat, bag or coat colour keeps the character identifiable in silhouette and when tiny on screen.
4. **Readable from behind.** Most shots are back or 3/4 back views, so put identity in the hair shape and the back of the outfit (hood, backpack, ponytail, stripes).
5. **Policy.** Original people only. Never copy the look of a real person, celebrity or franchise character (signature costume plus hair plus colours). Never use logos or brand marks. Characters under 18 must be dressed and posed age-appropriately.
6. **Cast size.** A MICRO or SHORT video needs 1 character. A LONG video needs 1–3, each with a distinct silhouette: height, hair and outer shape.

## 4. Workflow (HITL)

```bash
S=.claude/skills/ai-video-production-pipeline/scripts/hero3d
python3 $S/make_character.py check   videos/<slug>/cast/<id>.json
python3 $S/make_character.py sheet   videos/<slug>/cast/<id>.json --fast   # ~1 min draft sheet
#   → look at videos/_shared/cast_sprites/<id>/sheet.png, adjust the JSON, repeat
python3 $S/make_character.py sheet   videos/<slug>/cast/<id>.json          # final sheet (full hair, 720 px)
python3 $S/make_character.py sprites videos/<slug>/cast/<id>.json          # all "renders" sets
python3 $S/make_character.py sprites videos/<slug>/cast/<id>.json --only walk:side:day   # add one set later
```

In scenes.py:

```python
import anim_kit as ak
ak.SPRITE_ROOT = Path(__file__).resolve().parent.parent / "_shared" / "cast_sprites"
hands = ak.character(c, x, feet_y, h_px, "mia/idle_back_golden", t)          # loops
ak.character(c, x, feet_y, h_px, "mia/look_up_back_water", t, start=0.2)     # one-shot, holds the last frame
ak.character(c, x, feet_y, h_px, "mia/arms_up_back_water", t, frame=8 + t * 12 % 9)  # loop a sub-range
```

`h_px` is the character's full height on screen (feet to the top of the head, hat or hood). Each set's
`meta.json` stores `height_m`, so characters of different heights keep the right scale.

## 5. Render cost (per frame, 960 px, 24–32 samples)

| Machine | Time per frame | 80-frame cast |
|---|---|---|
| 2 vCPU cloud box | 35–50 s | ~55 min |
| 8-core laptop CPU | ~12 s | ~16 min |
| MX250 (CUDA, if Blender still supports it) | ~10–15 s | ~15 min |
| RTX 3060+/rented A10/4090 (OptiX) | 1–3 s | 2–4 min |

`--fast` (no motion blur, fewer hairs, subdiv 1) is ~4× quicker for previews. Sprites are cached per
character in `videos/_shared/cast_sprites/`, so one cast serves every video until the spec changes.

## 6. Known limits

- The face is MakeHuman-generic: fine at sprite sizes and in 3/4 views, but no facial expressions.
- Cloth is shaped, not simulated. Coats swing with the pelvis, and fast poses can pinch at the elbows.
- Hair follows the head rigidly (no dynamics). Long hair and ponytails don't sway.
- A hood or beanie keeps only a fringe of hair. Long hair under a hood is not supported.
