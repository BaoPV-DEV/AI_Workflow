"""Chủ đề đang thịnh hành – nguồn miễn phí, không cần key:

- Google Trends (RSS tìm kiếm thịnh hành theo quốc gia)
- Wikipedia (bài được xem nhiều nhất hôm qua theo ngôn ngữ)
- Hacker News (công nghệ, tiếng Anh)
- YouTube Most Popular (tuỳ chọn, cần trends.youtube_api_key trong settings)

Kết quả được cache 1 giờ. Sau đó AI (ideas()) lọc và biến thành ý tưởng video.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from . import config

UA = {"User-Agent": "AI-Workflow/0.2 (video idea research; https://github.com/BaoPV-DEV/AI_Workflow)"}
CACHE_SECONDS = 3600
SKIP_WIKI = re.compile(r"^(Main_Page|Trang_Chính|Special:|Đặc_biệt:|Wikipedia:|File:|Tập_tin:|Portal:|Cổng_thông_tin:|"
                       r"Help:|Trợ_giúp:|Spécial:|Spezial:|Especial:|Служебная:|特別:|Speciale:|-$|Undefined)", re.I)


def _get(url: str, timeout: int = 15) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _num(traffic: str) -> int:
    m = re.match(r"([\d.,]+)\s*([KkMm]?)", traffic or "")
    if not m:
        return 0
    n = float(m.group(1).replace(",", ""))
    return int(n * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1))


def google_trends(geo: str = "VN") -> list[dict]:
    root = None
    for url in (f"https://trends.google.com/trending/rss?geo={geo}",
                f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"):
        try:
            root = ET.fromstring(_get(url))
            break
        except Exception:
            continue
    if root is None:
        raise RuntimeError("Không tải được Google Trends")
    return parse_google_rss(root)


def parse_google_rss(root) -> list[dict]:
    out = []
    for it in root.iter("item"):
        traffic = (it.findtext("{*}approx_traffic") or "").strip()
        news = [{"title": (n.findtext("{*}news_item_title") or "").strip(),
                 "source": (n.findtext("{*}news_item_source") or "").strip(),
                 "url": (n.findtext("{*}news_item_url") or "").strip()} for n in it.findall("{*}news_item")]
        out.append({"title": (it.findtext("title") or "").strip(), "source": "google_trends", "traffic": traffic,
                    "score": _num(traffic), "context": [n["title"] for n in news if n["title"]][:3],
                    "url": next((n["url"] for n in news if n["url"]), "")})
    return out


def wikipedia_top(lang: str = "vi", limit: int = 30) -> list[dict]:
    project = f"{lang.split('-')[0]}.wikipedia"
    for back in (1, 2):
        d = dt.datetime.utcnow().date() - dt.timedelta(days=back)
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{project}/all-access/{d:%Y/%m/%d}"
        try:
            arts = json.loads(_get(url))["items"][0]["articles"]
            break
        except Exception:
            arts = None
    if not arts:
        raise RuntimeError("Không tải được Wikipedia top")
    out = []
    for a in arts:
        t = a["article"]
        if SKIP_WIKI.match(t):
            continue
        out.append({"title": t.replace("_", " "), "source": "wikipedia", "traffic": f"{a['views']:,} lượt xem",
                    "score": a["views"], "context": [],
                    "url": f"https://{project}.org/wiki/{urllib.parse.quote(t)}"})
        if len(out) >= limit:
            break
    return out


def hacker_news(limit: int = 15) -> list[dict]:
    data = json.loads(_get("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"))
    hits = sorted(data.get("hits", []), key=lambda h: -(h.get("points") or 0))[:limit]
    return [{"title": h.get("title", ""), "source": "hacker_news", "traffic": f"{h.get('points', 0)} điểm",
             "score": h.get("points") or 0, "context": [],
             "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"} for h in hits]


def youtube_popular(geo: str = "VN", key: str = "", limit: int = 20) -> list[dict]:
    if not key:
        return []
    q = urllib.parse.urlencode({"part": "snippet,statistics", "chart": "mostPopular", "regionCode": geo,
                                "maxResults": limit, "key": key})
    items = json.loads(_get(f"https://www.googleapis.com/youtube/v3/videos?{q}")).get("items", [])
    return [{"title": i["snippet"]["title"], "source": "youtube", "traffic": f"{int(i['statistics'].get('viewCount', 0)):,} views",
             "score": int(i["statistics"].get("viewCount", 0)), "context": i["snippet"].get("tags", [])[:5],
             "url": f"https://youtu.be/{i['id']}"} for i in items]


def collect(geo: str = "VN", lang: str = "vi", sources: list[str] | None = None, fresh: bool = False) -> dict:
    """Gom từ mọi nguồn. Nguồn lỗi được ghi vào 'errors', không làm hỏng cả lượt."""
    sources = sources or ["google", "wikipedia", "hackernews", "youtube"]
    cache_file = config.workspace() / ".trends_cache.json"
    key = f"{geo}|{lang}|{','.join(sources)}"
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    if not fresh and key in cache and time.time() - cache[key]["ts"] < CACHE_SECONDS:
        return cache[key]
    yt_key = config.settings().get("trends", {}).get("youtube_api_key", "")
    jobs = {"google": lambda: google_trends(geo), "wikipedia": lambda: wikipedia_top(lang),
            "hackernews": hacker_news, "youtube": lambda: youtube_popular(geo, yt_key)}
    items, errors = [], {}
    for s in sources:
        try:
            items += jobs[s]()
        except Exception as e:
            errors[s] = f"{type(e).__name__}: {e}"
    res = {"ts": time.time(), "geo": geo, "lang": lang, "items": items, "errors": errors,
           "fetched": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
    if items:
        cache[key] = res
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return res


def compact(items: list[dict], limit: int = 40) -> str:
    """Danh sách gọn để gửi AI (~1 dòng/chủ đề) – tiết kiệm token."""
    rows = []
    for i, t in enumerate(items[:limit], 1):
        ctx = " | ".join(t.get("context") or [])[:160]
        rows.append(f"{i}. [{t['source']}] {t['title']} ({t.get('traffic', '')}){' — ' + ctx if ctx else ''}")
    return "\n".join(rows)


IDEA_SCHEMA = {
    "type": "object", "required": ["ideas"],
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object", "required": ["topic", "hook", "genre", "score"],
        "properties": {
            "topic": {"type": "string", "description": "chủ đề video cụ thể, dùng làm đầu vào cho vf new"},
            "title": {"type": "string", "description": "tiêu đề video gợi tò mò"},
            "hook": {"type": "string", "description": "câu mở đầu ≤12 từ"},
            "angle": {"type": "string", "description": "góc khai thác: vì sao/thế nào/so sánh/sự thật thú vị"},
            "genre": {"enum": ["animation", "motion_graphic", "news", "explainer"]},
            "style": {"type": "string"},
            "trend": {"type": "string", "description": "xu hướng gốc"},
            "why_now": {"type": "string"},
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "risk": {"enum": ["low", "medium", "high"]},
            "facts_to_check": {"type": "array", "items": {"type": "string"}}}}}}}


def ideas_prompt(trend_text: str, count: int, lang: str, genre: str | None, niche: str = "") -> tuple[str, str]:
    system = (config.CONFIG / "prompts" / "ideas.md").read_text(encoding="utf-8")
    styles = ", ".join(config.list_styles())
    user = (f"Danh sách xu hướng (lấy lúc {dt.datetime.now():%Y-%m-%d %H:%M}):\n{trend_text}\n\n"
            f"Hãy đề xuất {count} ý tưởng video, sắp theo score giảm dần.\n"
            f"- Ngôn ngữ video: {lang}\n- Thể loại ưu tiên: {genre or 'tự chọn'}\n- Style hợp lệ: {styles}\n"
            + (f"- Kênh chuyên về: {niche}\n" if niche else ""))
    return system, user
