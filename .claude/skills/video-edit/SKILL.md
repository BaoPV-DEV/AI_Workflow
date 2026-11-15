---
name: video-edit
description: Sửa một video đã có trong AI Workflow - đổi lời, đổi cảnh, đổi màu, thêm/xoá cảnh, đổi hành động nhân vật - mà chỉ chạm vào phần cần sửa. Dùng khi người dùng nói "sửa cảnh", "đổi", "thêm cảnh", "bỏ cảnh", "cho nhân vật", "chỉnh video".
---

# Sửa video tiết kiệm token

1. `python vf.py show <id>` – danh sách 1 dòng/cảnh. Chỉ khi cần chi tiết: `python vf.py show <id> --scene N`.
2. Sửa bằng Edit trên `workspace/<id>/project_manifest.json`, chỉ khối của cảnh đó. Đổi `voice_text` thì xoá luôn `duration`, `word_timings`, `speech`, `audio_path` của cảnh đó.
3. Tên mới (template, act, hold, style) phải có trong `CATALOG.md`.
4. `python vf.py check <id>` → `python vf.py preview <id> --scenes sNNN` → xem ảnh.
5. Render lại: `python vf.py all <id>` – engine chỉ làm lại cảnh đã đổi (cache).

Màu/kiểu chung cho cả video: đổi `style` hoặc sửa `config/styles/<style>.yaml`, không sửa từng cảnh.
Người dùng có API key và muốn rẻ hơn: `python vf.py edit <id> "yêu cầu"` (agent dùng model nhỏ).
