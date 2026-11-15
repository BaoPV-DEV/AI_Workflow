"""Điều phối: voice -> visuals -> render. Mỗi bước đọc/ghi project_manifest.json, có cache."""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import align, captions, config, manifest, tts
from .cache import Cache, digest
from .util import encode_args, ffmpeg, log, pick_encoder, probe_duration, run
from .visual import Job, get as get_adapter

# ---------------------------------------------------------------- helpers

def _ctx(data: dict) -> dict:
    s = config.settings()
    st = config.style(data.get("style") or s.get("default_style", "classic_light"))
    w, h = config.resolution(data)
    return {"settings": s, "style": st, "w": w, "h": h, "fps": data.get("fps") or s.get("fps", 30),
            "lang": data.get("lang") or s.get("default_lang", "vi")}


def build_cast(data: dict, style: dict) -> dict:
    """Ghép preset nhân vật + style + ghi đè trong manifest. Luôn có ít nhất 'hero'."""
    presets = config.library("characters")["characters"]
    base = {**style.get("character", {})}
    cast = data.get("cast") or {"hero": {}}
    out = {}
    for name, c in cast.items():
        p = presets.get(c.get("preset", ""), {})
        out[name] = {**base, **p, **{k: v for k, v in c.items() if k != "preset"}, "name": name}
    return out


def resolve_acting(scene: dict, cast: dict) -> list[dict]:
    lib = config.library("actions")
    aliases = lib.get("aliases", {})
    default_who = next(iter(cast), "hero")
    dur, words = scene.get("duration", 4.0), scene.get("word_timings") or []
    out = []
    for b in scene.get("acting") or []:
        act = aliases.get(b.get("act"), b.get("act"))
        out.append({**b, "act": act, "who": b.get("who") or default_who,
                    "t": round(align.resolve_at(b.get("at"), words, dur), 3)})
    return sorted(out, key=lambda b: b["t"])


def _scenes(data: dict, only: list[str] | None):
    for s in data["scenes"]:
        if not only or manifest.scene_key(s) in only or str(s.get("scene_id")) in only:
            yield s


# ---------------------------------------------------------------- 1. voice

def voice(project, only=None, force=False) -> dict:
    d, data = manifest.load(project)
    c = _ctx(data)
    t = c["settings"]["tts"]
    eng = t.get("engine", "edge")
    voice_name = data.get("voice") or config.default_voice(c["lang"])
    used = {}
    cache = Cache(d)
    pad = c["settings"]["render"].get("scene_pad", 0.25)
    for s in _scenes(data, only):
        key = manifest.scene_key(s)
        wav = d / "assets" / f"{key}.wav"
        text = s.get("voice_text", "")
        h = digest(text, eng, voice_name, t.get("rate"))
        if force or not cache.fresh("tts:" + key, h, wav) or not s.get("word_timings"):
            log(f"  🎙  {key}: {text[:50]}")
            _, tw, got = tts.synth(text, wav, eng, voice_name, t.get("rate", "+0%"), t.get("piper_model", ""), c["lang"])
            speech = probe_duration(wav)
            a = c["settings"]["align"]
            s["word_timings"], how = align.align(wav, text, speech, c["lang"], a.get("engine", "auto"),
                                                 a.get("whisper_model", "base"), tw)
            s["speech"] = round(speech, 3)
            s["tts"] = got
            used[got] = used.get(got, 0) + 1
            log(f"      {speech:.2f}s · giọng: {got}{' (dự phòng)' if eng == 'auto' and got != 'edge' else ''} · mốc từ: {how}")
            cache.put("tts:" + key, h)
        speech = s.get("speech") or probe_duration(wav)
        s["audio_path"] = f"assets/{key}.wav"
        s["duration"] = round(max(speech + pad + float(s.get("pause", 0)), float(s.get("min_duration", 0)), 1.0), 3)
    manifest.save(d, data)
    total = sum(s.get("duration", 0) for s in data["scenes"])
    log(f"✔ Giọng đọc xong: {len(data['scenes'])} cảnh, tổng {total:.1f}s · {c['lang']} · {voice_name}")
    if used.get("silent") and eng != "silent":
        log("⚠ Có cảnh không có lời đọc (voice_text trống) nên im lặng.")
    if eng == "silent":
        log("⚠ tts.engine = silent: video sẽ KHÔNG có tiếng. Xoá dòng này trong config/settings.local.yaml để có giọng.")
    return data


# ---------------------------------------------------------------- 2. visuals

def _render_one(args):
    job, h, key = args
    try:
        get_adapter(job.scene["visual_type"]).render(job)
        return key, h, None
    except Exception as e:  # trả lỗi về tiến trình chính
        return key, h, f"{type(e).__name__}: {e}"


def caption_mode(c: dict) -> str:
    """ass: ffmpeg đốt phụ đề (cần libass). html: vẽ phụ đề ngay trong khung hình (không cần libass)."""
    r = c["settings"]["render"]
    if not r.get("captions", True) or not c["style"].get("captions", {}).get("enabled", True):
        return "off"
    mode = r.get("captions_mode", "auto")
    if mode == "auto":
        import sys
        from .util import has_filter
        mode = "ass" if has_filter("ass") and sys.platform != "win32" else "html"
    return mode


def _jobs(d: Path, data: dict, c: dict, draft: bool, only, estimate: bool = False):
    r = c["settings"]["render"]
    cmode = caption_mode(c)
    enc = pick_encoder(r.get("encoder", "auto"))
    cast = build_cast(data, c["style"])
    clips = d / "build" / ("draft" if draft else "clips")
    clips.mkdir(parents=True, exist_ok=True)
    for s in _scenes(data, only):
        if "duration" not in s:
            if not estimate:
                raise RuntimeError("Chưa có thời lượng: chạy 'vf voice' trước")
            n = len(align.words_of(s.get("voice_text") or "", c["lang"]))
            s = {**s, "duration": max(2.5, n / 2.5 + 0.3)}
            s["word_timings"] = align.estimate(s.get("voice_text") or "", s["duration"] - 0.3, lang=c["lang"])
        key = manifest.scene_key(s)
        sc = {**s, "acting_resolved": resolve_acting(s, cast)}
        if cmode == "html" and s.get("captions") is not False and s.get("template_name") != "kinetic_text":
            sc["_captions"] = {**c["style"].get("captions", {}), "chunk": r.get("caption_words", 4),
                               **captions.layout(s.get("word_timings") or [], c["lang"], r.get("caption_words", 4))}
        job = Job(scene=sc, project_dir=d, out=clips / f"{key}.mp4", width=c["w"], height=c["h"], fps=c["fps"],
                  duration=s["duration"], style=c["style"], cast=cast, encoder=enc, crf=r.get("crf", 20),
                  preset=r.get("preset", "veryfast"), draft=draft)
        yield key, job


def visuals(project, only=None, force=False, draft=False, workers=None) -> list[Path]:
    d, data = manifest.load(project)
    c = _ctx(data)
    cache = Cache(d)
    todo, outs = [], []
    for key, job in _jobs(d, data, c, draft, only):
        ad = get_adapter(job.scene["visual_type"])
        sc = {k: v for k, v in job.scene.items() if k not in ("audio_path", "speech")}
        h = digest(sc, job.width, job.height, job.fps, job.draft, *ad.fingerprint(job))
        outs.append(job.out)
        ck = ("draft:" if draft else "clip:") + key
        if force or not cache.fresh(ck, h, job.out):
            todo.append((job, h, ck))
    workers = workers or c["settings"]["render"].get("workers", 2)
    log(f"🎬 Quay {len(todo)}/{len(outs)} cảnh (còn lại lấy từ cache), {workers} luồng, encoder {pick_encoder(c['settings']['render'].get('encoder', 'auto'))}")
    fails = []
    if todo:
        if workers > 1 and len(todo) > 1:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(_render_one, todo))
        else:
            results = [_render_one(t) for t in todo]
        for key, h, err in results:
            if err:
                fails.append(f"{key}: {err}")
                log(f"  ✘ {key}: {err}")
            else:
                cache.put(key, h)
                log(f"  ✔ {key}")
    if fails:
        raise RuntimeError(f"{len(fails)} cảnh lỗi:\n" + "\n".join(fails))
    return outs


# ---------------------------------------------------------------- 3. render (ghép)

def render(project, draft=False, captions_on=None) -> Path:
    d, data = manifest.load(project)
    c = _ctx(data)
    r = c["settings"]["render"]
    clips = visuals(project, draft=draft)
    d_, data = manifest.load(project)  # đọc lại (visuals không ghi, nhưng an toàn)
    build = d / "build"
    enc = pick_encoder(r.get("encoder", "auto"))
    parts, offsets, t = [], [], 0.0
    for s, clip in zip(data["scenes"], clips):
        key = manifest.scene_key(s)
        part = build / f"part_{key}{'_d' if draft else ''}.mp4"
        dur = s["duration"]
        run([ffmpeg(), "-y", "-v", "error", "-i", clip, "-i", d / s["audio_path"],
             "-filter_complex", f"[1:a]apad,atrim=0:{dur:.3f},aresample=48000[a]", "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", part])
        parts.append(part)
        offsets.append(t)
        t += dur
    lst = build / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    joined = build / "joined.mp4"
    run([ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])

    out_dir = d / "out"
    out_dir.mkdir(exist_ok=True)
    pid = data["project_id"]
    w, h = (c["w"] // 2, c["h"] // 2) if draft else (c["w"], c["h"])
    captions.write(out_dir / f"{pid}.srt", captions.build_srt(data["scenes"], offsets, lang=c["lang"]))
    vf = []
    cap_on = r.get("captions", True) if captions_on is None else captions_on
    if cap_on and caption_mode(c) == "ass":
        ass = captions.write(build / "captions.ass",
                             captions.build_ass(data["scenes"], offsets, w, h, c["style"].get("captions", {}),
                                                r.get("caption_words", 4), c["lang"]))
        vf.append(f"ass='{_ff_path(ass)}'")
    music = data.get("music") or r.get("music")
    inputs, afilter = [joined], "[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    if music:
        mp = (d / "assets" / music) if (d / "assets" / music).exists() else Path(music)
        inputs.append(mp)
        afilter = ("[1:a]volume=0.18,aloop=loop=-1:size=2e9[m];[m][0:a]sidechaincompress=threshold=0.03:ratio=8[duck];"
                   "[0:a][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    final = out_dir / f"{pid}{'_draft' if draft else ''}.mp4"
    cmd = [ffmpeg(), "-y", "-v", "error"]
    for i in inputs:
        cmd += ["-i", i]
    cmd += ["-filter_complex", afilter, "-map", "0:v", "-map", "[a]"]
    if vf:
        cmd += ["-vf", ",".join(vf), *encode_args(enc, r.get("crf", 20), r.get("preset", "veryfast"))]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final]
    run(cmd)
    log(f"✅ Xong: {final}  ({t:.1f}s)")
    return final


def _ff_path(p: Path) -> str:
    s = p.resolve().as_posix()
    return s.replace(":", r"\:") if os.name == "nt" else s


# ---------------------------------------------------------------- preview

def preview(project, at=0.62, only=None) -> Path:
    """Mỗi cảnh 1 ảnh tĩnh + bảng tổng hợp _sheet.jpg (vài giây, để duyệt trước khi render)."""
    from .visual import html as vhtml
    from .visual.media import asset

    d, data = manifest.load(project)
    c = _ctx(data)
    pv = d / "preview"
    pv.mkdir(exist_ok=True)
    stills = []
    for key, job in _jobs(d, data, c, True, only, estimate=True):
        out = pv / f"{key}.jpg"
        vt = job.scene["visual_type"]
        if vt in ("html_animation", "svg_graphic"):
            vhtml.still(job, job.duration * at, out)
        elif vt == "image":
            run([ffmpeg(), "-y", "-v", "error", "-i", asset(job, job.scene["src"]), "-vf",
                 f"scale={job.width // 2}:{job.height // 2}:force_original_aspect_ratio=increase,crop={job.width // 2}:{job.height // 2}",
                 "-frames:v", "1", out])
        else:
            continue
        stills.append(out)
    vhtml.close()
    sheet = pv / "_sheet.jpg"
    if stills:
        contact_sheet(stills, sheet, c["w"], c["h"])
    log(f"🖼  Preview: {sheet}")
    return sheet


def _label_font() -> str | None:
    """File font cụ thể cho drawtext (tránh phụ thuộc fontconfig – hay lỗi trên Windows)."""
    import os
    for f in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(f):
            return f
    return None


def contact_sheet(stills: list[Path], sheet: Path, w: int, h: int, tile_w: int = 360) -> Path:
    n = len(stills)
    cols = min(n, 4 if h > w else 3)
    tile_h = round(tile_w * h / w / 2) * 2
    font = _label_font()

    def build(labels: bool):
        cmd = [ffmpeg(), "-y", "-v", "error"]
        for s in stills:
            cmd += ["-i", s]
        ff = font.replace("\\", "/").replace(":", "\\:") if font else ""
        lab = (lambda p: f",drawtext=fontfile='{ff}':text='{p.stem}':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6") \
            if labels and font else (lambda p: "")
        chains = "".join(f"[{i}:v]scale={tile_w}:{tile_h}{lab(p)}[v{i}];" for i, p in enumerate(stills))
        if n == 1:
            graph = chains.rstrip(";").replace("[v0]", "")
        else:
            layout = "|".join(f"{(i % cols) * tile_w}_{(i // cols) * tile_h}" for i in range(n))
            graph = chains + "".join(f"[v{i}]" for i in range(n)) + f"xstack=inputs={n}:layout={layout}:fill=gray"
        return cmd + ["-filter_complex", graph, "-frames:v", "1", sheet]

    try:
        run(build(True))
    except RuntimeError:
        try:
            run(build(False))  # không vẽ được nhãn thì bỏ nhãn, vẫn có bảng ảnh
        except RuntimeError as e:
            log(f"⚠ Không ghép được _sheet.jpg ({str(e)[:120]}); ảnh từng cảnh vẫn có trong thư mục preview")
    return sheet
