# Kiến trúc

```
chủ đề ──► Claude (vf new | claude.ai + vf import | Claude Code skill)
              │  project_manifest.json  (chỉ phần "authored")
              ▼
 ┌────────────── engine (local, 0 token) ──────────────┐
 │ voice   : tts.py (edge / piper / kokoro / silent)    │ → assets/sNNN.wav
 │ align   : mốc từ của edge-tts → faster-whisper → ước │ → word_timings, duration
 │ visuals : visual/ adapter (Plug & Play)              │ → build/clips/sNNN.mp4
 │           html_animation · svg_graphic  (Playwright, tua từng khung)
 │           image (Ken Burns) · video · color (ffmpeg)
 │           comfyui (local RTX / RunPod / Vast)
 │ render  : ghép + phụ đề karaoke ASS + nhạc nền duck + loudnorm -14 LUFS
 └──────────────────────────────────────────────────────┘
              ▼
        out/<id>.mp4 + .srt
```

## Thư mục

| Đường dẫn | Vai trò |
|---|---|
| `vf.py`, `vf.bat` | dòng lệnh |
| `engine/pipeline.py` | điều phối voice → visuals → render, preview |
| `engine/visual/` | adapter hình ảnh; thêm adapter = 1 class + `@register` |
| `engine/agent/` | mini agent: `llm.py` (cache, routing, sổ token), `loop.py` (vòng tool-use), `tools.py` (sửa manifest), `director.py` (tạo/sửa/dịch) |
| `engine/cache.py` | băm nội dung từng cảnh → chỉ làm lại phần đổi |
| `templates/html_scenes/` | 11 template + `_lib/` (runtime tua thời gian, rig người que, CSS chung) |
| `library/` | `actions.json` (32 động tác), `characters.json` (11 preset) |
| `config/` | `settings.yaml`, `styles/*.yaml` (8 style), `prompts/*.md` |
| `schema/manifest.schema.json` | hợp đồng dữ liệu |
| `web/` | Web Studio (thư viện chuẩn Python + 1 file HTML) |
| `.claude/skills/` | 5 skill cho Claude Code |
| `workspace/<id>/` | project_manifest.json, assets/, build/, preview/, out/ (không commit) |

## Vì sao quay từng khung hình

Playwright quay video thời gian thực sẽ giật trên máy yếu. Runtime cho phép engine gọi `__vfSeek(t)` rồi chụp, nên kết quả giống hệt nhau dù máy nhanh hay chậm, và CSS animation / GSAP / SMIL đều được tua đúng.

## Chế độ render (`render_mode`)

- `CODE_GRAPHICS` (mặc định, MX250): template + SVG + ảnh có sẵn.
- `LOW_GPU_API`: thêm adapter API ảnh/video giá rẻ (viết class kế thừa `Adapter`).
- `COMFYUI_CLOUD`: cảnh `visual_type: comfyui`, trỏ `visual.comfyui_url` tới GPU thuê.
