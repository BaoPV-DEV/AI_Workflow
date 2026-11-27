---
name: video-strategy
description: Lên chiến lược trước khi làm video trong AI Workflow - giải mã DNA kênh mẫu, ý tưởng theo content gap, dàn ý theo hồ sơ thời lượng (MICRO/SHORT/LONG), kiểm duyệt chính sách YouTube/TikTok có tự viết lại, và gói SEO (tiêu đề A/B/C, mô tả, tag, chương, thumbnail). Dùng khi người dùng nói "phân tích kênh", "kênh mẫu", "đối thủ", "dàn ý", "video dài 10 phút", "kiểm duyệt", "chính sách YouTube", "bật kiếm tiền", "vàng tiền", "SEO", "tiêu đề", "thumbnail".
---

# Chiến lược video (từ repo BaoPV-DEV/Skills)

Phần "bộ não" của pipeline `ai-video-production-pipeline`, đã ghép vào AI Workflow. Dựng hình vẫn do engine `vf` làm (không dùng render.py / Blender của repo gốc).
Tài liệu tham chiếu nằm trong `references/` - chỉ đọc đúng mục cần cho bước đang làm.

## Hồ sơ thời lượng

| Profile | Thời lượng | Khung | Đổi hình | Pattern interrupt | Cấu trúc |
|---|---|---|---|---|---|
| MICRO | 15–30s | 9:16/16:9 | 2–3s | 3–5s | Hook → 1 ý → twist → loop |
| SHORT | 31–90s | 9:16 | 1,5–3s | 3–5s | Hook → 3 beat → payoff → loop |
| LONG | 8–12 phút | 16:9 | 4–6s | 30–45s, re-hook ~35% và ~65% | Hook 30s → setup → 3–6 chương → payoff (75–90%) → CTA |

Số từ lời đọc = giây × 145 ÷ 60 (tiếng Việt ~ giây × 2,5). MICRO/SHORT không vượt mục tiêu. Trong manifest: 1 cảnh ≈ 1 shot (3–8s); LONG dùng `title_card_neon` mở mỗi chương để `vf` tự sinh chapters.

## Quy trình

Dừng hỏi người dùng sau bước 1, 2 và 3 (tóm tắt ≤8 dòng), trừ khi họ nói "auto" / "chạy liền".

1. **DNA kênh mẫu** (khi người dùng đưa link kênh/video): đọc `references/channel-analysis-framework.md`, lấy dữ liệu bằng web, chấm 6 trục (Hook, Pacing, Narrative, Tone, Visual/Audio, CTA), rút Content Gap + công thức DNA. Ghi `workspace/_research/<slug>-dna.md`. Không bịa số view, transcript.
2. **Ý tưởng & dàn ý**: đọc mục 1, 3, 4 của `references/seo-and-retention-rules.md`. 5–10 ý tưởng (chấm 6 câu CTR) - hoặc lấy từ `vf trends`/trang Chủ đề thịnh hành. Chốt profile, in bảng số từ, lập dàn ý theo mốc thời gian với hook 4 nhịp (H1 phá khuôn ≤10 từ → H2 bối cảnh → H3 lời hứa → H4 open loop).
3. **Kịch bản**: giao cho skill `video-director` (manifest + `vf check` + `vf preview`), kèm dàn ý và profile ở bước 2.
4. **Kiểm duyệt chính sách** - không bỏ qua: `python vf.py audit <id>` (thêm `--apply` để tự thay lời đọc an toàn), hoặc Studio → Render & đăng → 🛡 Kiểm duyệt. Muốn rà sâu (prompt ảnh, nhạc, thumbnail) thì đọc `references/policy-checklist.md` và tự rà theo mục A–E, kết luận theo mẫu mục G.
5. **SEO & đóng gói**: Studio → Render & đăng → Viết gói đăng (đã áp quy tắc mục 5–7 của seo-and-retention-rules) + 🎨 Thumbnail thu hút. Viết tay thì theo mục 2, 5–8.
6. **Dựng & QA**: `vf all <id>`; kiểm thời lượng thật lệch ≤5% so với mục tiêu, hook đổi hình ≥8 lần trong 30s đầu (LONG).

## Nguyên tắc

- Học công thức kênh mẫu, không chép câu chữ, nhân vật, thương hiệu. Trích ≤15 từ làm bằng chứng.
- Không dùng mặt, giọng, tên người thật; không IP phim/game; nhạc phải có license.
- Kiểm duyệt là rà soát theo chính sách đã biết, không phải tư vấn pháp lý.
- Trả lời tiếng Việt, ngắn.
