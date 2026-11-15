"""Mini agent: một phần vòng lặp agent của Claude (gọi công cụ, cache prompt, định tuyến model, ngân sách token).

- llm.py      : gọi Claude API + prompt caching + ghi nhận token/chi phí
- loop.py     : vòng lặp tool-use tổng quát (model gọi công cụ -> chạy local -> trả kết quả -> lặp)
- tools.py    : công cụ thao tác manifest (xem/sửa/thêm/xoá cảnh, kiểm tra, catalog)
- director.py : chủ đề -> manifest (1 lần gọi, ép trả JSON qua công cụ), sửa bằng lời, dịch
"""
