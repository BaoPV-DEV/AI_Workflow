"""Dữ liệu cho các trang Studio: trang chủ, thư viện/series, kế hoạch, phụ đề nhiều ngôn ngữ, gói đăng, công cụ, GPU, cài đặt."""
from __future__ import annotations

import json
import shutil
import time
import urllib.request
from functools import lru_cache
from pathlib import Path

import yaml

from . import config, manifest
from .util import ffmpeg, run


def _ws() -> Path:
    d = config.workspace()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _projects():
    for m in _ws().glob("*/" + manifest.MANIFEST):
        try:
            yield m.parent, json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            continue


# ---------------------------------------------------------------- series
def series_list() -> list[str]:
    f = _ws() / "_series.json"
    names = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    for _, d in _projects():
        if d.get("series") and d["series"] not in names:
            names.append(d["series"])
    return names


def series_add(name: str) -> list[str]:
    names = series_list()
    if name and name not in names:
        names.append(name)
    (_ws() / "_series.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return names


def series_delete(name: str) -> list[str]:
    for d, data in _projects():
        if data.get("series") == name:
            data.pop("series", None)
            manifest.save(d, data)
    names = [n for n in series_list() if n != name]
    (_ws() / "_series.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return names


# ---------------------------------------------------------------- thư viện
def episode(d: Path, data: dict) -> dict:
    scenes = data.get("scenes", [])
    out = d / "out"
    vids = sorted(out.glob("*.mp4"), key=lambda p: "_draft" in p.name) if out.exists() else []
    thumb = d / "preview" / "s001.jpg"
    if not thumb.exists():
        thumb = next(iter(sorted((d / "preview").glob("s*.jpg"))), None) if (d / "preview").exists() else None
    if not thumb and (d / "build" / "thumb.jpg").exists():
        thumb = d / "build" / "thumb.jpg"
    subs = sorted({p.suffixes[-2].lstrip(".") for p in out.glob("*.*.srt")}) if out.exists() else []
    return {"id": d.name, "title": data.get("title") or d.name.replace("_", " ").capitalize(), "series": data.get("series", ""),
            "scenes": len(scenes), "lang": data.get("lang", "vi"), "aspect": data.get("aspect_ratio", "9:16"),
            "duration": round(sum(s.get("duration", 0) for s in scenes), 1), "style": data.get("style", ""),
            "voiced": all(s.get("duration") for s in scenes) and bool(scenes),
            "rendered": any("_draft" not in v.name for v in vids), "draft": any("_draft" in v.name for v in vids),
            "videos": [v.name for v in vids], "subs": [data.get("lang", "vi")] + subs,
            "ai": data.get("source") != "narration", "source": data.get("source", "ai"),
            "thumb": f"/files/{d.name}/{thumb.relative_to(d).as_posix()}?{int(thumb.stat().st_mtime)}" if thumb else "",
            "mtime": int((d / manifest.MANIFEST).stat().st_mtime)}


def library() -> dict:
    eps = sorted((episode(d, data) for d, data in _projects()), key=lambda e: e["mtime"])
    groups = {}
    for name in series_list():
        groups[name] = []
    for e in eps:
        groups.setdefault(e["series"] or "", []).append(e)
    out = [{"name": k, "episodes": v} for k, v in groups.items() if k]
    if groups.get(""):
        out.append({"name": "", "episodes": groups[""]})
    return {"series": out}


def delete_project(pid: str) -> None:
    d = manifest.project_dir(pid)
    trash = _ws() / "_trash"
    trash.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash / f"{d.name}_{int(time.time())}"))


def thumbnail(pid: str) -> Path | None:
    """Ảnh đại diện từ video đã xuất (khi chưa có ảnh xem trước)."""
    d = manifest.project_dir(pid)
    t = d / "build" / "thumb.jpg"
    vids = sorted((d / "out").glob("*.mp4")) if (d / "out").exists() else []
    if not t.exists() and vids:
        t.parent.mkdir(exist_ok=True)
        run([ffmpeg(), "-y", "-v", "error", "-ss", "1.5", "-i", vids[0], "-frames:v", "1", "-vf", "scale=480:-2", t])
    return t if t.exists() else None


# ---------------------------------------------------------------- trang chủ
_checks_cache: dict = {}


def checks(fresh: bool = False) -> list[dict]:
    if _checks_cache.get("v") and not fresh and time.time() - _checks_cache["t"] < 300:
        return _checks_cache["v"]
    out = []

    def add(name, ok, hint=""):
        out.append({"name": name, "ok": bool(ok), "hint": hint})

    try:
        from .util import pick_encoder
        exe = ffmpeg()
        add("FFmpeg (ghép video, phụ đề)", True, f"encoder {pick_encoder(config.settings()['render'].get('encoder', 'auto'))}")
    except Exception as e:
        add("FFmpeg (ghép video, phụ đề)", False, str(e)[:80])
    for mod, name, hint in [("edge_tts", "Edge TTS (giọng đọc)", "pip install edge-tts"),
                            ("gtts", "gTTS (giọng dự phòng)", "pip install gTTS"),
                            ("playwright", "Playwright (quay cảnh)", "pip install playwright"),
                            ("faster_whisper", "faster-whisper (mốc từ cho giọng thu sẵn)", "tuỳ chọn")]:
        try:
            __import__(mod)
            add(name, True)
        except ImportError:
            add(name, False, hint)
    from .agent.llm import backend, claude_cli
    be = backend()
    add({"cli": "Claude Code (gói Claude của bạn)", "api": "Claude API key", "manual": "AI tự gọi"}[be], be != "manual",
        "" if be != "manual" else "Cài đặt → Kết nối AI")
    url = config.settings().get("visual", {}).get("comfyui_url", "")
    add("ComfyUI / GPU (ảnh AI)", gpu_ping(url)["ok"], "tuỳ chọn · Kết nối GPU")
    _checks_cache.update(v=out, t=time.time())
    return out


def home() -> dict:
    lib = library()
    eps = [e for s in lib["series"] for e in s["episodes"]]
    return {"stats": {"series": len([s for s in lib["series"] if s["name"]]), "episodes": len(eps),
                      "rendered": sum(1 for e in eps if e["rendered"])},
            "recent": sorted(eps, key=lambda e: -e["mtime"])[:6],
            "presets": config.library("presets")["presets"], "checks": checks()}


# ---------------------------------------------------------------- kế hoạch (chủ đề đã lưu)
def plan_get() -> list[dict]:
    f = _ws() / "_plan.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def plan_set(items: list[dict]) -> list[dict]:
    (_ws() / "_plan.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def research_saved() -> list[dict]:
    from .trends import research_dir
    out = []
    for f in sorted(research_dir().glob("*.json"), reverse=True)[:30]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            q = d.get("query", {})
            out.append({"file": f.name, "label": f"{d.get('created', '')} · {', '.join(q.get('markets', []))} · "
                                                 f"{q.get('window', '')} · {len(d.get('topics', []))} chủ đề"})
        except Exception:
            continue
    return out


def research_load(name: str) -> dict:
    from .trends import research_dir
    f = research_dir() / Path(name).name
    d = json.loads(f.read_text(encoding="utf-8"))
    d["file"] = f.name
    return d


# ---------------------------------------------------------------- phụ đề nhiều ngôn ngữ (chỉ dịch chữ)
def extra_subtitles(pid: str, langs: list[str]) -> list[str]:
    """Dịch lời đọc từng cảnh rồi xuất <id>.<lang>.srt theo thời lượng cảnh. Cần AI (1 lần gọi / ngôn ngữ, model nhỏ)."""
    from .agent.llm import complete_json
    from .captions import build_srt

    d, data = manifest.load(pid)
    scenes = data["scenes"]
    if not all(s.get("duration") for s in scenes):
        raise RuntimeError("Chưa có giọng đọc: chạy bước Giọng đọc trước")
    cache = data.setdefault("subtitles", {})
    made = []
    for lang in langs:
        if lang == data.get("lang"):
            continue
        if not cache.get(lang) or len(cache[lang]) != len(scenes):
            schema = {"type": "object", "required": ["lines"], "properties": {"lines": {"type": "array", "items": {"type": "string"}}}}
            info = config.language(lang)
            res = complete_json("subtitles", ["Dịch phụ đề video. Giữ đúng số dòng và thứ tự, mỗi dòng là một cảnh. Ngắn gọn, tự nhiên."],
                                f"Ngôn ngữ đích: {info['name']} ({lang})\n" + json.dumps([s.get("voice_text", "") for s in scenes], ensure_ascii=False),
                                schema, "submit")
            cache[lang] = res["lines"][:len(scenes)] + [""] * max(0, len(scenes) - len(res["lines"]))
            manifest.save(d, data)
        fake, offsets, t = [], [], 0.0
        from .align import estimate
        for s, line in zip(scenes, cache[lang]):
            fake.append({"word_timings": estimate(line, s["duration"] - 0.2, lang=lang)})
            offsets.append(t)
            t += s["duration"]
        (d / "out").mkdir(exist_ok=True)
        f = d / "out" / f"{d.name}.{lang}.srt"
        f.write_text(build_srt(fake, offsets, lang=lang), encoding="utf-8")
        made.append(f.name)
    return made


# ---------------------------------------------------------------- gói đăng (tiêu đề, mô tả, tag)
PUBLISH_SCHEMA = {"type": "object", "required": ["title", "description"], "properties": {
    "title": {"type": "string"}, "alt_titles": {"type": "array", "items": {"type": "string"}},
    "description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
    "hashtags": {"type": "array", "items": {"type": "string"}}, "chapters": {"type": "array", "items": {"type": "string"}},
    "thumbnail_text": {"type": "string"}, "pinned_comment": {"type": "string"}}}


def publish_pack(pid: str, platform: str = "YouTube") -> dict:
    from .agent.llm import complete_json

    d, data = manifest.load(pid)
    t, chapters = 0.0, []
    for s in data["scenes"]:
        if s.get("template_name") == "title_card_neon":
            chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {(s.get('props') or {}).get('heading', '').replace('*', '')}")
        t += s.get("duration", 0)
    script = "\n".join(s.get("voice_text", "") for s in data["scenes"])
    res = complete_json("publish", [
        "Viết gói đăng video tối ưu tìm kiếm nhưng trung thực (không giật tít sai sự thật). Ngôn ngữ = ngôn ngữ kịch bản. "
        "title ≤ 70 ký tự, 3 alt_titles, description 2 đoạn + câu hỏi gợi bình luận, 15 tags, 3-5 hashtags, "
        "thumbnail_text ≤ 4 từ, pinned_comment."],
        f"Nền tảng: {platform}\nTiêu đề tạm: {data.get('title', '')}\nChương có sẵn: {chapters}\n\nKỊCH BẢN:\n{script[:6000]}",
        PUBLISH_SCHEMA, "submit")
    if chapters and not res.get("chapters"):
        res["chapters"] = chapters
    out = d / "out"
    out.mkdir(exist_ok=True)
    (out / f"publish_{platform.replace(' ', '_').lower()}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


# ---------------------------------------------------------------- công cụ nhanh (video có sẵn)
def tools_dir() -> Path:
    d = _ws() / "_tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tool_run(kind: str, src: str, opt: dict) -> str:
    from .util import encode_args, pick_encoder
    s = tools_dir() / Path(src).name
    if not s.exists():
        raise FileNotFoundError(src)
    enc = encode_args(pick_encoder(config.settings()["render"].get("encoder", "auto")))
    stem = s.stem
    if kind == "reframe":
        ar = opt.get("aspect", "9:16")
        w, h = config.ASPECTS.get(ar, (1080, 1920))
        out = tools_dir() / f"{stem}_{ar.replace(':', 'x')}.mp4"
        vf = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,eq=brightness=-0.08[bg];"
              f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p")
        run([ffmpeg(), "-y", "-v", "error", "-i", s, "-filter_complex", vf, *enc, "-c:a", "aac", out])
    elif kind == "thumbnail":
        out = tools_dir() / f"{stem}_thumb.jpg"
        run([ffmpeg(), "-y", "-v", "error", "-ss", str(opt.get("at", 2)), "-i", s, "-frames:v", "1", "-q:v", "2", out])
    elif kind == "audio":
        out = tools_dir() / f"{stem}.mp3"
        run([ffmpeg(), "-y", "-v", "error", "-i", s, "-vn", "-b:a", "192k", out])
    elif kind == "compress":
        out = tools_dir() / f"{stem}_small.mp4"
        run([ffmpeg(), "-y", "-v", "error", "-i", s, "-vf", "scale='min(1080,iw)':-2", *encode_args(pick_encoder("auto"), 28), "-c:a", "aac", "-b:a", "128k", out])
    elif kind == "translate_srt":
        from .agent.llm import complete_json
        lang = opt.get("lang", "en")
        blocks = s.read_text(encoding="utf-8-sig").strip().split("\n\n")
        lines = ["\n".join(b.splitlines()[2:]) for b in blocks]
        res = complete_json("subtitles", ["Dịch từng dòng phụ đề, giữ nguyên số dòng và thứ tự."],
                            f"Ngôn ngữ đích: {lang}\n" + json.dumps(lines, ensure_ascii=False),
                            {"type": "object", "required": ["lines"], "properties": {"lines": {"type": "array", "items": {"type": "string"}}}}, "submit")
        new = ["\n".join(b.splitlines()[:2] + [t]) for b, t in zip(blocks, res["lines"])]
        out = tools_dir() / f"{stem}.{lang}.srt"
        out.write_text("\n\n".join(new) + "\n", encoding="utf-8")
    else:
        raise ValueError(kind)
    return out.name


# ---------------------------------------------------------------- GPU (ComfyUI)
def gpu_ping(url: str) -> dict:
    if not url:
        return {"ok": False, "error": "chưa đặt địa chỉ"}
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=1.5) as r:
            data = json.loads(r.read())
        dev = (data.get("devices") or [{}])[0]
        return {"ok": True, "device": dev.get("name", ""), "vram": round((dev.get("vram_total") or 0) / 2**30, 1),
                "version": data.get("system", {}).get("comfyui_version", "")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def workflows() -> list[str]:
    return sorted(p.stem for p in (config.TEMPLATES / "comfy_workflows").glob("*.json"))


# ---------------------------------------------------------------- cài đặt (settings.local.yaml)
LOCAL = config.CONFIG / "settings.local.yaml"
EDITABLE = {"tts.engine", "tts.rate", "render.workers", "render.encoder", "render.captions", "render.captions_mode",
            "render.caption_words", "render.music", "default_style", "default_aspect", "default_lang", "fps",
            "agent.backend", "visual.comfyui_url", "visual.browser_channel", "visual.default_workflow", "trends.youtube_api_key",
            "agent.tiers.plan", "agent.tiers.ideas", "agent.tiers.edit", "agent.tiers.translate", "agent.tiers.subtitles",
            "agent.tiers.publish"}


def settings_get() -> dict:
    s = config.settings()
    flat = {}
    for k in EDITABLE:
        cur = s
        for part in k.split("."):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        flat[k] = cur if cur != {} else None
    return flat


def settings_set(values: dict) -> dict:
    local = yaml.safe_load(LOCAL.read_text(encoding="utf-8-sig")) if LOCAL.exists() else {}
    local = local or {}
    for k, v in values.items():
        if k not in EDITABLE:
            continue
        parts = k.split(".")
        cur = local
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        if v in ("", None):
            cur.pop(parts[-1], None)
        else:
            cur[parts[-1]] = v
    LOCAL.write_text(yaml.safe_dump(local, allow_unicode=True, sort_keys=False), encoding="utf-8")
    config.settings.cache_clear()
    _checks_cache.clear()
    return settings_get()
