---
name: video-cast
description: Thiết kế nhân vật người que, nhân vật 3D Blender và động tác mới cho AI Workflow (library/characters.json, library/cast3d, library/actions.json). Dùng khi người dùng nói "tạo nhân vật", "nhân vật 3D", "nhân vật thật", "Blender", "thêm động tác", "nhân vật làm gì", "diễn xuất", "character", "pose mới".
---

# Nhân vật & động tác

Nhân vật (`library/characters.json` → dùng trong manifest `cast: {"Tên": {"preset": "...", ...ghi đè}}`):
- Phân vai theo chức năng: người học (nhỏ scale 0.78-0.85, màu tươi), người biết (1.0-1.08, màu trầm), người phản bác (mũ/dáng lạ).
- Phân biệt bằng hình bóng: chiều cao, mũ (`hat`), `head` hollow/filled/solid. Hai nhân vật không trùng `shirt`.
- Tên 1-2 âm tiết, không dấu.
- Màu áo tương phản với nền cảnh hay dùng (nền xanh → đỏ/cam/vàng, nền tối → màu sáng, nền ấm → xanh lam/trắng); engine tự thêm viền sáng và làm dịu nền, nhưng chọn màu đúng vẫn quan trọng.

Động tác (`library/actions.json`, rig 11 khớp, dùng chung mọi nhân vật):
- Góc độ: 0 buông xuống, 90 chỉa ngang ra trước, 180 giơ thẳng lên, âm = ra sau. `fa/ba` tay trước/sau (1 trên, 2 dưới), `fl/bl` chân, `lean`, `head`, `lift` (nhảy). Tay tự cộng `lean`.
- Tư thế giữ: 1 frame. Lặp (chạy, gõ, vẫy): `loop: true` + 2-4 frame `dur` 0.1-0.5 s. Ngồi: thêm `"seated": true` (tự vẽ ghế).
- Không tạo lại tên đã có; tên đồng nghĩa → thêm vào `aliases`.

Kiểm: project thử 1 cảnh `stickman_stage` với act mới → `vf preview --at 0.3` và `--at 0.8` → xem ảnh. Xong chạy `python vf.py catalog`.

## Nhân vật 3D (Blender, từ repo BaoPV-DEV/Skills)

Người thật dựng bằng MakeHuman CC0 + Blender Cycles, render 1 lần thành ảnh động, mọi video dùng lại. Chỉ chạy trong cảnh `stickman_stage`; 49 act tự quy về 12 động tác 3D gần nhất (idle, talk, walk, run, wave, point, celebrate, look_up, arms_up, push, crouch, fall).

1. Cài 1 lần: `python vf.py char3d setup` (hoặc Studio → 🧍 Nhân vật 3D → Cài Blender). `vf char3d status` xem có card NVIDIA không (CPU chậm hơn ~6 lần).
2. Thiết kế: `vf char3d new <id> --base mia --name "<Tên>"` rồi sửa `library/cast3d/<id>.json` theo `engine/hero3d` (bảng giá trị: tóc, áo `length/sleeves/collar/hood/material`, quần, giày, phụ kiện). Quy tắc: hợp bối cảnh chủ đề, màu áo tương phản nền, 1 món nhận diện; người hư cấu, không giống người thật/nhân vật có bản quyền, không logo; dưới 18 tuổi thì trang phục, tư thế phù hợp lứa tuổi.
3. Duyệt: `vf char3d sheet <id>` → xem `workspace/_cast3d/<id>/sheet.png` (thủng áo, tóc, màu). Sửa JSON đến khi ổn rồi mới render động tác (tốn thời gian).
4. Render: `vf char3d sprites <id> [--profile co_ban|day_du] [--quality nhap|chuan|cao]` (bộ đã có thì bỏ qua). Xong tự chạy `vf catalog`.
5. Dùng: manifest `"cast": {"Mia": {"model3d": "mia"}}`; có thể trộn với người que trong cùng cảnh. Kiểm bằng `vf preview <id>`.
