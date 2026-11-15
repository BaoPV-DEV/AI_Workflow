"""Mốc thời gian từng từ: faster-whisper trên CPU, hoặc ước lượng khi không có."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


def words_of(text: str, lang: str | None = None) -> list[str]:
    ws = [w for w in re.split(r"\s+", text.strip()) if w]
    if lang and len(ws) <= 2 and len(text) > 8:
        from . import config
        if config.language(lang).get("nospace"):  # ja/zh/th: cắt theo dấu câu, tối đa ~6 ký tự
            return re.findall(r"[^\s、。，！？,.!?]{1,6}[、。，！？,.!?]?", text)
    return ws


def estimate(text: str, duration: float, lead: float = 0.05, lang: str | None = None) -> list[dict]:
    """Chia thời lượng theo số ký tự mỗi từ (+ nghỉ ở dấu câu). Đủ tốt cho phụ đề cụm."""
    ws = words_of(text, lang)
    if not ws:
        return []
    weights = [len(w) + (3 if re.search(r"[.,!?;:…]$", w) else 0) + 1 for w in ws]
    span = max(0.1, duration - lead * 2)
    t, out = lead, []
    for w, wt in zip(ws, weights):
        d = span * wt / sum(weights)
        out.append({"word": w, "start": round(t, 3), "end": round(t + d * 0.92, 3)})
        t += d
    return out


@lru_cache
def _model(name: str):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8")


def whisper(audio: Path, text: str, lang: str, model: str = "base") -> list[dict] | None:
    try:
        m = _model(model)
    except ImportError:
        return None
    segs, _ = m.transcribe(str(audio), language=lang[:2], word_timestamps=True, vad_filter=True)
    got = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
           for s in segs for w in (s.words or []) if w.word.strip()]
    script = words_of(text)
    if got and len(got) == len(script):  # giữ đúng chính tả của kịch bản, lấy thời gian của whisper
        for g, w in zip(got, script):
            g["word"] = w
    return got or None


def align(audio: Path, text: str, duration: float, lang: str, engine: str = "auto",
          model: str = "base", tts_words: list | None = None) -> tuple[list[dict], str]:
    if engine in ("auto",) and tts_words:
        return tts_words, "tts"
    if engine in ("auto", "whisper"):
        w = whisper(audio, text, lang, model)
        if w:
            return w, "whisper"
    return estimate(text, duration, lang=lang), "estimate"


def resolve_at(at, timings: list[dict], duration: float, default: float = 0.0) -> float:
    """'60%' | 2.5 | 'từ trong lời đọc' -> giây."""
    if at is None:
        return default
    if isinstance(at, (int, float)):
        return float(at)
    s = str(at).strip()
    if s.endswith("%"):
        try:
            return duration * float(s[:-1]) / 100
        except ValueError:
            return default
    try:
        return float(s)
    except ValueError:
        pass
    norm = lambda x: re.sub(r"[^\w]", "", x.lower())
    target = [norm(x) for x in words_of(s)]
    seq = [norm(w["word"]) for w in timings]
    for i in range(len(seq) - len(target) + 1):
        if seq[i:i + len(target)] == target:
            return timings[i]["start"]
    for i, w in enumerate(seq):  # khớp lỏng: từ đầu tiên
        if target and w.startswith(target[0]):
            return timings[i]["start"]
    return default
