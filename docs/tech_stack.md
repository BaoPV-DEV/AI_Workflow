# Kiến Trúc & Tech Stack Hệ Thống Sản Xuất Video AI Tự Động (Modular Hybrid Pipeline)

Tài liệu này tổng hợp toàn bộ bộ công nghệ (Tech Stack), kiến trúc hệ thống và chiến lược tối ưu chi phí token khi kết hợp **Claude** với **môi trường Local (máy cấu hình thấp như MX250)** và **khả năng mở rộng lên GPU mạnh / Cloud GPU (RunPod, Vast.ai)** trong tương lai.

---

## 1. Nguyên Tắc Thiết Kế Cốt Lõi

1. **Tách biệt "Bộ não" và "Cơ bắp":** Claude chỉ chịu trách nhiệm tư duy kịch bản, cấu trúc phân cảnh, viết code đồ họa vector/animation và xuất dữ liệu JSON chuẩn. Toàn bộ khâu tạo âm thanh, căn chỉnh phụ đề, tải tài nguyên và ghép nối video do script cục bộ thực hiện (0 token).
2. **Kiến trúc Modular (Adapter Pattern):** Giao tiếp giữa các bước thông qua một file trung tâm duy nhất (`project_manifest.json`). Tầng tạo hình ảnh/video được thiết kế dạng "cắm là chạy" (Plug & Play) để chuyển đổi linh hoạt giữa **Code-Driven Graphics / API giá rẻ** (khi dùng MX250) và **ComfyUI** (khi thuê GPU Cloud hoặc nâng cấp máy).
3. **Component-Driven Video:** Với mảng Motion Graphics và Hoạt hình 2D, xây dựng sẵn thư viện hiệu ứng bằng code (SVG, HTML/CSS/GSAP, Remotion). Claude chỉ truyền tham số (props) hoặc sinh code vector nhẹ thay vì viết lại toàn bộ hệ thống từ đầu cho mỗi video.

---

## 2. Tech Stack Chi Tiết Theo Từng Tầng Xử Lý

| Tầng xử lý | Công nghệ / Công cụ | Nơi chạy | Vai trò & Lý do lựa chọn |
| :--- | :--- | :--- | :--- |
| **1. Điều phối & Kịch bản** | **Claude API / Claude Code**<br>(Sonnet 3.5/3.7 & Haiku) | Cloud API | Lên kịch bản, chia phân cảnh và xuất file `project_manifest.json`. Dùng **Haiku** cho các tác vụ format/dịch thuật để giảm 75% chi phí. |
| **2. Giọng đọc (TTS)** | **Edge-TTS** / **Kokoro-82M** / **Piper TTS** | Local CPU (MX250) | Chạy cực nhẹ trên CPU (RAM < 500MB), tốc độ sinh tiếng nhanh gấp 5–10 lần thời gian thực, chất lượng tự nhiên, **0 đồng**. |
| **3. Căn chỉnh phụ đề** | **faster-whisper**<br>(Model `tiny` hoặc `base` int8) | Local CPU (MX250) | Bóc tách timestamp chính xác từng từ (word-level alignment) để làm hiệu ứng chữ chạy (karaoke/captions) mà không tốn token Claude. |
| **4. Tạo Hình Ảnh & Clip**<br>*(Chế độ MX250 - Không GPU)* | **Cách 1 (0 đồng, Không Watermark):**<br>Claude sinh **SVG / HTML+GSAP** + **Playwright**<br> | Local CPU + Cloud API | - **Cách 1:** Claude trực tiếp vẽ biểu đồ, icon (SVG) và hiệu ứng chuyển động (HTML/CSS). Dùng Playwright quay lại thành video 60fps, nét căng 4K, tùy biến mọi tỷ lệ (9:16, 16:9).|
| **5. Tạo Hình Ảnh & Clip**<br>*(Chế độ GPU khỏe / Thuê)* | **ComfyUI (Headless API)**<br>(`Flux`, `Wan 2.1`, `LTX-Video`, `AnimateDiff`) | Local RTX hoặc<br>RunPod / Vast.ai | Khi cần sản xuất hoạt hình AI tạo sinh chất lượng cao, thuê GPU rời theo giờ ($0.3-$0.5/h), bật sẵn ComfyUI API và trỏ endpoint từ máy MX250 sang để batch-render. |
| **6. Dựng & Render Video** | **Remotion (React)** hoặc **FFmpeg** (`h264_nvenc`) | Local MX250 | Đọc `project_manifest.json`, ghép âm thanh, phụ đề động, SVG/HTML animation và clip lại thành file `.mp4`. Tận dụng nhân mã hóa phần cứng NVENC của MX250 để xuất video nhanh. |

---

## 3. Cấu Trúc Thư Mục Dự Án Chuẩn

```text
ai-video-pipeline/
├── config/
│   ├── settings.yaml          # Cấu hình chế độ: "CODE_GRAPHICS", "LOW_GPU_API", hoặc "COMFYUI_CLOUD"
│   └── prompts/               # Tách prompt theo thể loại để tiết kiệm token đầu vào
│       ├── news.md
│       ├── motion_graphic.md
│       └── animation.md
├── core/
│   ├── orchestrator.py        # Script điều phối chính (đọc JSON, gọi các module)
│   ├── tts_whisper.py         # Module tạo giọng đọc & lấy timing phụ đề trên CPU
│   ├── visual_adapter.py      # Adapter chuyển đổi giữa SVG/Playwright, Fal.ai và ComfyUI
│   └── renderer.py            # Module gọi FFmpeg (h264_nvenc) / Remotion để xuất video
├── templates/                 # Thư viện giao diện dựng sẵn (Claude chỉ truyền props)
│   ├── html_scenes/           # Các template HTML/CSS/GSAP cho motion graphics
│   └── comfy_workflows/       # Các file workflow_api.json cho ComfyUI
├── workspace/                 # Thư mục làm việc của từng video (được ignore khi dùng Claude Code)
│   └── project_01/
│       ├── project_manifest.json
│       └── assets/            # Chứa file .wav, .svg, .png, .mp4 tạm thời
└── CLAUDE.md                  # File quy tắc ngắn gọn (<150 từ) hướng dẫn Claude Code
```

---

## 4. Quy Chuẩn File Giao Tiếp Trung Tâm (`project_manifest.json`)

Thay vì để Claude viết văn xuôi hay code dài dòng mỗi lần tạo video, hệ thống ép Claude trả về đúng cấu trúc JSON tối giản này:

```json
{
  "project_id": "vid_001",
  "aspect_ratio": "9:16",
  "resolution": "1080x1920",
  "render_mode": "CODE_GRAPHICS",
  "scenes": [
    {
      "scene_id": 1,
      "voice_text": "Tại sao máy cấu hình yếu vẫn làm được video triệu view?",
      "visual_type": "html_animation",
      "template_name": "title_card_neon",
      "props": {
        "heading": "TỰ ĐỘNG HÓA VIDEO AI",
        "subheading": "Tối ưu cho máy cấu hình thấp"
      },
      "audio_path": "assets/scene_1.wav",
      "duration": 3.8,
      "word_timings": [
        {"word": "Tại", "start": 0.0, "end": 0.3},
        {"word": "sao", "start": 0.3, "end": 0.6}
      ]
    },
    {
      "scene_id": 2,
      "voice_text": "Bí mật nằm ở việc kết hợp đồ họa vector và trí tuệ nhân tạo.",
      "visual_type": "svg_graphic",
      "svg_code": "<svg viewBox='0 0 1080 1920'>...</svg>",
      "audio_path": "assets/scene_2.wav",
      "duration": 4.2
    }
  ]
}
```

---

## 5. Quy Tắc Tối Ưu Token Khi Làm Việc Với Claude

* **Không bao giờ để Claude đọc thư mục `workspace/` hoặc `node_modules/`:** Khai báo rõ trong `.claudeignore` để tránh làm phình Context Window bởi các file log, file media hoặc JSON dữ liệu cũ.
* **Tận dụng Prompt Caching:** Khi gọi Claude API qua `orchestrator.py`, luôn bật `cache_control` cho phần System Prompt và JSON Schema mẫu (giảm 90% chi phí đọc lại khung hướng dẫn ở các video tiếp theo).
* **Dùng `/compact` thường xuyên (nếu dùng Claude Code):** Sau khi chốt xong một tính năng trong `core/` hoặc một template trong `templates/`, gõ `/compact` ngay lập tức để xóa lịch sử hội thoại thừa.
* **Sửa lỗi cục bộ:** Khi tinh chỉnh giao diện hoặc hiệu ứng, chỉ định chính xác tên file template cần sửa (ví dụ: *"Chỉ sửa file `templates/html_scenes/title_card.html`, đổi màu chữ sang xanh cyan"*), tuyệt đối không yêu cầu sinh lại toàn bộ pipeline.