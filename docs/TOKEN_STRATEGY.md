# Chiến lược tối ưu token

Mục tiêu: Claude chỉ "nghĩ", máy local làm mọi việc lặp lại. Mỗi video mới tốn một lần viết manifest (~3–8k token ra); sửa video tốn vài trăm token.

## 1. Không gửi gì Claude không cần

| Kỹ thuật | Ở đâu trong repo | Tiết kiệm |
|---|---|---|
| Catalog sinh tự động ~1k token thay cho đọc 11 template (~60k ký tự) | `vf catalog` → `CATALOG.md` | ~90% phần tra cứu |
| `vf show` in 1 dòng/cảnh, bỏ `word_timings` | `vf.py show` | timing chiếm 50–70% kích thước manifest |
| Engine tự điền `audio_path`, `duration`, `word_timings` – schema gửi cho model đã bỏ các trường này | `director.authored_schema()` | model không phải sinh/đọc lại |
| `.claudeignore` chặn `workspace/`, media, workflow ComfyUI | `.claudeignore` | tránh phình context |
| Prompt theo thể loại: chỉ nạp `base.md` + 1 file thể loại | `config/prompts/` | — |

## 2. Trả lời có cấu trúc, không văn xuôi

- `vf new` ép model trả qua công cụ `submit_manifest` (tool_choice bắt buộc): không lời dẫn, JSON luôn hợp lệ cú pháp.
- Lỗi ngữ nghĩa (template sai tên…) được gửi lại đúng danh sách lỗi; model sửa tối đa 2 lần.
- Nhân vật diễn bằng tên động tác (`"act": "carry"`), không bằng toạ độ.

## 3. Prompt caching

`LLM.cached_system()` đặt phần tĩnh (quy tắc + thể loại + catalog) lên đầu và gắn `cache_control`; công cụ cũng được cache. Từ video thứ hai trong vòng vài phút, phần này chỉ tính giá đọc cache. Xem tỉ lệ cache trong dòng `📊` sau mỗi lệnh hoặc `vf usage`.

## 4. Định tuyến model

`config/settings.yaml → agent.models`: model lớn cho `plan` (sáng tạo kịch bản), model nhỏ cho `edit` và `translate`. Đổi tên model ở một chỗ khi có bản mới.

## 5. Sửa cục bộ

- `vf edit <id> "..."`: agent chỉ có công cụ xem/sửa **một cảnh**; kết quả công cụ cũ tự rút gọn sau 2 lượt (`Agent._compact`); có trần token/lần chạy (`budget_tokens_per_run`).
- Trong Claude Code: skill `video-edit` buộc chỉ Edit đúng khối cảnh.
- Cache render theo băm nội dung: đổi 1 cảnh chỉ quay lại 1 cảnh (CPU, không phải token, nhưng giúp lặp nhanh).

## 6. Chế độ 0 đồng API

Có gói Claude (Pro/Max) nhưng không muốn trả API:
1. `vf prompt "chủ đề" --genre animation --out p.txt` (hoặc nút *Lấy prompt* trong Web Studio).
2. Dán vào claude.ai, nhận JSON.
3. `vf import file.json` (hoặc dán vào ô *Nhập*).

Hoặc dùng Claude Code trong repo này: skill `video-director` tự viết manifest và chạy engine.

## 7. Thói quen

- Duyệt bằng `vf preview` (vài giây) và `--draft` trước khi render đầy đủ.
- Trong Claude Code: `/compact` sau khi xong một tính năng; mở phiên mới cho mỗi video.
- Thêm template tổng quát thay vì để Claude vẽ SVG riêng cho từng video.
