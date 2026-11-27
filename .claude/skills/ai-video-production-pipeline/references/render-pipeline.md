# Render Pipeline (Bước 6–7)

`scripts/render.py` dựng `storyboard.json` thành video hoàn chỉnh: voiceover theo từng shot, chuyển động camera trên ảnh, chữ on-screen, phụ đề burn-in, nhạc nền tự ducking, SFX, chuẩn hoá loudness, SRT và `qa.json`.

Cần: `python3`, `Pillow`, `numpy`, `ffmpeg`, `ffprobe` (khuyến nghị thêm `scipy`). TTS offline: `festival` + `festvox-us-slt-hts` hoặc `espeak-ng` (`apt-get install festival festvox-us-slt-hts`).

## 1. Schema `storyboard.json`

```json
{
  "title": "What If You Could Stop Time for 10 Seconds?",
  "slug": "stop-time-10s",
  "target_seconds": 20,
  "profile": "MICRO",
  "format": {"width": 1920, "height": 1080, "fps": 30},
  "style": {"font": "Inter:style=ExtraBold", "accent": "#FFD23F"},
  "voice": {"engine": "festival", "voice": "cmu_us_slt_arctic_hts", "target_wpm": 150},
  "music": {"mood": "tense", "bpm": 92, "volume_db": -8, "duck": 0.45, "file": null},
  "captions": {"burn_in": true, "max_words": 3, "y": 0.86, "upper": true, "box": true, "box_alpha": 150},
  "timing": {"lead": 0.08, "tail": 0.14},
  "sfx_gain": 0.8,
  "shots": [
    {
      "id": "S01",
      "chapter": "Hook",
      "vo": "What if you could stop time?",
      "prompt": "Wide shot of a rainy neon city street at night, ... 16:9",
      "image": "assets/S01.png",
      "motion": "zoom_in",
      "motion_amount": 0.12,
      "focus": [0.5, 0.45],
      "text": {"content": "STOP TIME?", "at": 0.3, "size": 160, "position": "center", "anim": "pop"},
      "sfx": ["whoosh@0.0", "tick@0.6"],
      "transition_in": "cut",
      "grade": null,
      "music_drop": false,
      "pi": true,
      "min_duration": 2.0,
      "still_at": [0.3, 0.8]
    }
  ]
}
```

| Trường shot | Ý nghĩa |
|---|---|
| `vo` | Lời thoại của shot. Độ dài shot = max(`min_duration`, `duration`, lead + thời lượng giọng + tail) |
| `image` | Ảnh hoặc frame từ công cụ AI. Thiếu file → thẻ đỏ "missing asset" kèm prompt (để lộ chỗ thiếu) |
| `motion` | `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `push_up`, `crash_zoom`, `shake`, `static` |
| `focus` | Tâm khung hình [x, y] (0–1) — đặt vào chủ thể để zoom không cắt mất |
| `text` | Chữ on-screen: `at` (giây trong shot), `size`, `position` (`top`/`upper`/`center`), `anim` (`pop`/`fade`), `accent` |
| `sfx` | `tên@giây` hoặc `tên*gain@giây`. Có sẵn: `whoosh`, `hit`, `tick`, `riser` (kết thúc tại mốc giây), `freeze`, `reverse`, `pop`, `splash`, `bubbles`, `shrink` |
| `transition_in` | `cut`, `fade`, `flash` (được dựng bên trong file shot) |
| `grade` | `freeze` (phủ tông lạnh từ `grade_at`), `dark` (tối dần tới gần đen — hợp với cảnh "mất ánh sáng", kết video) |
| `shake_at` | Rung camera 0,5s từ mốc này (kết hợp với `hit`) |
| `music_drop` | Tắt nhạc trong shot — pattern interrupt bằng khoảng lặng |
| `pi` | Đánh dấu pattern interrupt để QA đếm |

## 2. Nguồn ảnh (asset)

Thứ tự ưu tiên:
1. **Ảnh/clip production** từ Midjourney, Flux, Kling…: xuất theo đúng `prompt` của shot, tỷ lệ đúng khung (16:9 hoặc 9:16), độ phân giải ≥ khung xuất × 1,25 (vì renderer cắt để tạo chuyển động). Đặt tên `assets/<shot_id>.png`.
2. **Ảnh tạm vẽ bằng code** (khi không có công cụ ảnh, hoặc cần video thử): viết `make_assets.py` trong thư mục dự án, vẽ bằng Pillow theo bố cục, bảng màu, ánh sáng của prompt, xuất ở 2400×1350 (16:9) hoặc 1350×2400 (9:16). Quy tắc để ảnh tạm trông tử tế:
   - Nền gradient nhiều lớp + vignette, không dùng màu phẳng.
   - Có chiều sâu: ít nhất 3 lớp (xa – giữa – gần), lớp xa mờ/nhạt hơn.
   - Một chủ thể rõ, chiếm 30–50% khung, đặt theo quy tắc 1/3, tương phản với nền.
   - Ánh sáng có hướng (glow, rim light, bóng đổ) khớp với prompt.
   - Chừa vùng trống cho chữ on-screen và phụ đề (dải 72–92% chiều cao).
   - Ghi rõ trong `qa-report.md` là ảnh tạm.
3. Không có gì: renderer tự chèn thẻ "missing asset" — chỉ dùng để duyệt nhịp.

## 2b. Animation từng khung (`scene`) — mặc định khi không có ảnh/clip AI

Ảnh tĩnh + Ken Burns trông như slideshow. Khi không có asset AI, dựng cảnh động bằng `scripts/anim_kit.py` (skia-python: vector khử răng cưa, gradient, blur, blend add/screen):

```python
# videos/<slug>/scenes.py
from anim_kit import Rain, sky, make_city_layer, hero, ripple, flare, vignette, to_pil, ease, lerp
def s01(t, dur, ctx):                     # t: giây trong shot; ctx: kích thước + cache
    s = ctx.surface(); c = s.getCanvas()
    ...                                   # vẽ theo t → mọi khung độc lập, render song song được
    return to_pil(s)
```

| Thành phần kit | Dùng cho |
|---|---|
| `sky`, `make_city_layer`, `make_neon_layer`/`draw_neon`, `draw_fog`, `draw_road` | Nền nhiều lớp; dịch các lớp theo `cam_x × depth` để có parallax |
| `Rain(freeze_at=…, stop=…)` | Mưa/hạt có chiều sâu; giảm tốc mượt rồi đứng yên (time-stop), vệt → hạt sáng |
| `character(...)` | Nhân vật 3D theo chủ đề (sprite từ `make_character.py`, mục 2c) — mặc định |
| `hero(...)` | Nhân vật vector dự phòng khi chưa có sprite |
| `ripple`, `flare`, `vignette` | Sóng xung kích, loé sáng, viền tối |
| `bokeh`, `light_rays`, `motes`, `grass_blade`, `water_drop`, `ant` | Thế giới macro/thiên nhiên: hậu cảnh mờ, tia nắng, bụi phấn, cỏ đung đưa, giọt nước khúc xạ, côn trùng bước đi |
| `bloom`, `grain`, `chroma` | Hậu kỳ — bật qua `"post"` trong storyboard |

Storyboard: `"scene": "scenes.py:s01"` (thay cho `image`/`motion`); hậu kỳ chung:
`"post": {"vignette": false, "bloom": {"threshold": 200, "strength": 0.9, "radius": 24}, "chroma": 1, "grain": 0.03}`.
Chữ on-screen, phụ đề, flash/fade, rung camera (`shake_at`) vẫn do `render.py` vẽ chồng lên.

Nguyên tắc để animation trông "có tiền":
- Mỗi shot có ít nhất 2 chuyển động độc lập (camera + chủ thể/hạt), không chỉ zoom.
- Parallax: lớp xa dịch ít, lớp gần dịch nhiều; hạt tiền cảnh vẽ **sau** nhân vật.
- Chuyển động dùng easing (`ease`, `back` cho cú bật), không tuyến tính.
- Luật thế giới nhất quán (vd. thời gian dừng → mưa, sương, neon cùng dừng; chỉ camera và nhân vật còn động).
- Bloom tính theo độ sáng cảm nhận, ngưỡng ~200 — thấp hơn sẽ làm màu bão hoà (áo vàng) cháy trắng.
- Kiểm tra bố cục ở `--stills` tại 20% và 70% mỗi shot: đầu/tay chủ thể không ra khỏi khung, không chạm chữ on-screen.
- **Vùng an toàn:** dải 80–94% chiều cao là của phụ đề, dải 8–26% là của chữ on-screen `top` → đặt chân chủ thể ≤ 78%, vật thể chính ở 26–78%.
- Sơ đồ/infographic: phần tử chính chiếm ≥ 25% chiều cao khung — nhỏ hơn là không đọc được trên điện thoại.
- Vật thể "đang tới" (rơi, bay vào) phải lộ ≥ 50% ngay từ khung đầu của shot — người xem chỉ có 2–3 giây.

Hiệu năng: ~0,15–0,45s/khung 1080p; `render.py` render các shot song song (`--jobs`, mặc định = số nhân CPU). 20s ≈ 2,5 phút trên 2 nhân.

## 2c. Nhân vật 3D theo chủ đề — `scripts/hero3d/make_character.py`

Mỗi video/chủ đề có **dàn nhân vật riêng**, mô tả trong `videos/<slug>/cast/<id>.json` (schema, giá trị, quy tắc thiết kế: `references/character-spec.md`; mẫu: `assets/cast-presets/`). Skill `ai-video-character` là "action" tạo nhân vật: thiết kế spec → bảng nhân vật (sheet) để duyệt → sprite.

`build_character.py` (chạy bằng Blender Python, chỉ đọc file dữ liệu CC0 của MakeHuman/MPFB2):

1. Thân người: pha trộn macro MakeHuman thật (giới, tuổi, cơ, cân nặng, chiều cao, tỉ lệ, sắc tộc) + target tuỳ chọn; khung xương 163 xương + trọng số da.
2. Da: subsurface, mặt nạ UV môi/má/mí mắt, lỗ chân lông; mắt (tròng, đồng tử, bóng ướt), lông mi; lông mày và **tóc sợi thật** (Curves, Principled Hair BSDF) theo kiểu: buzz/short/messy/bob/long/wavy/curly/afro/ponytail/bun.
3. Quần áo sinh tự động: áo (độ dài, tay, cổ, mũ trùm mềm, khoá kéo, đường may, vạt A-line liền cho áo dài/váy), quần/short/váy, giày/ủng/sneaker (đế màu), phụ kiện: ba lô (quai qua vai), kính, mũ len, mũ lưỡi trai, khăn. Nếp nhăn vải bằng displacement gắn theo vải; phần thân bị che được ẩn để không xuyên áo.
4. 12 chuyển động (idle, walk, run, arms_up, push, fall, wave, point, look_up, crouch, celebrate, talk), keyframe hoá để Cycles **motion blur**; 8 góc nhìn; 9 bộ đèn + đèn tuỳ chỉnh trong spec.
5. Xuất `videos/_shared/cast_sprites/<id>/<anim>_<view>_<light>/*.png` + `meta.json` (fps, loop, `height_m`, `ortho`, chân/tay/đầu từng khung).

```bash
S=scripts/hero3d
python3 $S/make_character.py check   videos/<slug>/cast/mia.json
python3 $S/make_character.py sheet   videos/<slug>/cast/mia.json --fast   # bản nháp ~1 phút → sheet.png
python3 $S/make_character.py sprites videos/<slug>/cast/mia.json          # các bộ trong "renders"
```

Trong `scenes.py`: `ak.SPRITE_ROOT = .../videos/_shared/cast_sprites`; `ak.character(c, x, feet_y, h, "mia/idle_back_golden", t, lean=…, flip=…, frame=…)` — `h` = chiều cao nhân vật trên màn hình (px, chân → đỉnh đầu/mũ), trả về vị trí 2 bàn tay. Khung sprite được **nội suy** (trộn premultiplied giữa 2 khung kề) và lọc mipmap khi thu nhỏ → chuyển động mượt ở 30 fps dù sprite 12–24 fps. `has_sprite(name)` để rơi về nhân vật vector khi thiếu sprite.

Thời gian: ~35–50 s/khung (960 px) trên 2 nhân CPU; GPU thuê 1–3 s/khung — bảng đầy đủ ở character-spec §5. Mỗi nhân vật chỉ render một lần rồi dùng lại cho mọi video.

Giới hạn: mặt chung kiểu MakeHuman (không biểu cảm), vải tạo hình chứ không mô phỏng, tóc không đung đưa. Ưu tiên góc sau/3/4/ngang.

## 3. Giọng đọc

| Engine | Cách dùng | Ghi chú |
|---|---|---|
| File riêng | `voice/<shot_id>.wav` | Luôn được ưu tiên — xuất từ ElevenLabs/thu âm theo từng shot |
| `elevenlabs` | `ELEVENLABS_API_KEY` + `voice_id` | Cần mạng tới api.elevenlabs.io; không có thì tự rơi về festival |
| `festival` | `voice`: `cmu_us_slt_arctic_hts` (nữ US) | Offline, nghe máy — chỉ để duyệt nhịp |
| `espeak-ng` | `espeak_voice`, `wpm` | Dự phòng cuối |

`voice.target_wpm` (mặc định 150): sau khi tạo giọng, renderer đo tốc độ và tự kéo giãn/nén (atempo, giữ cao độ, giới hạn ×0,75–1,33) để khớp mục tiêu. Không áp dụng khi dùng file `voice/` của người dùng. Đặt `target_wpm: null` để tắt. (Festival SLT đọc ~180 wpm nếu không chỉnh.)

Phụ đề: chia theo dấu câu rồi chia đều ≤ `max_words` (7 từ → 3/2/2, không bao giờ còn 1 chữ); `box` vẽ nền mờ sau chữ để đọc được trên nền nhiều chi tiết.

## 3b. Phần cứng & hiệu năng

**Chạy một lần trên mỗi máy mới:** `python scripts/setup_check.py` → kiểm tra ffmpeg, thư viện, giọng đọc, card đồ hoạ, bộ mã hoá (thử mã hoá thật), đo tốc độ và ghi `render_profile.json` (số tiến trình, có dùng `--gpu` không). `render.py` tự đọc file này.

Cài đặt: `pip install -r requirements.txt` + ffmpeg trong PATH (Windows: `winget install Gyan.FFmpeg`). Giọng offline: Linux `apt install festival festvox-us-slt-hts`; Windows/macOS `pip install pyttsx3`. Font Inter đi kèm skill (`assets/fonts`, giấy phép OFL).

| Khâu | Chạy trên | Ghi chú |
|---|---|---|
| Vẽ cảnh (skia) | CPU, song song theo đoạn khung hình trên mọi luồng | Nút thắt chính (~160 ms/khung/luồng ở 1080p). `--gpu` (thử nghiệm): skia OpenGL qua `glfw`, cần driver + màn hình; `setup_check` chỉ bật nếu đo thấy nhanh hơn |
| Hậu kỳ (bloom, grain) | OpenCV nếu có, không thì numpy | `pip install opencv-python-headless` nhanh hơn ~3 lần |
| Mã hoá | x264 (mặc định khi nhiều tiến trình), NVENC / QuickSync / AMF / VideoToolbox khi ít tiến trình | Mã hoá chỉ chiếm ~5–10% thời gian. GPU GeForce giới hạn số phiên mã hoá đồng thời |

**Laptop có MX250:** chip GP108 **không có NVENC** (cũng như MX150/MX230/MX330/GT 1030). Máy sẽ vẽ bằng CPU trên mọi luồng; Intel QuickSync chỉ dùng khi chạy ≤4 tiến trình. Cắm sạc, chọn chế độ hiệu năng cao (tránh hạ xung), lặp bằng `--preview`, render đầy đủ một lần cuối.

**Thuê GPU:** pipeline này cần **nhiều nhân CPU** hơn là GPU mạnh — chọn máy 16–32 vCPU; tốc độ tăng gần tuyến tính theo số nhân. GPU chỉ thật sự đáng tiền khi tự chạy model tạo ảnh/video AI (Flux, Wan…) để thay ảnh vẽ bằng code. NVENC được dùng tự động khi phù hợp.

**Quy tắc viết cảnh nhanh (CPU):**
- Nội dung mờ (tia nắng, bokeh, quầng sáng, sương, phản chiếu) → vẽ qua `soft()` (lớp 1/4 độ phân giải). `light_rays`, `bokeh`, `draw_road` đã làm sẵn.
- Thứ tĩnh (bầu trời, lớp nhà xa, viền tối) → vẽ một lần, lưu cache (`sky`, `vignette`, `make_city_layer` đã cache).
- Tránh vẽ **ảnh co giãn kèm blend screen/add** trực tiếp lên khung lớn (chậm ~10 lần trên CPU) — `soft()` tự xử lý.
- Hạt (mưa, bụi) vài nghìn hạt là ổn; tránh `blur` riêng cho từng hạt nhỏ — dùng quầng cho hạt gần (z cao) thôi.

Đo được (máy thử 2 luồng): khung mẫu 368 → 163 ms; video 20s 169 → 97 s; `--preview` 20s ≈ 20 s.

**Bitrate xuất:** mặc định CRF 20, trần 10 Mbps (khuyến nghị YouTube cho 1080p30 ~8 Mbps). `qa.json` ghi `size_mb`, `video_mbps` — Q11: > 16 Mbps là quá nặng (file 20s > 40 MB sẽ khó xem trên điện thoại).

## 4. Chạy

```bash
cd videos/<slug>
python3 make_assets.py                                   # nếu dùng ảnh tạm
python3 ../../.claude/skills/ai-video-production-pipeline/scripts/render.py storyboard.json --stills
# xem out/still_*.png, sửa, rồi:
python3 ../../.claude/skills/ai-video-production-pipeline/scripts/render.py storyboard.json
```

Sửa sau khi render:
- Sửa hình 1–2 shot: `--shots S03,S04` (chỉ dựng lại các shot đó rồi ghép lại).
- Chỉ sửa nhạc/SFX/âm lượng: `--audio-only` (giữ nguyên hình).
- Sửa lời thoại một shot: thời lượng shot đổi → dựng lại shot đó; các shot khác giữ nguyên.

## 5. QA — kiểm tra bắt buộc ở Bước 7

| # | Kiểm tra | Ngưỡng đạt | Lấy từ |
|---|---|---|---|
| Q1 | Thời lượng thật vs mục tiêu | ±5% (MICRO: ±2s) | `qa.json.duration_error_pct` |
| Q2 | Tốc độ đọc khi đang nói | 135–165 wpm | `wpm_while_speaking` |
| Q3 | Độ dài shot TB | Đúng profile (MICRO/SHORT 1,5–3,5s; LONG 4–6s) | `avg_shot_s` |
| Q4 | Pattern interrupt | MICRO/SHORT ≥ giây ÷ 5; LONG ≥ giây ÷ 45 | `pattern_interrupts` |
| Q5 | Hook | Câu đầu ≤10 từ, có chữ hoặc chuyển động lớn trong 1s đầu | Xem `still_S01_*` |
| Q6 | Loudness | -14 ±1 LUFS, true peak ≤ -1 dBTP | `integrated_lufs`, `true_peak_dbtp` |
| Q7 | Asset thiếu | 0 | `missing_assets` |
| Q8 | Chữ & phụ đề | Không tràn, không che chủ thể, đọc được ở 25% kích thước | Ảnh trích (mục 6) |
| Q9 | Âm thanh | Giọng nổi rõ trên nhạc; không có đoạn câm ngoài ý muốn | Nghe/đo: `ffmpeg -af silencedetect=n=-45dB:d=0.6` |
| Q10 | Khớp kịch bản | Lời thoại = bản đã qua audit Bước 4 | So `storyboard.json` với `audit.md` |
| Q11 | Dung lượng | ≤ 16 Mbps (20s ≤ 40 MB) | `video_mbps`, `size_mb` |

## 6. Trích ảnh để tự xem

```bash
# 3 ảnh: hook, giữa, kết
for t in 0.8 10 18.5; do ffmpeg -v error -y -ss $t -i out/<slug>.mp4 -frames:v 1 out/check_$t.png; done
# contact sheet 1 ảnh/giây
ffmpeg -v error -y -i out/<slug>.mp4 -vf "fps=1,scale=480:-1,tile=5x4" -frames:v 1 out/contact.png
```

Mở và nhìn các ảnh này (công cụ Read) trước khi kết luận Đạt.

## 7. Bài học từ lần chạy thử (stop-time-10s)

- Luôn chạy `--stills` trước: 3/6 lỗi được bắt ở đây (phụ đề đè chủ thể, chữ mồ côi, cảnh tối chậm) mà không tốn một lần render.
- Lỗi chỉ ở âm thanh → `--audio-only` (≈4s) thay vì render lại toàn bộ (≈40s cho 20s video).
- Ảnh vẽ bằng code: kiểm tra mật độ chi tiết nền (cửa sổ, hạt mưa) — quá dày làm phụ đề khó đọc; điểm sáng/va chạm phải đặt đúng vào hành động (tay), không vào đầu nhân vật.
- MICRO: viết đúng số từ mục tiêu, không dùng cận trên.
- Người dùng chê "ảnh tĩnh + zoom" là kém → mặc định dùng animation từng khung (mục 2b) khi chưa có asset AI.
- Bloom theo kênh màu lớn nhất làm áo vàng cháy trắng → bloom theo luminance, ngưỡng 200.
- Hạt phim + CRF 18 không giới hạn bitrate → file 20s nặng 210 MB (86 Mbps), điện thoại không tải được → thêm trần bitrate mặc định và Q11.
- (tiny-human-20s) 4/7 cảnh đặt chủ thể trong dải phụ đề → thêm quy tắc vùng an toàn; bắt được ở `--stills`, không tốn render.

## 8. Định dạng `qa-report.md`

```
# QA — <title>
| # | Kiểm tra | Kết quả | Đạt? |
...
## Lỗi & cách sửa
## Phần tạm cần thay khi sản xuất thật
(giọng TTS offline → ElevenLabs; ảnh vẽ code → ảnh AI theo prompt; nhạc tổng hợp → nhạc thư viện có license)
## Kết luận: SẴN SÀNG ĐĂNG / CẦN SỬA / CHỈ LÀ BẢN DUYỆT NHỊP
```
