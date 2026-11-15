"""Phụ đề karaoke (ASS) từ word_timings – không tốn token."""
from __future__ import annotations

from pathlib import Path

from . import config


def layout(words: list[dict], lang: str, max_words: int = 4) -> dict:
    """Chia từ thành cụm phụ đề. Ngôn ngữ không có dấu cách (ja, zh, th) chia theo số ký tự."""
    nospace = bool(config.language(lang).get("nospace"))
    limit = 12 if nospace else max(14, max_words * 7)
    groups, start, length = [], 0, 0
    for i, w in enumerate(words):
        n = len(w["word"])
        too_many = (not nospace and i - start >= max_words) or (length + n > limit and i > start)
        if too_many:
            groups.append([start, i])
            start, length = i, 0
        length += n + (0 if nospace else 1)
        if not nospace and w["word"][-1:] in ".!?…" and i + 1 - start >= 2:
            groups.append([start, i + 1])
            start, length = i + 1, 0
    if start < len(words):
        groups.append([start, len(words)])
    return {"groups": groups, "joiner": "" if nospace else " "}


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_color(hex_: str) -> str:
    h = hex_.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def build_ass(scenes: list[dict], offsets: list[float], width: int, height: int, cap: dict, chunk: int = 4,
              lang: str = "vi") -> str:
    font = cap.get("font", "Arial")
    size = int(cap.get("size", 0.045) * height) if cap.get("size", 0.045) < 1 else int(cap["size"])
    color, hi, outline = cap.get("color", "#FFFFFF"), cap.get("highlight", "#FFD400"), cap.get("outline", "#000000")
    margin_v = int(cap.get("y", 0.22) * height)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{_ass_color(color)},{_ass_color(hi)},{_ass_color(outline)},&H80000000,-1,0,0,0,100,100,0,0,1,{max(2, size // 12)},0,2,{width // 12},{width // 12},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for sc, off in zip(scenes, offsets):
        words = sc.get("word_timings") or []
        if sc.get("captions") is False or sc.get("template_name") == "kinetic_text":
            continue  # cảnh tự hiển thị chữ theo giọng đọc
        if cap.get("upper"):
            words = [{**w, "word": w["word"].upper()} for w in words]
        lay = layout(words, lang, chunk)
        for a, b in lay["groups"]:
            grp = words[a:b]
            for j, w in enumerate(grp):
                start = off + w["start"]
                end = off + (grp[j + 1]["start"] if j + 1 < len(grp) else w["end"] + 0.15)
                txt = lay["joiner"].join(("{\\c" + _ass_color(hi) + "}" + g["word"] + "{\\c" + _ass_color(color) + "}") if k == j
                               else g["word"] for k, g in enumerate(grp))
                lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{txt}")
    return header + "\n".join(lines) + "\n"


def build_srt(scenes: list[dict], offsets: list[float], chunk: int = 7, lang: str = "vi") -> str:
    out, n = [], 1
    f = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}"
    for sc, off in zip(scenes, offsets):
        words = sc.get("word_timings") or []
        lay = layout(words, lang, chunk)
        for a, b in lay["groups"]:
            g = words[a:b]
            out.append(f"{n}\n{f(off + g[0]['start'])} --> {f(off + g[-1]['end'])}\n{lay['joiner'].join(w['word'] for w in g)}\n")
            n += 1
    return "\n".join(out)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8-sig" if path.suffix == ".ass" else "utf-8")
    return path
