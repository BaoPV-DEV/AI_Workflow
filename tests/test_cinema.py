import json

from engine import cinema


def test_slugify():
    assert cinema.slugify("Vì sao mèo thích chui vào hộp?") == "vi-sao-meo-thich-chui-vao-hop"
    assert cinema.slugify("Đà Lạt") == "da-lat"


def test_projects_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(cinema, "root", lambda: tmp_path)
    d = tmp_path / "thu"
    (d / "out").mkdir(parents=True)
    (d / "storyboard.json").write_text(json.dumps({"title": "Thử", "target_seconds": 20, "shots": [{"id": "S01", "vo": "Xin chào"}]}))
    for n in ("picture.mp4", "thu.mp4", "thu-preview.mp4"):
        (d / "out" / n).write_bytes(b"x")
    (d / "out" / "qa.json").write_text(json.dumps({"duration_s": 19.5, "missing_assets": []}))
    p = cinema.projects()[0]
    assert p["videos"] == ["thu.mp4", "thu-preview.mp4"] and p["qa"]["missing_assets"] == 0 and p["shots"] == 1
    txt = cinema._prompt(d, "Chủ đề", 60, "vi", "9:16", "", "")
    assert "1080x1920" in txt and "ai-video-production-pipeline" in txt and "cinema voice thu" in txt
