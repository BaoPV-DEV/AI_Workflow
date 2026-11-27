# Channel Analysis Framework

Bộ khung dùng thống nhất ở Bước 1 cho mọi lần chạy. Mỗi kênh chấm 6 trục, thang 1–5, kèm bằng chứng. Không có bằng chứng → ghi "N/A (thiếu dữ liệu)", không đoán điểm.

## 1. Dữ liệu cần thu thập cho mỗi kênh

| Trường | Nguồn ưu tiên |
|---|---|
| Tên kênh, URL kênh, ngách | Trang video / trang kênh |
| Video mẫu: tiêu đề, thời lượng, ngày đăng, view | Trang video |
| Transcript (ít nhất 2 phút đầu + 1 đoạn giữa + phần kết) | Transcript tool / người dùng dán |
| 5–10 tiêu đề phổ biến nhất & gần nhất | Trang kênh (Popular / Latest) |
| Mô tả thumbnail (bố cục, chữ, màu, khuôn mặt) | Quan sát / người dùng mô tả |
| Tần suất đăng | Ngày đăng các video gần nhất |

### Mẫu dán dữ liệu (khi không truy xuất được)

Yêu cầu người dùng dán cho từng kênh theo mẫu:

```
KÊNH [số]: [tên kênh]
Video mẫu: [tiêu đề] | [thời lượng] | [view] | [ngày đăng]
Transcript 0:00–2:00:
...
Transcript đoạn giữa (khoảng 1–2 phút):
...
Transcript 1 phút cuối:
...
10 tiêu đề nổi bật:
1. ...
Thumbnail: [mô tả ngắn: có mặt người? chữ gì? màu chủ đạo?]
Hình ảnh trong video: [stock / AI / hoạt hình / quay thật / motion graphics]
Nhạc & giọng: [giọng nam/nữ, nhanh/chậm, nhạc gì]
```

Thiếu transcript vẫn phân tích được trục 4–6 từ tiêu đề, thumbnail và mô tả; ghi rõ độ tin cậy thấp cho trục 1–3.

## 2. Sáu trục chấm điểm

### Trục 1 — Hook (0–15 giây đầu)

Xác định loại hook (có thể nhiều loại):
- **Cold open:** vào thẳng cảnh/khoảnh khắc kịch tính
- **Bold claim:** khẳng định gây sốc ("Everything you know about X is wrong")
- **Question/curiosity gap:** câu hỏi chưa có lời đáp
- **Stakes:** nêu hậu quả / cái giá
- **Result preview:** cho xem kết quả cuối trước
- **Story in media res:** bắt đầu giữa câu chuyện
- **Contrast:** "Most people think X. Actually Y."

Đo: giây đến câu hook đầu tiên; giây nêu lời hứa (promise); có xuất hiện tên kênh/intro dài không (trừ điểm nếu intro >5 giây).

| Điểm | Tiêu chí |
|---|---|
| 5 | Hook ≤3s, lời hứa rõ ≤15s, có open loop kéo qua 30s, hình ảnh khớp lời |
| 4 | Hook ≤5s, lời hứa ≤20s |
| 3 | Hook có nhưng chậm (5–10s) hoặc lời hứa mơ hồ |
| 2 | Mở đầu chào hỏi / intro kênh trước nội dung |
| 1 | Không có hook nhận diện được |

### Trục 2 — Retention Pacing

Đo trên một đoạn mẫu 60 giây:
- Số lần đổi cảnh/shot (cuts per minute)
- Số pattern interrupt (đổi nhạc, SFX, zoom, đồ hoạ, đổi góc, câu hỏi tu từ)
- Khoảng cách giữa các open loop / mini-hook (giây)
- Có "re-hook" ở giữa video không (khoảng 40–60% thời lượng)

| Điểm | Tiêu chí (long-form) |
|---|---|
| 5 | 12–20 cuts/phút, interrupt mỗi 20–40s, open loop mỗi chương |
| 4 | 8–12 cuts/phút, interrupt mỗi 40–60s |
| 3 | 5–8 cuts/phút, ít open loop |
| 2 | Cảnh tĩnh dài >15s thường xuyên |
| 1 | Gần như không đổi nhịp |

### Trục 3 — Narrative Structure

Xác định khung kể chuyện chính:
- **Listicle** (Top N, đếm ngược)
- **Chronological** (dòng thời gian)
- **Mystery/Investigation** (câu hỏi → manh mối → lời giải)
- **Problem → Agitate → Solution**
- **Hero's journey / character arc**
- **Explainer layered** (đơn giản → phức tạp)
- **Comparison / versus**

Ghi: số chương, độ dài trung bình mỗi chương, vị trí payoff lớn nhất (% thời lượng), cách chuyển chương (câu nối mẫu).

Điểm 5 = cấu trúc rõ, mỗi chương có hook mở + payoff, payoff lớn nhất ở 75–90% thời lượng.

### Trục 4 — Tone of Voice

Mô tả bằng 4 thang đo (1–5 mỗi thang):
- Trang trọng ↔ Thân mật
- Nghiêm túc ↔ Hài hước
- Trung lập ↔ Quan điểm mạnh
- Chậm rãi ↔ Dồn dập

Ghi thêm: ngôi kể (I / we / you / ngôi thứ ba), độ dài câu trung bình, từ vựng đặc trưng, câu cửa miệng lặp lại. Tốc độ đọc ước tính (wpm) nếu có transcript + thời lượng.

Điểm của trục này = độ nhất quán và độ phù hợp với audience (không phải "càng hài càng tốt").

### Trục 5 — Visual & Audio Style

- Nguồn hình: AI image / AI video / stock / hoạt hình 2D / 3D / quay thật / screen recording / motion graphics (ước % mỗi loại)
- Phong cách: photoreal, cinematic, illustration, minimal, documentary…
- Bảng màu chủ đạo, kiểu chữ on-screen, tần suất text on-screen
- Nhạc: thể loại, mức độ (nền / nổi), thay đổi theo chương?
- SFX: dày / vừa / ít
- Giọng: người thật / TTS, giới tính, chất giọng
- Thumbnail: công thức (mặt + cảm xúc, vật thể lớn, chữ ≤4 từ, mũi tên/khoanh tròn, tương phản)

Điểm 5 = phong cách nhận diện được ngay, nhất quán, chất lượng cao, phục vụ nội dung.

### Trục 6 — CTA

- Số lần CTA, vị trí (giây hoặc %)
- Loại: subscribe / like / comment prompt / video tiếp theo / sponsor / sản phẩm
- Cách lồng ghép: trực tiếp vs gắn vào giá trị ("if this helped…")
- End screen: có / không, dẫn đến đâu

Điểm 5 = CTA ≤3 lần, không chen trong 30s đầu, gắn vào giá trị, end screen dẫn tới video liên quan.

## 3. Audience Persona

Tổng hợp từ cả 5 kênh:

```
Tên persona: ...
Độ tuổi / giới / quốc gia chính (ước đoán, ghi căn cứ): ...
Vì sao họ xem (nhu cầu: giải trí / học / tò mò / ra quyết định): ...
Họ đã biết gì / chưa biết gì: ...
Điều làm họ bấm vào (CTR triggers): ...
Điều làm họ thoát (drop-off triggers): ...
Thiết bị xem chủ yếu (TV / mobile / desktop) → hệ quả cho thumbnail & text: ...
```

## 4. Bảng tổng hợp

| Trục | Kênh 1 | Kênh 2 | Kênh 3 | Kênh 4 | Kênh 5 | Pattern chung (≥3/5) |
|---|---|---|---|---|---|---|
| Hook | | | | | | |
| Pacing | | | | | | |
| Narrative | | | | | | |
| Tone | | | | | | |
| Visual/Audio | | | | | | |
| CTA | | | | | | |
| **Tổng /30** | | | | | | |

## 5. Content Gap Analysis

Tìm gap theo 5 hướng, mỗi hướng ≥1 ý:
1. **Topic gap:** chủ đề trong ngách mà comment / tiêu đề đối thủ gợi ý khán giả muốn nhưng chưa ai làm sâu.
2. **Angle gap:** chủ đề đã có nhưng thiếu góc nhìn (dữ liệu mới, phản biện, cá nhân hoá, "behind the scenes").
3. **Format gap:** cùng chủ đề nhưng định dạng khác (investigation thay vì listicle, timeline trực quan, so sánh).
4. **Depth gap:** đối thủ làm hời hợt (<8 phút) hoặc quá dài lê thê.
5. **Freshness gap:** thông tin của đối thủ đã cũ (sự kiện, số liệu năm mới).

Mỗi gap ghi: mô tả, bằng chứng, mức cơ hội (Cao/TB/Thấp).

## 6. Công thức DNA (đầu ra cuối Bước 1)

Viết 1 đoạn 80–120 từ theo mẫu:

> "Our videos open with [hook type] within [X]s, promise [type of payoff], follow a [structure] in [N] chapters of ~[X] min, keep [N] cuts/min with a pattern interrupt every [X]s, speak in a [tone] voice at ~[X] wpm, look [visual style] with [palette], and place CTAs at [positions]. We differentiate by [gap/angle]."
