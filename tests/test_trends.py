from engine import trends

RAW = [
    {"title": "latvia vs", "source": "google_trends", "traffic": "100+", "score": 100,
     "context": ["%*((ROJADIRECTA>)))* Latvia VS Armenia in diretta streaming gratis"]},
    {"title": "latvia đấu với armenia", "source": "google_trends", "traffic": "200+", "score": 200, "context": ["Nhận định Latvia vs Armenia"]},
    {"title": "lũ quét", "source": "google_trends", "traffic": "2000+", "score": 2000, "context": ["Cảnh báo lũ quét"]},
    {"title": "Phim khiêu dâm", "source": "wikipedia", "traffic": "1 lượt", "score": 1, "context": []},
    {"title": "Xôi Lạc TV", "source": "wikipedia", "traffic": "1 lượt", "score": 1, "context": []},
    {"title": "Tô Lâm", "source": "wikipedia", "traffic": "1 lượt", "score": 1, "context": []},
    {"title": "kinh doanh đa cấp", "source": "google_trends", "traffic": "200+", "score": 200, "context": ["Bị bắt vì đa cấp"]},
]


def test_clean_filters_and_classifies():
    out, dropped = trends.clean(RAW, "vi")
    titles = [o["title"] for o in out]
    assert dropped == 3  # link lậu, nội dung người lớn, trang xem bóng đá lậu
    assert "Latvia đấu với armenia" in titles and not any("ROJADIRECTA" in c for o in out for c in o["context"])
    by = {o["title"]: o for o in out}
    assert by["Lũ quét"]["category"] == "weather" and not by["Lũ quét"]["sensitive"]
    assert by["Tô Lâm"]["sensitive"] and by["Kinh doanh đa cấp"]["sensitive"]
    assert by["Lũ quét"]["heat"] == 100
