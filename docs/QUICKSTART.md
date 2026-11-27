# Bắt đầu nhanh: video đầu tiên trong 10 phút (Windows)

## 1. Cài một lần (một dòng lệnh)

Mở **PowerShell** (bấm Start, gõ `powershell`, Enter) rồi dán:

```powershell
irm https://raw.githubusercontent.com/BaoPV-DEV/AI_Workflow/main/install.ps1 | iex
```

Script tự làm hết, không cần winget, Git hay cài ffmpeg bằng tay:
- chưa có Python 3.10+ thì tải Python 3.12 từ python.org và cài riêng cho user (không cần quyền admin);
- tải code về `D:\AI_Workflow` (không có ổ D thì về thư mục người dùng);
- cài thư viện vào `.venv`; ffmpeg đi kèm gói `imageio-ffmpeg`; quay cảnh bằng Microsoft Edge có sẵn;
- tạo shortcut **AI Workflow Studio** trên Desktop và mở Studio, video mẫu `meo_thich_hop` có sẵn.

Chạy lại đúng lệnh đó bất cứ lúc nào để cập nhật (giữ nguyên các video của bạn). Muốn cài chỗ khác: `$env:AIWF_DIR="E:\AI_Workflow"` trước khi chạy.

Nếu PowerShell báo không chạy được script: dùng lệnh trên (nó không cần đổi ExecutionPolicy), hoặc tải repo dạng zip rồi bấm đúp `setup.bat`.

## 2. Chạy video mẫu có sẵn

Bấm đúp shortcut **AI Workflow Studio** → **Video của tôi** → `meo_thich_hop` → **Xuất video**.

Hoặc dòng lệnh (trong thư mục cài, ví dụ `cd /d D:\AI_Workflow`):

```bat
vf preview meo_thich_hop
vf all meo_thich_hop
```

- `preview` tạo `workspace\meo_thich_hop\preview\_sheet.jpg` (mỗi cảnh một ảnh) trong vài giây.
- `all` tạo giọng đọc (cần internet), quay cảnh, ghép → `workspace\meo_thich_hop\out\meo_thich_hop.mp4` + `.srt`.
- Máy MX250: ~1–3 phút cho video 60 giây. Duyệt nhanh bằng `vf render meo_thich_hop --draft`.

## 3. Mở Web Studio

```bat
vf studio
```

Hoặc bấm đúp shortcut **AI Workflow Studio** (hay `Studio.vbs`): Studio chạy ẩn, không hiện cửa sổ terminal; đóng tab Studio là tự tắt.
Cần xem log khi có lỗi: mở `.cache\studio.log`, hoặc chạy `Studio.bat debug` để có terminal như cũ.

Trình duyệt mở `http://127.0.0.1:8765`. Bấm **Video của tôi → meo_thich_hop** để sửa lời, đổi cảnh, phát thử kèm giọng, rồi **Xuất video**.

## 4. Tạo video với chủ đề của bạn

**Cách A – không cần API key (dùng gói Claude):**
1. Studio → **Tạo video mới** → nhập chủ đề, chọn thể loại / phong cách / độ dài.
2. Bấm **Lấy prompt cho claude.ai** (prompt được chép sẵn).
3. Mở claude.ai, dán, gửi. Chép toàn bộ câu trả lời.
4. Dán vào ô trong Studio → **Nhập kịch bản** → kiểm tra → **Xuất video**.

Dòng lệnh tương đương: `vf prompt "chủ đề" --out p.txt` → dán vào claude.ai → lưu JSON thành `kb.json` → `vf import kb.json` → `vf all <id>`.

**Cách B – có API key:**
```bat
set ANTHROPIC_API_KEY=sk-ant-...
vf new "Vì sao bầu trời màu xanh" --genre explainer --seconds 60 --style classic_light
vf all vi_sao_bau_troi_mau_xanh
```

**Cách C – Claude Code:** mở thư mục repo trong Claude Code và nói "làm video về …" (skill `video-director`).

## Lỗi hay gặp

| Thông báo | Cách xử lý |
|---|---|
| `'vf' is not recognized` | Đang không ở thư mục repo: `cd /d D:\AI_Workflow` |
| `Không tìm thấy ffmpeg` | `.venv\\Scripts\\python -m pip install imageio-ffmpeg` (hoặc chạy lại lệnh cài) |
| `Không mở được trình duyệt` | Cập nhật Microsoft Edge, hoặc `.venv\Scripts\python -m playwright install chromium` |
| Lỗi edge-tts / mạng | Kiểm tra internet. Thử hình không tiếng: tạo `config\settings.local.yaml` với `tts: {engine: silent}` |
| Lỗi `h264_nvenc` | `config\settings.local.yaml`: `render: {encoder: libx264}` |
| Máy nóng / chậm | `config\settings.local.yaml`: `render: {workers: 1}` |

## Nhân vật 3D (Blender)

Thay người que bằng nhân vật người thật dựng bằng Blender (bộ hero3d của repo Skills):

1. Studio → **🧍 Nhân vật 3D** → **Cài Blender** (1 lần, ~500 MB, cần `git`). Hoặc `vf char3d setup`.
2. Chọn nhân vật mẫu (Mia, Rain Hero) hoặc **Tạo nhân vật mới** → **Sửa ngoại hình** → **Bảng xem trước** để duyệt.
3. **Render động tác** (1 lần cho mỗi nhân vật; máy không có card NVIDIA mất ~15 phút cho 6 động tác chuẩn).
4. Trình sửa cảnh → **Cài đặt video** → Nhân vật → chọn mục **🧍 Nhân vật 3D**. Cảnh "Người que diễn" sẽ dùng nhân vật 3D.

## Chế độ Điện ảnh (bộ skill repo Skills)

Video kiểu điện ảnh: Claude viết storyboard và code từng cảnh (hạt, chiều sâu, ánh sáng, nhân vật 3D), máy bạn dựng hình + nhạc + hiệu ứng âm thanh.

1. Cần AI là **Claude Code** (Cài đặt → AI). Studio → **🎬 Điện ảnh** → **Cài thư viện dựng hình** (1 lần).
2. Nhập chủ đề, thời lượng, khung, ngôn ngữ, chọn nhân vật 3D (đã render ở trang Nhân vật 3D) → **Viết storyboard & ảnh xem thử** (Claude làm 10–30 phút).
3. Xem ảnh xem thử, Storyboard, Kiểm duyệt, SEO → **⚡ Dựng nhanh** để xem nhịp → **🎬 Dựng video**.
4. Lệnh tương đương: `vf cinema new "chủ đề" --seconds 60 --char3d mia`, `vf cinema render <slug>`.
