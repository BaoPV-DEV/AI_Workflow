---
name: ai-video-production-pipeline
description: Runs an end-to-end AI video production pipeline for English YouTube content (micro 15–30s tests, Shorts, and 8–12 min long-form) - benchmark channel DNA extraction, content-gap ideation and timed outline, storyboard script with AI image/video prompts, policy and copyright audit with auto-rewrite, SEO packaging, then automated rendering (voiceover, motion, captions, music, SFX) and a quality-control report. Use when the user asks to analyze competitor or benchmark channels, brainstorm video ideas, outline or write a video script, create AI visual prompts or a storyboard, check a video for YouTube policy or monetization risk, write titles, thumbnails, descriptions and tags, or render, assemble or QA a video; also triggers on "phân tích kênh", "kênh mẫu", "ý tưởng video", "dàn ý", "kịch bản", "storyboard", "prompt ảnh", "kiểm duyệt", "chính sách YouTube", "bật kiếm tiền", "SEO video", "tiêu đề", "thumbnail", "dựng video", "render video", "xuất video", "video thử".
---

# AI Video Production Pipeline

Pipeline 7 giai đoạn biến 5 kênh mẫu thành một video YouTube tiếng Anh hoàn chỉnh: 5 giai đoạn tiền kỳ có checkpoint kiểm duyệt, rồi dựng tự động và kiểm tra chất lượng.

## Hồ sơ thời lượng (Duration Profiles)

Chọn profile ngay khi biết thời lượng. Mọi con số ở các bước sau lấy từ profile.

| Profile | Thời lượng | Khung | Shot TB | Pattern interrupt | Cấu trúc | Dùng cho |
|---|---|---|---|---|---|---|
| **MICRO** | 15–30s | 16:9 hoặc 9:16 | 2–3s | mỗi 3–5s | Hook → 1 ý → twist/payoff → loop/CTA | Test chất lượng, teaser, quảng cáo |
| **SHORT** | 31–90s | 9:16 | 1,5–3s | mỗi 3–5s | Hook → 3 beat → payoff → loop | YouTube Shorts / TikTok |
| **LONG** | 8–12 phút (mặc định 10) | 16:9 | 4–6s | mỗi 30–45s | Hook 30s → setup → 3–6 chương → payoff → CTA | Video chính của kênh |

Thời lượng ngoài các khoảng trên: nội suy giữa 2 profile gần nhất và ghi rõ giả định.

### Quy đổi thời lượng → số từ → số shot (bắt buộc)

- Số từ voiceover = giây × 145 ÷ 60 (khoảng chấp nhận: ×140 đến ×150). MICRO/SHORT trừ 10% cho khoảng thở, SFX và text-only beat.
- Số shot = giây ÷ độ dài shot trung bình của profile.
- LONG: scene storyboard = giây ÷ 20 (mỗi scene 15–25s gồm 3–5 shot). MICRO/SHORT: mỗi hàng storyboard = 1 shot.

| Thời lượng | Số từ (min–max) | Mục tiêu | Shot |
|---|---|---|---|
| 20 giây (MICRO) | 42–50 | 44 | 7–10 @2–3s |
| 60 giây (SHORT) | 126–135 | 130 | 20–30 @2–3s |
| 8 phút | 1.120–1.200 | 1.160 | 96 @5s (24 scene) |
| 10 phút | 1.400–1.500 | 1.450 | 120 @5s (30 scene) |
| 12 phút | 1.680–1.800 | 1.740 | 144 @5s (36 scene) |

MICRO/SHORT: số từ **không vượt mục tiêu** (không dùng cận trên) — khoảng nghỉ giữa shot, `min_duration` và chữ on-screen luôn cộng thêm thời gian (chạy thử: 48 từ cho 20s ra 21,4s).

In bảng này cho thời lượng đã chọn ở đầu Bước 2, đếm lại số từ thực tế ở cuối Bước 3, và đo lại thời lượng thật ở Bước 7. Lệch quá ±5% thì sửa trước khi chuyển bước.

## Thông số mặc định

| Thông số | Mặc định |
|---|---|
| Nền tảng | YouTube; LONG 16:9 1080p, SHORT 9:16 1080×1920 |
| Ngôn ngữ / thị trường | English (US/Global); phụ đề tuỳ chọn: es, pt-BR, de, fr, ja, ko, vi, hi, id |
| Tốc độ đọc | 140–150 wpm |
| Âm lượng xuất | -14 LUFS, true peak ≤ -1,5 dBTP |

### Bộ công cụ đề xuất

Prompt viết trung lập công cụ; khi người dùng chọn công cụ cụ thể thì thêm tham số riêng.

| Khâu | Production (khuyến nghị) | Offline / animatic (có sẵn trong workspace) |
|---|---|---|
| Kịch bản | Claude | Claude |
| Giọng đọc | ElevenLabs (voice clone chính chủ hoặc voice có license thương mại) | Festival HTS / espeak-ng — chỉ để duyệt nhịp |
| Ảnh | Midjourney, Flux, Ideogram (ảnh có chữ) | Cảnh animation vẽ bằng code (`scripts/anim_kit.py`) |
| Nhân vật | Ảnh/clip AI theo Consistency Bible | Dàn nhân vật 3D riêng cho từng chủ đề: `cast/<id>.json` → `scripts/hero3d/make_character.py` (skill `ai-video-character`) |
| Video AI | Kling, Runway, Google Veo, Luma (image-to-video) | Animation từng khung: hạt, parallax, nhân vật, hậu kỳ bloom/grain (`anim_kit.py` + `scenes.py`) |
| Dựng | CapCut Pro, Premiere, DaVinci Resolve | `scripts/render.py` (ffmpeg) |
| Nhạc / SFX | Epidemic Sound, Artlist, YouTube Audio Library | Nhạc nền và SFX tự tổng hợp trong `render.py` (không vướng bản quyền) |
| Phụ đề | Whisper / CapCut → SRT từng ngôn ngữ | SRT xuất tự động từ `render.py` |

### Ràng buộc riêng đề xuất

1. Mỗi video có giá trị gia tăng của con người: góc nhìn, phân tích, dữ liệu, hoặc câu chuyện riêng.
2. Tối thiểu 30% shot là hình ảnh "có chủ đích" (biểu đồ, bản đồ, so sánh, minh hoạ dữ kiện).
3. Mọi dữ kiện có nguồn trong cột Ghi chú và trong mô tả video.
4. Có Consistency Bible cho nhân vật, bối cảnh lặp lại.
5. Không dùng giọng, mặt, tên người thật hay thương hiệu, IP game/phim (Minecraft, Marvel…) khi chưa có quyền — kể cả khi kênh mẫu dùng.

## Lưu trạng thái

Thư mục dự án: `videos/<slug>/` (hoặc nơi người dùng chỉ định). Ghi lần lượt:
`project-brief.md` → `channel-dna.md` → `ideas.md` → `outline.md` → `storyboard.md` + `storyboard.json` → `audit.md` → `package.md` → `assets/` → `out/` + `qa-report.md`.
Mở lại skill thì đọc các file đã có để tiếp tục đúng giai đoạn. Không commit file `.mp4`, `.wav` vào git.

## Quy trình

Sau mỗi bước 1–5, dừng ở **CHECKPOINT**: tóm tắt ≤8 dòng, liệt kê quyết định cần chốt, chờ trả lời. Chỉ bỏ qua checkpoint khi người dùng nói rõ "chạy liền", "auto", "không cần hỏi", hoặc phiên chạy không có người theo dõi — khi đó tự chọn phương án tốt nhất, ghi lý do vào file của bước đó.

### Bước 1 — Giải mã DNA 5 kênh mẫu

Đọc `references/channel-analysis-framework.md`.

1. Thu thập từng link bằng công cụ web: tiêu đề, kênh, mô tả, chương, thời lượng, transcript nếu có; tìm thêm 5–10 tiêu đề nổi bật của kênh. YouTube thường chặn bot: thử link `youtu.be`, link `watch?v=` và tìm kiếm theo ID/tiêu đề; ghi rõ link nào lấy được, link nào không.
2. Thiếu dữ liệu: đưa người dùng mẫu dán trong framework. Ở chế độ auto, phân tích phần lấy được, suy ra ngách từ video đọc được, đánh dấu độ tin cậy thấp. Không bịa transcript, số view, số liệu kênh.
3. Chấm 6 trục (Hook, Pacing, Narrative, Tone, Visual/Audio, CTA) kèm bằng chứng; tổng hợp Persona, pattern chung, Content Gap và Công thức DNA.
4. Ghi `channel-dna.md`.

**CHECKPOINT 1:** xác nhận DNA, chọn mức bám (sát / cân bằng / khác biệt mạnh).

### Bước 2 — Ý tưởng & Dàn ý

Đọc `references/seo-and-retention-rules.md` (mục 1, 3, 4).

1. Đề xuất 5–10 ý tưởng: working title, gap khai thác, lời hứa (1 câu), keyword chính, CTR ước lượng + lý do, độ khó sản xuất AI (1–5), rủi ro chính sách. Xếp hạng, đánh dấu khuyến nghị.

**CHECKPOINT 2a:** chọn ý tưởng và thời lượng → chốt profile.

2. In bảng quy đổi cho thời lượng đã chốt.
3. Lập outline theo timestamp khớp tổng thời lượng, theo cấu trúc của profile. Mỗi mục: timestamp, mục tiêu, số từ phân bổ (giây × 145 ÷ 60), pattern interrupt dự kiến. Tổng số từ = mục tiêu ±2%.

**CHECKPOINT 2b:** duyệt outline.

### Bước 3 — Kịch bản & Prompt AI

1. Viết **Consistency Bible** nếu có nhân vật, bối cảnh lặp lại: mô tả cố định chèn nguyên văn vào mọi prompt; bảng màu; phong cách; ống kính mặc định.
   - **Nhân vật theo chủ đề:** thiết kế dàn nhân vật riêng cho video này bằng skill `ai-video-character` (đọc `references/character-spec.md`): mỗi nhân vật một `cast/<id>.json` hợp bối cảnh, tương phản với bảng màu cảnh, có 1 món nhận diện; liệt kê đúng các bộ `[anim, view, light]` storyboard cần. Duyệt bằng `sheet.png` cùng CHECKPOINT 3. Có thể dùng lại mẫu trong `assets/cast-presets/`.
2. Viết `storyboard.md`:

| # | Mốc thời gian | Lời thoại (Voiceover) | Prompt AI (ảnh/video) | SFX / Nhạc / Chữ trên màn hình |
|---|---|---|---|---|

   - **Prompt AI** (tiếng Anh) đủ 6 phần theo thứ tự: `[Subject + consistency tag], [Action/motion], [Setting], [Camera: shot size, angle, lens, movement], [Lighting + mood], [Style + aspect ratio]` + negative prompt khi cần. Cảnh video ghi thời lượng clip.
   - **Ghi chú:** nhạc (mood, BPM), SFX cụ thể, text on-screen (≤6 từ; ≤3 từ với MICRO/SHORT), nguồn số liệu, `[PI]` tại pattern interrupt.
   - LONG: 1 hàng = 1 scene, liệt kê shot a/b/c. MICRO/SHORT: 1 hàng = 1 shot.
3. Viết lời thoại cho tai nghe: câu ngắn (12–16 từ với LONG, ≤10 từ với MICRO/SHORT), ngôi "you", một ý mỗi câu; ghi phiên âm cho từ khó với TTS.
4. Cuối file: tổng số từ, số shot, thời lượng ước tính, số `[PI]`, danh sách asset, bản voiceover liền mạch, 3 phương án hook nếu là LONG.
5. Xuất song song `storyboard.json` theo schema trong `references/render-pipeline.md` (dùng cho Bước 6).

**CHECKPOINT 3:** duyệt kịch bản.

### Bước 4 — Kiểm duyệt Chính sách & Bản quyền

Đọc toàn bộ `references/policy-checklist.md`. Không bỏ qua bước này, kể cả ở chế độ auto.

1. Rà mọi câu thoại, prompt, tiêu đề dự kiến, nhạc/SFX.
2. Ghi `audit.md`: `[Vị trí | Mục | Mức (Chặn/Rủi ro/Lưu ý) | Vấn đề | Bản viết lại an toàn]`.
3. **Auto-Rewrite:** mọi mục Chặn/Rủi ro có bản viết lại, áp ngay vào `storyboard.md` và `storyboard.json`; giữ ý và nhịp, số từ lệch ≤10%.
4. Kết luận theo mẫu mục G của checklist. Đây là rà soát theo chính sách đã biết, không phải tư vấn pháp lý; có công cụ web thì kiểm tra trang chính sách hiện hành.

**CHECKPOINT 4:** xác nhận bản đã sửa.

### Bước 5 — SEO & Đóng gói

Đọc mục 2, 5–8 của `references/seo-and-retention-rules.md`. Ghi `package.md`:

1. 3 tiêu đề A/B/C (≤60 ký tự, keyword trong 40 ký tự đầu, 3 cơ chế: tò mò / con số-kết quả / mâu thuẫn), khớp lời hứa của hook.
2. 3 concept thumbnail + prompt AI đầy đủ (LONG 1280×720; SHORT: frame bìa 9:16 + chữ trong vùng an toàn).
3. Mô tả SEO (2 dòng đầu ≤150 ký tự; tóm tắt; chapters nếu ≥3 phút; nguồn; AI disclosure; credits nhạc; 3 hashtag — SHORT thêm `#Shorts`).
4. 10–15 tag (≤500 ký tự). 5. Chapters (LONG). 6. Gói dịch tiêu đề/mô tả cho ngôn ngữ phụ đề đã chọn.
7. Checklist upload: file, SRT, thumbnail A/B/C cho Test & Compare, ô Altered content, end screen, cards, playlist, giờ đăng (ET).

**CHECKPOINT 5:** duyệt gói xuất bản.

### Bước 6 — Dựng video (Render)

Đọc `references/render-pipeline.md`. Máy mới: chạy `python scripts/setup_check.py` một lần (kiểm tra công cụ, đo tốc độ, lưu cấu hình nhanh nhất). Khi lặp sửa dùng `--preview` (nửa kích thước, 15 fps, nhanh ~6–8 lần); render đầy đủ một lần cuối.

1. Chuẩn bị asset theo `storyboard.json`:
   - Có ảnh/clip từ công cụ AI của người dùng: đặt vào `assets/<shot_id>.png|.jpg|.mp4`.
   - Chưa có: đưa người dùng danh sách prompt để tạo (theo thứ tự shot), **hoặc** dựng **animation từng khung** bằng `scripts/anim_kit.py` (nhân vật: `make_character.py sprites cast/<id>.json` rồi `ak.character(...)`, xem mục 2c render-pipeline): viết `scenes.py` trong thư mục dự án, mỗi shot một hàm `sXX(t, dur, ctx)` và trỏ `"scene": "scenes.py:sXX"` trong storyboard (xem mục 2b của render-pipeline). Không dùng ảnh tĩnh + zoom làm sản phẩm cuối — người xem thấy ngay là "slideshow".
   - Giọng: ElevenLabs (API key hoặc file `voice/<shot_id>.wav`); không có thì dùng TTS offline và ghi rõ đây là giọng tạm.
2. Vẽ trước ảnh xem thử ở các shot dày đặc nhất: `python3 scripts/render.py storyboard.json --stills`. Mở và xem từng ảnh (chữ tràn, che mặt chủ thể, độ tương phản, vùng an toàn) rồi sửa trước khi render.
3. Render 1 lần: `python3 scripts/render.py storyboard.json`. Đầu ra trong `out/`: `<slug>.mp4`, `<slug>.srt`, `qa.json`.

### Bước 7 — Kiểm tra chất lượng (QA) & bàn giao

1. Đọc `out/qa.json` và chạy các kiểm tra trong mục QA của `references/render-pipeline.md`: thời lượng thật so với mục tiêu (±5%), wpm 135–160, độ dài shot TB đúng profile, số pattern interrupt, loudness, dung lượng/bitrate, ảnh trích ở hook / giữa / kết.
2. Ghi `qa-report.md`: bảng Đạt / Không đạt, danh sách lỗi kèm cách sửa, và phần nào là bản tạm (giọng, ảnh) cần thay khi sản xuất thật.
3. Lỗi sửa được thì sửa và chỉ render lại shot hỏng (hoặc âm thanh) theo hướng dẫn trong render-pipeline.
4. Gửi video, SRT và `qa-report.md` cho người dùng. Đề xuất bước tiếp: thay asset tạm bằng asset production, theo dõi CTR/AVD sau 48h và 7 ngày, ghi bài học vào `channel-dna.md`.

## Nguyên tắc chung

- Không bịa số liệu kênh, số view, transcript hay nguồn. Thiếu dữ liệu thì nói rõ.
- Trích từ video/transcript của kênh khác ≤15 từ mỗi lần, chỉ làm bằng chứng phân tích.
- Học cấu trúc và công thức của kênh mẫu, không sao chép câu chữ, nhân vật, thương hiệu.
- Trả lời người dùng bằng tiếng Việt; kịch bản, prompt, SEO bằng tiếng Anh trừ khi được yêu cầu khác.
