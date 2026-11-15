---
name: video-produce
description: Chạy, xem trước, render và xử lý lỗi pipeline AI Workflow (giọng đọc, phụ đề, quay cảnh, ghép video, ComfyUI). Dùng khi người dùng nói "render", "xuất video", "xem thử", "lỗi vf", "chạy pipeline", "cài đặt".
---

# Chạy & sửa lỗi pipeline

Lệnh: `vf doctor` · `vf voice <id>` · `vf preview <id> [--scenes s003 --at 0.8]` · `vf render <id> [--draft]` · `vf all <id>` · `vf list` · `vf studio`.
Cache theo nội dung: chỉ cảnh đổi mới quay lại. Chỉ dùng `--force` khi nghi cache sai.

| Triệu chứng | Cách sửa |
|---|---|
| edge-tts lỗi mạng/giọng | kiểm tra internet; `tts.voices` trong settings; tạm `tts.engine: silent` để thử hình |
| Đọc sai số/từ | viết lại `voice_text` theo cách đọc ("hai nghìn") |
| Hành động lệch chữ | đổi `at` sang đúng từ trong lời đọc hoặc "%" |
| Cảnh quá ngắn | `"pause": 1` hoặc `"min_duration": 5` |
| Không mở được trình duyệt | `python -m playwright install chromium` (hoặc đặt `visual.browser_channel: msedge`) |
| NVENC lỗi | `render.encoder: libx264` trong `config/settings.local.yaml` |
| Máy chậm/nóng (MX250) | `render.workers: 1`, render `--draft` khi duyệt |
| Phụ đề đè chữ cảnh | `"captions": false` ở cảnh đó |
| ComfyUI | `visual.comfyui_url`, workflow API format trong `templates/comfy_workflows/` |

Ghi đè riêng máy vào `config/settings.local.yaml` (không commit). Xem ảnh preview trước khi render đầy đủ.
