---
name: ai-video-character
description: Designs and builds realistic 3D characters fitted to a video's topic for the ai-video-production-pipeline - writes a character spec (body, skin, hair, outfit, accessories, poses, lighting), renders a turnaround sheet for approval, then renders the animation sprites the scenes use. Use when the user asks to create, design, change or add a character or cast for a video or topic, or says "tạo nhân vật", "thiết kế nhân vật", "nhân vật riêng", "nhân vật cho chủ đề", "đổi nhân vật", "thêm nhân vật", "dàn nhân vật", "nhân vật 3D".
---

# AI Video Character

Builds one or more original 3D characters per topic. The engine (MakeHuman CC0 body, generated clothes,
strand hair, Blender Cycles) lives in the `ai-video-production-pipeline` skill:

- Spec schema, values, design rules, render cost: `../ai-video-production-pipeline/references/character-spec.md` (read it first).
- Tool: `../ai-video-production-pipeline/scripts/hero3d/make_character.py` (`check`, `sheet`, `sprites`, `presets`).
- Ready-made specs: `../ai-video-production-pipeline/assets/cast-presets/*.json`.

The character files go in `videos/<slug>/cast/<id>.json`. Sprites are written to `videos/_shared/cast_sprites/<id>/`, which is git-ignored and rebuilt from the JSON.

## Steps

### 1. Brief

Read the project's `project-brief.md`, `outline.md` and `storyboard.md` if they exist. List:

- the setting and era;
- the dominant scene colours;
- the role of each character;
- the shots each character appears in, with action, view and lighting.

If there is no project yet, ask for the topic in one short question, or take it from the request.

### 2. Design

Write one spec per character following §3 of character-spec.md. Rules:

- **Topic fit.** Clothing and props should say the setting at a glance.
- **Contrast.** Contrast the scene palette.
- **Signature item.** Give each character one signature item.
- **Readable from behind.**
- **Distinct casts.** In a multi-character cast, vary the silhouettes (height, hair, outer shape).

Fill `renders` with exactly the `[anim, view, light]` sets the storyboard needs. Use the fewest sets possible, because each frame costs render time.

Validate with `make_character.py check`.

### 3. Sheet (CHECKPOINT)

1. Run `make_character.py sheet <spec> --fast` (≈1 min) and view `sheet.png` yourself. Check:
   - clothes clipping or holes;
   - hair coverage;
   - colours against the planned backgrounds;
   - that the silhouette reads.
2. Fix the JSON and repeat until it is clean. Then render the final sheet without `--fast` and send it to the user with a 3–5 line description.
3. Stop and wait for approval, unless the user said "auto" or "chạy liền", or nobody is watching. In that case, note the choice in `cast/README.md` and continue.

### 4. Sprites

1. Run `make_character.py sprites <spec>`. Run it in the background when the cast is large. §5 of character-spec.md gives the time per frame for this machine, so you can tell the user how long it will take.
2. Open 2–3 frames of each set (first, middle, last) and check:
   - poke-through at the extreme poses;
   - feet on the ground line;
   - that motion blur doesn't smear the face.

### 5. Hook into the video

1. In `scenes.py`, set `ak.SPRITE_ROOT` to `videos/_shared/cast_sprites` and draw with `ak.character(c, x, feet_y, h_px, "<id>/<anim>_<view>_<light>", t, ...)`. It returns the hand positions for props and effects.
2. Update the storyboard's Consistency Bible with each character's one-line description, which is also the AI-prompt tag.
3. Record each character (id, look, signature item, sets) in `cast/README.md`.

### Changing a character

Edit the JSON, rerun `sheet`, then rerun only the affected `sprites` sets with `--only`. The `seed` field gives a new hair variation without changing the design.

## Rules

- Create original people only. Do not copy the look of a real person, celebrity or franchise character. Do not use logos.
- Characters under 18 must have age-appropriate clothing and poses.
- Reply to the user in Vietnamese. Specs, prompts and file contents stay in English.
- Never commit the rendered sprites. The JSON is the source of truth.
