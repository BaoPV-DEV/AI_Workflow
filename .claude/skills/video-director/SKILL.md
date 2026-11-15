---
name: video-director
description: Tạo video mới từ một chủ đề - viết kịch bản và project_manifest.json cho engine AI Workflow, rồi xem trước và render. Dùng khi người dùng nói "làm video về", "tạo video mới", "viết kịch bản", "làm short", "new video".
---

# Đạo diễn video mới

0. Người dùng chưa có chủ đề / muốn chủ đề hot: `python vf.py trends --geo VN --limit 30`, chọn 3-5 ý theo `config/prompts/ideas.md`, đề xuất kèm hook, để người dùng chọn.
1. Chốt nhanh (hỏi 1 lần, tối đa 3 câu, cái nào người dùng đã nói thì bỏ): thể loại (animation | motion_graphic | news | explainer), tỉ lệ 9:16/16:9, độ dài (mặc định 45 s), style.
2. Đọc đúng 3 file, không đọc thêm: `config/prompts/base.md`, `config/prompts/<thể loại>.md`, `CATALOG.md`.
3. Nếu cần dữ kiện thời sự/số liệu: tìm kiếm web, giữ nguồn.
4. Viết `workspace/<id>/project_manifest.json` (id: không dấu, gạch dưới). Không viết audio_path, duration, word_timings.
5. `python vf.py check <id>` → sửa đến khi hợp lệ.
6. `python vf.py preview <id>` → xem `workspace/<id>/preview/_sheet.jpg`. Kiểm: chữ tràn, cảnh trống, 2 cảnh liền giống nhau, nhân vật bị cắt. Sửa từng cảnh bằng Edit.
7. Đa ngôn ngữ: dịch voice_text + chữ trên màn hình, gọi `python -c "from engine.agent.director import translate; translate('<id>','en',texts=[...])"` hoặc `vf translate <id> --to en`.
8. Báo người dùng: hook, số cảnh, thời lượng ước tính, lệnh tiếp theo `vf all <id>` (hoặc tự chạy nếu có shell trên máy họ).

Ngân sách: cả quy trình nên < 15k token. Không đọc template HTML, không đọc engine/.
