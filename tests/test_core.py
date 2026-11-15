"""Kiểm tra nhanh phần lõi không cần trình duyệt/mạng: python -m pytest tests"""
import json
from pathlib import Path

from engine import align, captions, manifest

DEMO = Path(__file__).parent.parent / "examples" / "demo_pipeline" / "project_manifest.json"


def test_demo_manifest_valid():
    assert manifest.validate(json.loads(DEMO.read_text(encoding="utf-8"))) == []


def test_bad_names_reported():
    data = json.loads(DEMO.read_text(encoding="utf-8"))
    data["scenes"][1]["acting"][0]["act"] = "moonwalk"
    data["scenes"][0]["template_name"] = "nope"
    errs = manifest.validate(data)
    assert any("moonwalk" in e for e in errs) and any("nope" in e for e in errs)


def test_resolve_at():
    w = align.estimate("Mi có một chiếc laptop cũ", 3.0)
    assert align.resolve_at("laptop", w, 3.0) == w[4]["start"]
    assert align.resolve_at("50%", w, 3.0) == 1.5
    assert align.resolve_at(1.2, w, 3.0) == 1.2


def test_parse_fenced_json():
    assert manifest.parse('xin chào\n```json\n{"project_id": "a", "scenes": []}\n```')["project_id"] == "a"


def test_captions_skip_kinetic():
    sc = [{"template_name": "kinetic_text", "word_timings": [{"word": "a", "start": 0, "end": 1}]},
          {"word_timings": [{"word": "b", "start": 0, "end": 1}]}]
    ass = captions.build_ass(sc, [0, 1], 1080, 1920, {})
    assert ass.count("Dialogue:") == 1
