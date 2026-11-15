---
name: video-template
description: Tạo hoặc sửa template cảnh HTML/CSS/SVG (motion graphics) trong templates/html_scenes cho AI Workflow. Dùng khi người dùng muốn hiệu ứng, kiểu cảnh, layout hoặc template mới, hoặc nói "thêm template", "hiệu ứng mới", "sửa template".
---

# Template cảnh

Hợp đồng (bắt buộc):
- File `templates/html_scenes/<tên>.html`, nạp `_lib/base.css`, `_lib/runtime.js` (và `_lib/stickman.js` nếu có người que).
- `<script type="application/json" data-doc>` gồm `desc` (1 câu) và `props` (tên: mô tả ngắn) – đây là nguồn của CATALOG.
- `<script type="application/json" data-demo>` – input mẫu để xem thử.
- `VF.scene({ setup(input, root), draw(t, input) })`. Mọi chuyển động là hàm của `t` (dùng `VF.prog`, `VF.at`, `VF.ease`); không setTimeout/requestAnimationFrame. CSS animation và GSAP được runtime tua tự động.
- Màu chỉ dùng biến `--bg --ink --a1 --a2 --a3`, chữ dùng class `fs-xl/l/m/s` để tự co theo khung 9:16 và 16:9.
- Vùng an toàn dọc: chữ quan trọng trong 12%–75% chiều cao (dưới là phụ đề + nút của nền tảng).

Quy trình: mở template gần giống nhất làm mẫu (chỉ 1 file) → viết file mới → `python vf.py catalog` → tạo project thử 1 cảnh → `vf preview` ở 2-3 mốc `--at 0.2/0.6/0.95` cho cả 9:16 và 16:9 → xem ảnh → sửa.
Giữ template tổng quát (nhận props), không gắn với một video cụ thể.
