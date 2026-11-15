# Bắt đầu nhanh: video đầu tiên trong 10 phút (Windows)

## 1. Cài một lần

1. Cài **Python 3.10+** (python.org, tick *Add python.exe to PATH*) và **Git**.
2. Cài ffmpeg: mở PowerShell, chạy `winget install Gyan.FFmpeg`, rồi **mở lại** cửa sổ.
3. Lấy code và cài:

```bat
cd /d D:\
git clone https://github.com/BaoPV-DEV/AI_Workflow.git
cd AI_Workflow
setup.bat
```

`setup.bat` tạo `.venv`, cài thư viện, Chromium và cuối cùng chạy `vf doctor`. Mọi dòng phải có ✔ (riêng `faster_whisper`, `anthropic`, `ANTHROPIC_API_KEY` là tuỳ chọn).

## 2. Chạy video mẫu có sẵn

```bat
xcopy /e /i examples\meo_thich_hop workspace\meo_thich_hop
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
| `Chưa cài ffmpeg` | `winget install Gyan.FFmpeg`, mở lại cửa sổ |
| `Không mở được trình duyệt` | `.venv\Scripts\python -m playwright install chromium` |
| Lỗi edge-tts / mạng | Kiểm tra internet. Thử hình không tiếng: tạo `config\settings.local.yaml` với `tts: {engine: silent}` |
| Lỗi `h264_nvenc` | `config\settings.local.yaml`: `render: {encoder: libx264}` |
| Máy nóng / chậm | `config\settings.local.yaml`: `render: {workers: 1}` |
