# AI Workflow – quy tắc cho Claude

Claude = bộ não (kịch bản → `project_manifest.json`). Engine local = cơ bắp (giọng, phụ đề, hình, ghép) – 0 token.

- Lệnh: `python vf.py <lệnh>` (Windows: `vf`). Xem `python vf.py -h`.
- Tên template/act/style/preset hợp lệ: chỉ đọc `CATALOG.md`. Không mở file template để tra cứu.
- Xem project: `vf show <id>` hoặc `vf show <id> --scene N`. KHÔNG đọc `workspace/` trực tiếp, không đọc `word_timings`.
- Sửa = chỉ đúng cảnh/trường được yêu cầu. Không viết lại cả manifest, không sinh lại pipeline.
- Sau khi sửa: `vf check <id>`, rồi `vf preview <id> --scenes sNNN` và xem ảnh trong `preview/`.
- Sửa engine/template: chỉ file được chỉ định; thêm template xong chạy `vf catalog`.
- Trả lời người dùng bằng tiếng Việt, ngắn.
