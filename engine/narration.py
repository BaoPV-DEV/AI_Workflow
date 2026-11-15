"""Tự viết lời dẫn → manifest, KHÔNG gọi AI (0 token).

Chia lời dẫn thành cảnh theo câu, rồi chọn kiểu cảnh bằng quy tắc:
- câu có con số / % / năm  → stat_card hoặc timeline
- câu liệt kê (a, b và c / thứ nhất…)  → bullet_list
- câu trích dẫn “…”  → quote_card
- câu hỏi mở đầu  → kinetic_text
- còn lại  → người que diễn (hành động đoán theo động từ), xen thẻ tiêu đề mỗi vài cảnh
Kết quả là bản nháp tốt để chỉnh tiếp trong Trình sửa cảnh.
"""
from __future__ import annotations

import re

from . import config

SENT = re.compile(r"(?<=[.!?…。！？])\s+|\n+")
NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|phần trăm|percent|triệu|tỷ|nghìn|million|billion|thousand)?", re.I)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
LIST_HINT = re.compile(r"thứ nhất|thứ hai|đầu tiên|firstly|first,|second,|gồm|bao gồm|including|:\s*\w+,", re.I)
QUOTE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")

ACT_RULES = [  # (mẫu, act, mood)
    (r"vì sao|tại sao|tự hỏi|nghĩ|liệu|why|wonder|think", "think", "curious"),
    (r"nhìn|đây là|chính là|hãy xem|look|this is", "point", "neutral"),
    (r"vui|tuyệt|thành công|chiến thắng|hạnh phúc|win|happy|success", "celebrate", "happy"),
    (r"buồn|thất bại|mất|khó khăn|tiếc|sad|fail|lost", "sad", "sad"),
    (r"sợ|nguy hiểm|cảnh báo|scared|danger|warning", "scared", "scared"),
    (r"chạy|nhanh|vội|run|rush", "run", "neutral"),
    (r"đọc|sách|học|read|book|study", "read", "curious"),
    (r"làm việc|máy tính|code|work|computer", "work", "neutral"),
    (r"tiền|giá|mua|bán|money|price|buy", "present", "neutral"),
    (r"không|chẳng|đừng|no|don't|never", "shake_head", "neutral"),
]
HOLD_RULES = [(r"tiền|giá|đồng|money|price", "money"), (r"sách|học|book", "book"), (r"điện thoại|phone", "phone"),
              (r"ý tưởng|idea|sáng tạo", "bulb"), (r"bản đồ|đường|map|travel", "map"), (r"cúp|giải|trophy|win", "trophy")]
BACKDROPS = ["room", "office", "street", "park", "cafe", "studio", "nature", "library"]
PLACE_RULES = [(r"phòng tắm|nhà vệ sinh|bồn tắm|bathroom|toilet", "bathroom"), (r"phòng gym|tập tạ|thể hình|gym|workout", "gym"),
               (r"siêu thị|supermarket|grocery", "supermarket"), (r"nhà hàng|bữa tối|restaurant|dinner", "restaurant"),
               (r"bảo tàng|museum", "museum"), (r"triển lãm|bức tranh|họa sĩ|gallery|painting", "gallery"), (r"rạp phim|xem phim|cinema|movie", "cinema"),
               (r"bản tin|thời sự|phóng viên|news|reporter", "newsroom"), (r"podcast|phỏng vấn|radio|interview", "podcast"),
               (r"máy chủ|dữ liệu|server|data center|hacker", "server_room"), (r"nhà máy|xưởng|sản xuất|factory", "factory"),
               (r"tòa án|luật sư|thẩm phán|court|lawyer|judge", "courtroom"), (r"ngân hàng|tiết kiệm|bank", "bank"), (r"gara|sửa xe|ô tô|garage", "garage"),
               (r"tàu vũ trụ|phi hành gia|spaceship|astronaut", "spaceship"), (r"mặt trăng|moon", "moon"), (r"sao hỏa|mars", "mars"),
               (r"sân bay|máy bay|chuyến bay|airport|flight|plane", "airport"), (r"tàu điện ngầm|metro|subway", "subway"), (r"nhà ga|tàu hỏa|\btrain\b", "train_station"),
               (r"sân chơi|xích đu|cầu trượt|playground", "playground"), (r"sân vận động|bóng đá|trận đấu|stadium|football|soccer", "stadium"),
               (r"công trường|xây dựng|construction|builder", "construction"), (r"làng quê|nông thôn|lũy tre|quê nhà|village", "village"),
               (r"chùa|pagoda", "pagoda"), (r"sân thượng|rooftop", "rooftop"), (r"con hẻm|ngõ|alley", "alley"), (r"hồ nước|câu cá|chèo thuyền|lake|fishing", "lake"),
               (r"dưới nước|đại dương sâu|cá mập|san hô|lặn|underwater|coral|shark", "underwater"), (r"hang động|cave", "cave"), (r"núi lửa|dung nham|volcano|lava", "volcano"),
               (r"bắc cực|nam cực|băng tuyết|chim cánh cụt|arctic|penguin|polar", "arctic"), (r"rừng rậm|rừng nhiệt đới|amazon|jungle", "jungle"), (r"thác|waterfall", "waterfall"),
               (r"cắm trại|lửa trại|camp", "campsite"), (r"hòn đảo|island", "island"), (r"khủng long|tiền sử|dinosaur|prehistoric", "prehistoric"),
               (r"bầu trời|bay lên|trên mây|sky|fly", "sky"),
               (r"bếp|nấu|món ăn|kitchen|cook", "kitchen"), (r"trường|lớp học|giáo viên|học sinh|school|class", "classroom"),
               (r"thư viện|sách|library", "library"), (r"bệnh viện|bác sĩ|thuốc|hospital|doctor", "hospital"),
               (r"cà phê|quán|cafe|coffee", "cafe"), (r"chợ|cửa hàng|mua sắm|market|shop", "shop"),
               (r"đường phố|thành phố|xe cộ|street|city", "street"), (r"công viên|park", "park"), (r"rừng|forest", "forest"),
               (r"biển|bãi biển|sóng|beach|sea|ocean", "beach"), (r"núi|leo núi|mountain", "mountain"), (r"sa mạc|desert", "desert"),
               (r"nông trại|ruộng|trang trại|farm", "farm"), (r"sông|cầu|river|bridge", "river"),
               (r"vũ trụ|hành tinh|ngôi sao|tên lửa|space|planet|rocket", "space"), (r"ngủ|giường|phòng ngủ|sleep|bed", "bedroom"),
               (r"văn phòng|công ty|sếp|họp|office|meeting", "office"), (r"thí nghiệm|nhà khoa học|lab|scientist", "lab"),
               (r"lâu đài|nhà vua|hoàng|castle|king", "castle"), (r"đền|cổ đại|la mã|hy lạp|temple|ancient", "temple"),
               (r"xe buýt|chuyến đi|bus|trip", "bus"), (r"sân khấu|biểu diễn|stage|show", "stage")]
WEATHER_RULES = [(r"mưa|rain", "rain"), (r"tuyết|snow|mùa đông|winter", "snow"), (r"mùa thu|lá rơi|autumn|fall leaves", "leaves"), (r"sương mù|fog", "fog")]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT.split(text.strip()) if s.strip()]


def group(sents: list[str], max_words: int = 24) -> list[str]:
    out, cur = [], ""
    for s in sents:
        if cur and len((cur + " " + s).split()) > max_words:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def short(text: str, n: int = 6) -> str:
    w = re.sub(r"[“”\"]", "", text).split()
    return " ".join(w[:n]).rstrip(",.;:!?") + ("…" if len(w) > n else "")


def first_word(text: str, pattern: str) -> str | int:
    """Từ trong lời đọc khớp mẫu → dùng làm mốc 'at'."""
    for w in text.split():
        if re.search(pattern, w, re.I):
            return re.sub(r"[^\w%]", "", w) or "50%"
    return "40%"


def scene_for(text: str, i: int, n: int, cast: list[str], state: dict) -> dict:
    sid = i + 1
    base = {"scene_id": sid, "voice_text": text}
    words = text.split()
    q = QUOTE.search(text)
    years = YEAR.findall(text)
    if i == 0 and (text.rstrip().endswith("?") or len(words) <= 14):
        return {**base, "visual_type": "html_animation", "template_name": "kinetic_text",
                "props": {"emphasize": [re.sub(r"[^\w]", "", w) for w in words[::-1] if len(w) > 4][:2]}}
    if q:
        return {**base, "visual_type": "html_animation", "template_name": "quote_card", "props": {"quote": q.group(1)[:140]}}
    if len(set(years)) >= 2:
        evs = []
        for y in dict.fromkeys(years):
            after = text.split(y, 1)[1]
            evs.append({"year": y, "label": short(after.strip(" ,.:;-–"), 4) or y})
        return {**base, "visual_type": "html_animation", "template_name": "timeline", "props": {"title": "", "events": evs[:5]}}
    m = NUM.search(text)
    if m and not years and re.search(r"\d", m.group(1)):
        val = float(m.group(1).replace(",", "."))
        unit = (m.group(2) or "").lower()
        suffix = "%" if unit in ("%", "phần trăm", "percent") else (f" {unit}" if unit else "")
        after = re.split(r"[.!?…]", text[m.end():], maxsplit=1)[0].strip(" ,.:;")
        label = short(after or text[:m.start()], 5)
        return {**base, "visual_type": "html_animation", "template_name": "stat_card",
                "props": {"value": int(val) if val.is_integer() else val, "suffix": suffix, "label": label,
                          "at": re.sub(r"[^\w%]", "", m.group(1)) or "30%"}}
    parts = [p.strip(" .") for p in re.split(r",|;| và | and ", text) if p.strip(" .")]
    if (LIST_HINT.search(text) or len(parts) >= 3) and len(parts) >= 3 and all(len(p.split()) <= 9 for p in parts[1:]):
        head = parts[0].split(":")[0] if ":" in parts[0] else short(parts[0], 5)
        src = ([parts[0].split(":", 1)[1]] + parts[1:]) if ":" in parts[0] else parts
        items = [short(p, 6) for p in src if p.strip()][:5]
        return {**base, "visual_type": "html_animation", "template_name": "bullet_list", "props": {"title": head, "items": items}}
    if state["since_title"] >= 4 and i < n - 1:
        state["since_title"] = 0
        return {**base, "visual_type": "html_animation", "template_name": "title_card_neon",
                "props": {"heading": short(text, 5)}}
    # người que
    state["since_title"] += 1
    act, mood = "talk", "neutral"
    for pat, a, md in ACT_RULES:
        if re.search(pat, text, re.I):
            act, mood = a, md
            break
    hold = next((h for pat, h in HOLD_RULES if re.search(pat, text, re.I)), None)
    who = cast[i % len(cast)]
    beats = []
    if state.get("first_stick", True):
        beats.append({"who": who, "at": 0, "act": "walk", "move": "enter_left", "mood": "neutral"})
        state["first_stick"] = False
    beat = {"who": who, "at": first_word(text, "|".join(p for p, a, _ in ACT_RULES if a == act)) if act != "talk" else 0,
            "act": act, "mood": mood}
    if hold:
        beat["hold"] = hold
    beats.append(beat)
    if len(cast) > 1:
        other = cast[(i + 1) % len(cast)]
        beats.append({"who": other, "at": "60%", "act": "nod" if mood in ("neutral", "happy", "curious") else "shrug", "mood": mood})
    place = next((b for pat, b in PLACE_RULES if re.search(pat, text, re.I)), None)
    if place:
        state["backdrop"] = place
    elif i % 3 == 0 or "backdrop" not in state:
        state["backdrop"] = BACKDROPS[state.setdefault("rot", 0) % len(BACKDROPS)]
        state["rot"] += 1
    props = {"backdrop": state["backdrop"]}
    if re.search(r"ban đêm|buổi tối|đêm khuya|night|evening", text, re.I):
        props["time"] = "night"
    elif re.search(r"hoàng hôn|chiều tà|sunset", text, re.I):
        props["time"] = "sunset"
    wx = next((w for pat, w in WEATHER_RULES if re.search(pat, text, re.I)), None)
    if wx:
        props["weather"] = wx
    return {**base, "visual_type": "html_animation", "template_name": "stickman_stage", "props": props, "acting": beats}


def build(text: str, title: str = "", lang: str = "vi", aspect: str = "9:16", style: str | None = None,
          cast: dict | None = None, max_words: int = 24) -> dict:
    chunks = group(sentences(text), max_words)
    if not chunks:
        raise ValueError("Lời dẫn trống")
    cast = cast or {"Bo": {"preset": "classic"}, "Mi": {"preset": "kid"}}
    state = {"since_title": 0, "first_stick": True}
    scenes = [scene_for(c, i, len(chunks), list(cast), state) for i, c in enumerate(chunks)]
    return {"project_id": "", "title": title or short(chunks[0], 8), "aspect_ratio": aspect, "lang": lang,
            "style": style or config.settings().get("default_style", "classic_light"), "cast": cast, "scenes": scenes,
            "source": "narration"}
