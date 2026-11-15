---
name: video-cast
description: Thiết kế nhân vật người que và động tác mới cho AI Workflow (library/characters.json, library/actions.json). Dùng khi người dùng nói "tạo nhân vật", "thêm động tác", "nhân vật làm gì", "diễn xuất", "character", "pose mới".
---

# Nhân vật & động tác

Nhân vật (`library/characters.json` → dùng trong manifest `cast: {"Tên": {"preset": "...", ...ghi đè}}`):
- Phân vai theo chức năng: người học (nhỏ scale 0.78-0.85, màu tươi), người biết (1.0-1.08, màu trầm), người phản bác (mũ/dáng lạ).
- Phân biệt bằng hình bóng: chiều cao, mũ (`hat`), `head` hollow/filled/solid. Hai nhân vật không trùng `shirt`.
- Tên 1-2 âm tiết, không dấu.

Động tác (`library/actions.json`, rig 11 khớp, dùng chung mọi nhân vật):
- Góc độ: 0 buông xuống, 90 chỉa ngang ra trước, 180 giơ thẳng lên, âm = ra sau. `fa/ba` tay trước/sau (1 trên, 2 dưới), `fl/bl` chân, `lean`, `head`, `lift` (nhảy). Tay tự cộng `lean`.
- Tư thế giữ: 1 frame. Lặp (chạy, gõ, vẫy): `loop: true` + 2-4 frame `dur` 0.1-0.5 s. Ngồi: thêm `"seated": true` (tự vẽ ghế).
- Không tạo lại tên đã có; tên đồng nghĩa → thêm vào `aliases`.

Kiểm: project thử 1 cảnh `stickman_stage` với act mới → `vf preview --at 0.3` và `--at 0.8` → xem ảnh. Xong chạy `python vf.py catalog`.
