from pathlib import Path

import pytest

from engine import align, captions, config, tts


def test_language_lookup():
    assert config.language("ja-JP")["code"] == "ja"
    assert config.default_voice("vi").startswith("vi-VN")
    assert config.default_voice("en-GB").startswith("en-GB")


def test_cjk_caption_groups():
    w = align.estimate("東京は日本の首都です。人口は約千四百万人です。", 4, lang="ja")
    lay = captions.layout(w, "ja")
    assert lay["joiner"] == "" and len(lay["groups"]) >= 2


def test_latin_groups_break_on_sentence():
    w = align.estimate("Một hai ba. Bốn năm sáu bảy tám", 4, lang="vi")
    assert captions.layout(w, "vi", 4)["groups"][0] == [0, 3]


def test_tts_reports_failure_instead_of_silence(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "_edge", lambda *a: (_ for _ in ()).throw(RuntimeError("mạng")))
    monkeypatch.setattr(tts, "_gtts", lambda *a: (_ for _ in ()).throw(RuntimeError("mạng")))
    with pytest.raises(tts.TTSError):
        tts.synth("xin chào", tmp_path / "a.wav", "auto", "vi-VN-HoaiMyNeural", lang="vi")
