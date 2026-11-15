# AI Workflow – Pipeline video AI tối ưu token

Biến một chủ đề thành video hoàn chỉnh (giọng đọc, phụ đề karaoke, motion graphics, hoạt hình người que) trên máy cấu hình thấp như MX250. Claude chỉ viết kịch bản dạng JSON; phần còn lại chạy local, không tốn token.

```
chủ đề → Claude → project_manifest.json → [giọng đọc → mốc từ → quay cảnh → ghép] → video.mp4
```

## Cài đặt (Windows)

```bat
git clone https://github.com/BaoPV-DEV/AI_Workflow.git
cd AI_Workflow
setup.bat              :: tạo .venv, cài thư viện, Chromium, kiểm tra ffmpeg
vf studio              :: mở Web Studio trong trình duyệt
```

Cần Python 3.10+ và ffmpeg (`winget install Gyan.FFmpeg`). Linux/macOS: `pip install -r requirements.txt && python -m playwright install chromium`, rồi dùng `python vf.py`.

## Ba cách tạo video

| Cách | Lệnh | Chi phí |
|---|---|---|
| **Web Studio** | `vf studio` → *Video mới* | tuỳ chọn API hoặc dán từ claude.ai |
| **Claude API** | `set ANTHROPIC_API_KEY=...` rồi `vf new "chủ đề" --genre animation --seconds 45` | vài nghìn token/video, có cache |
| **Không API** (gói Claude Pro) | `vf prompt "chủ đề" --out p.txt` → dán vào claude.ai → lưu JSON → `vf import file.json` | 0 đồng API |
| **Claude Code** | mở repo, nói "làm video về …" (skill `video-director`) | theo gói |

Sau đó:

```bat
vf preview <id>      :: ảnh tĩnh mỗi cảnh + _sheet.jpg (vài giây) – duyệt trước
vf all <id>          :: giọng đọc + quay cảnh + ghép → workspace\<id>\out\<id>.mp4
vf edit <id> "cảnh 3 cho Bo cầm cúp, vui hơn"     :: agent sửa đúng 1 cảnh (model nhỏ)
vf translate <id> --to en,ja                      :: bản dịch thành project mới
```

Thử ngay với video mẫu: `xcopy /e /i examples\demo_pipeline workspace\demo_pipeline` rồi `vf all demo_pipeline`.

## Có gì trong bộ này

- **Engine module** (`engine/`): TTS (edge-tts/piper/kokoro), mốc từng từ (edge-tts → faster-whisper → ước lượng), adapter hình ảnh cắm-là-chạy (HTML/SVG qua Playwright, ảnh Ken Burns, clip, ComfyUI), phụ đề karaoke, nhạc nền tự giảm khi có lời, chuẩn âm lượng -14 LUFS, cache theo cảnh, tự chọn NVENC/QSV/x264.
- **11 template** (`templates/html_scenes/`): `stickman_stage`, `title_card_neon`, `kinetic_text`, `stat_card`, `bullet_list`, `bar_chart`, `compare_split`, `timeline`, `quote_card`, `headline_news`, `svg_wrapper`. Chạy cả 9:16 và 16:9.
- **Rig người que** 11 khớp, 32 động tác, cảm xúc khuôn mặt, đạo cụ, bong bóng thoại, tự đi bộ khi đổi vị trí – tương thích định dạng `actions.json` của VF Studio.
- **8 style** (`config/styles/`) lấy cảm hứng từ stickman-video-director: classic light/dark, beanie tech, cozy, historical, retro TV, neon news, dynamic meme.
- **Mini agent** (`engine/agent/`): vòng lặp tool-use như Claude Code thu nhỏ – prompt caching, định tuyến model, trần token, rút gọn lịch sử.
- **Web Studio** (`vf studio`): bố cục bàn dựng – kịch bản bên trái (gõ lời đọc như soạn văn bản), màn xem giữa phát kèm giọng đọc và tự sang cảnh tiếp, bảng chỉnh bên phải (form theo từng kiểu cảnh, trình chỉnh diễn xuất bằng menu, không cần sửa JSON), timeline phía dưới có ảnh thu nhỏ và kéo thả đổi thứ tự. Tự lưu, hoàn tác `Ctrl+Z`, phím tắt `Space` / `←` `→` / `Ctrl+Enter` (xuất nháp), thanh tiến độ khi render, 4 bước Kịch bản → Giọng đọc → Xem trước → Xuất video luôn hiện bước tiếp theo.
- **5 skill Claude Code** (`.claude/skills/`) và `CLAUDE.md` ngắn.

Tài liệu: [kiến trúc](docs/ARCHITECTURE.md) · [tối ưu token](docs/TOKEN_STRATEGY.md) · [lộ trình](docs/ROADMAP.md) · [tech stack gốc](docs/tech_stack.md) · [catalog](CATALOG.md).

## Mở rộng

- Template mới: copy một file trong `templates/html_scenes/`, giữ `data-doc` + `data-demo`, chạy `vf catalog`.
- Động tác/nhân vật: sửa `library/actions.json`, `library/characters.json`.
- Style: thêm `config/styles/<tên>.yaml`.
- Nguồn hình mới (API, GPU thuê): class kế thừa `engine.visual.base.Adapter` + `@register`.
- Cấu hình riêng máy: `config/settings.local.yaml` (không commit), ví dụ `render: {workers: 1, encoder: libx264}`.
