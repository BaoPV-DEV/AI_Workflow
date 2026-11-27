# AI Workflow – quy tắc cho Claude

Claude = bộ não (kịch bản → `project_manifest.json`). Engine local = cơ bắp (giọng, phụ đề, hình, ghép) – 0 token.

- Lệnh: `python vf.py <lệnh>` (Windows: `vf`). Xem `python vf.py -h`.
- Tên template/act/style/preset hợp lệ: chỉ đọc `CATALOG.md`. Không mở file template để tra cứu.
- Xem project: `vf show <id>` hoặc `vf show <id> --scene N`. KHÔNG đọc `workspace/` trực tiếp, không đọc `word_timings`.
- Sửa = chỉ đúng cảnh/trường được yêu cầu. Không viết lại cả manifest, không sinh lại pipeline.
- Sau khi sửa: `vf check <id>`, rồi `vf preview <id> --scenes sNNN` và xem ảnh trong `preview/`.
- Sửa engine/template: chỉ file được chỉ định; thêm template xong chạy `vf catalog`.
- Kênh mẫu, dàn ý video dài, kiểm duyệt chính sách, SEO: skill `video-strategy` (nguồn: repo BaoPV-DEV/Skills, cập nhật `vf skills-sync`). Trước khi đăng: `vf audit <id>`.
- Chủ đề hot: `vf trends --geo VN`; lọc theo `config/prompts/ideas.md` (bỏ chết chóc, chính trị, tin đồn, trẻ em).
- Bản ngôn ngữ khác: tự dịch rồi dùng `engine.agent.director.translate(id, lang, texts=...)`, hoặc `vf translate`.
- Trả lời người dùng bằng tiếng Việt, ngắn.
