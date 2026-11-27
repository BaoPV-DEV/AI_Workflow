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
    if not thumb:  # chưa "Xem trước" lần nào nhưng đã xuất video → tự trích 1 khung hình làm ảnh đại diện
        thumb = thumbnail(d.name)
    subs = sorted({p.suffixes[-2].lstrip(".") for p in out.glob("*.*.srt")}) if out.exists() else []
    return {"id": d.name, "title": data.get("title") or d.name.replace("_", " ").capitalize(), "series": data.get("series", ""),
            "scenes": len(scenes), "lang": data.get("lang", "vi"), "aspect": data.get("aspect_ratio", "9:16"),
            "duration": round(sum(s.get("duration", 0) for s in scenes), 1), "style": data.get("style", ""),
            "voiced": all(s.get("duration") for s in scenes) and bool(scenes),
            "rendered": any("_draft" not in v.name for v in vids), "draft": any("_draft" in v.name for v in vids),
            "videos": [v.name for v in vids], "subs": [data.get("lang", "vi")] + subs,
            "publish": {p.stem.removeprefix("publish_"): p.name for p in out.glob("publish_*.json")} if out.exists() else {},
            "audit": (out / "audit.json").exists(),
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


def thumbnail(pid: str, at: float | None = None) -> Path | None:
    """Ảnh đại diện từ video đã xuất (khi chưa có ảnh xem trước).
    at: chỉ định giây muốn lấy khung hình (vd. người dùng chọn lại) → luôn ghi đè."""
    d = manifest.project_dir(pid)
    t = d / "build" / "thumb.jpg"
    vids = sorted((d / "out").glob("*.mp4")) if (d / "out").exists() else []
    if vids and (at is not None or not t.exists()):
        t.parent.mkdir(exist_ok=True)
        run([ffmpeg(), "-y", "-v", "error", "-ss", f"{at if at is not None else 1.5:.2f}", "-i", vids[0],
             "-frames:v", "1", "-vf", "scale=480:-2", t])
    return t if t.exists() else None


def thumbnail_pro(pid: str, text: str | None = None, badge: str | None = None, at: float | None = None) -> Path:
    """Thumbnail 'xịn' để thu hút click: khung hình nét từ video + chữ to + dải màu, đúng tông màu/font của style
    video (không chỉ 1 khung hình trần như thumbnail()). Ghi đè build/thumb.jpg, luôn là ảnh đại diện mới nhất."""
    import base64
    from .visual.html import browser

    d, data = manifest.load(pid)
    vids = sorted((d / "out").glob("*.mp4")) if (d / "out").exists() else []
    if not vids:
        raise RuntimeError("Chưa có video đã xuất để lấy khung hình. Xuất video trước.")
    scenes = data.get("scenes", [])
    dur = sum(s.get("duration", 0) for s in scenes) or 10
    if at is not None:
        frame_at = at
    else:
        # ưu tiên lấy giữa 1 cảnh có nhân vật diễn (bắt mắt hơn nền trống/chữ), bỏ qua cảnh đầu (hay là tiêu đề/mở bài)
        t0, pick = 0.0, None
        for s in scenes:
            sd = s.get("duration", 0)
            if pick is None and s.get("template_name") == "stickman_stage" and t0 > 0.3:
                pick = t0 + sd * 0.5
            t0 += sd
        frame_at = pick if pick is not None else max(1.0, dur * 0.3)
    raw = d / "build" / "_thumb_raw.jpg"
    raw.parent.mkdir(parents=True, exist_ok=True)
    # cắt bỏ ~30% phía dưới khung hình: đó là vùng phụ đề đã in sẵn vào video (karaoke), giữ lại sẽ đè chữ rối lên thumbnail
    run([ffmpeg(), "-y", "-v", "error", "-ss", f"{frame_at:.2f}", "-i", vids[0], "-frames:v", "1",
         "-vf", "scale=960:-2,crop=in_w:in_h*0.72:0:0", raw])
    b64 = base64.b64encode(raw.read_bytes()).decode()
    raw.unlink(missing_ok=True)

    aspect = data.get("aspect_ratio", "9:16")
    W, H = (720, 1280) if aspect == "9:16" else (1080, 1080) if aspect == "1:1" else (1280, 720)
    st = config.style(data.get("style", "classic_light"))
    accent = st.get("accent", ["#ff3b30"])
    title = (text or data.get("thumbnail_text") or data.get("title") or pid.replace("_", " ")).strip()
    title = " ".join(title.split()[:8])  # thumbnail chỉ cần vài từ ấn tượng, không phải cả câu
    info = {"bg": f"data:image/jpeg;base64,{b64}", "title": title, "badge": badge,
            "a1": accent[0] if accent else "#ff3b30", "a2": accent[1] if len(accent) > 1 else "",
            "a3": accent[2] if len(accent) > 2 else "", "ink": st.get("ink", "#111"),
            "title_font": st.get("title_font", "Arial Black, sans-serif"),
            "font_size": 11 if len(title) < 18 else 8.5 if len(title) < 32 else 6.5}

    b = browser()
    page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    try:
        page.add_init_script(f"window.THUMB_INPUT = {json.dumps(info, ensure_ascii=False)}")
        page.goto((config.TEMPLATES / "thumbnail.html").resolve().as_uri())
        page.wait_for_function("window.__thumbReady === true")
        out = d / "build" / "thumb.jpg"
        page.screenshot(path=out, type="jpeg", quality=88)
    finally:
        page.close()
    return {"thumb": f"/files/{pid}/build/thumb.jpg?{int(out.stat().st_mtime)}"}


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
    res = complete_json("publish", [_prompt("publish")],
        f"Nền tảng: {platform}\nKhung hình: {data.get('aspect_ratio', '9:16')}\nThời lượng: {round(t)} giây\n"
        f"Tiêu đề tạm: {data.get('title', '')}\nChương có sẵn: {chapters}\n\nKỊCH BẢN:\n{script[:6000]}",
        PUBLISH_SCHEMA, "submit")
    if chapters and not res.get("chapters"):
        res["chapters"] = chapters
    out = d / "out"
    out.mkdir(exist_ok=True)
    (out / f"publish_{platform.replace(' ', '_').lower()}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _prompt(name: str) -> str:
    return (config.CONFIG / "prompts" / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- kiểm duyệt chính sách (từ repo Skills)
AUDIT_SCHEMA = {"type": "object", "required": ["issues", "ai_disclosure", "status"], "properties": {
    "issues": {"type": "array", "items": {"type": "object", "required": ["scene_id", "item", "level", "problem"], "properties": {
        "scene_id": {"type": "integer", "description": "0 = tiêu đề video"}, "item": {"type": "string", "description": "mã mục, vd D3, C4"},
        "level": {"type": "string", "enum": ["CHAN", "RUI_RO", "LUU_Y"]}, "problem": {"type": "string", "description": "đoạn vi phạm ≤15 từ + lý do"},
        "field": {"type": "string", "enum": ["voice_text", "props", "title"]}, "rewrite": {"type": "string"}}}},
    "ai_disclosure": {"type": "string", "description": "Bật / Không cần + lý do"},
    "inauthentic_risk": {"type": "string", "description": "Thấp / TB / Cao + lý do"},
    "ad_friendly": {"type": "string", "description": "Xanh dự kiến / Có thể vàng + điểm còn lại"},
    "status": {"type": "string", "description": "SẴN SÀNG hoặc CẦN NGƯỜI DÙNG QUYẾT ĐỊNH: …"}}}


def policy_audit(pid: str) -> dict:
    """Rà kịch bản theo checklist chính sách YouTube/TikTok, đề xuất câu viết lại. Lưu out/audit.json."""
    from .agent.llm import complete_json

    d, data = manifest.load(pid)
    lines = [f"0|title|{data.get('title', '')}"]
    for s in data["scenes"]:
        props = {k: v for k, v in (s.get("props") or {}).items() if isinstance(v, str) and len(v) < 200}
        lines.append(f"{s['scene_id']}|{s.get('template_name') or s.get('visual_type')}|{s.get('voice_text', '')}"
                     + (f"|chữ: {json.dumps(props, ensure_ascii=False)}" if props else "")
                     + (f"|prompt ảnh: {s['prompt']}" if s.get("prompt") else ""))
    res = complete_json("audit", [_prompt("policy")],
                        f"Ngôn ngữ: {data.get('lang', 'vi')} · Khung {data.get('aspect_ratio', '9:16')} · hình: hoạt hình người que/đồ hoạ vẽ bằng code"
                        f" · giọng: TTS tổng hợp (không mô phỏng người thật)\nCẢNH (id|kiểu|lời đọc|…):\n" + "\n".join(lines)[:12000],
                        AUDIT_SCHEMA, "submit")
    res["applied"] = []
    out = d / "out"
    out.mkdir(exist_ok=True)
    (out / "audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def audit_apply(pid: str, idx: list[int] | None = None) -> dict:
    """Áp các câu viết lại (field voice_text/title) của audit.json vào manifest. Cảnh đổi lời sẽ cần tạo lại giọng."""
    d, data = manifest.load(pid)
    f = d / "out" / "audit.json"
    res = json.loads(f.read_text(encoding="utf-8"))
    by_id = {s["scene_id"]: s for s in data["scenes"]}
    done = []
    for i, it in enumerate(res.get("issues", [])):
        if (idx is not None and i not in idx) or i in res.get("applied", []) or not it.get("rewrite"):
            continue
        if it.get("field") == "title" or it.get("scene_id") == 0:
            data["title"] = it["rewrite"]
        elif it.get("field", "voice_text") == "voice_text" and it.get("scene_id") in by_id:
            sc = by_id[it["scene_id"]]
            sc["voice_text"] = it["rewrite"]
            for k in ("audio_path", "duration", "word_timings"):  # lời mới → giọng và mốc từ phải tạo lại
                sc.pop(k, None)
        else:
            continue  # chữ trên màn hình: để người dùng tự sửa trong Trình sửa cảnh
        done.append(i)
    if done:
        manifest.save(d, data)
        res["applied"] = sorted(set(res.get("applied", [])) | set(done))
        f.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"applied": done, "audit": res}


# ---------------------------------------------------------------- công cụ nhanh (video có sẵn)
def tools_dir() -> Path:
    d = _ws() / "_tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tools_delete(name: str) -> None:
    f = tools_dir() / Path(name).name  # Path(...).name chặn "../" thoát khỏi thư mục _tools
    if f.exists():
        f.unlink()


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
            "agent.tiers.publish", "agent.tiers.audit", "studio.auto_exit", "char3d.cpu", "char3d.device"}


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
