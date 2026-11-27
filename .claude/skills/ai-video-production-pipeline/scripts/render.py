#!/usr/bin/env python3
"""Render a storyboard.json into a finished video (animatic or production).

Usage:
  python3 render.py path/to/storyboard.json            # full render
  python3 render.py path/to/storyboard.json --stills   # key-frame PNGs only
  python3 render.py path/to/storyboard.json --shots S03,S04   # re-render some shots, then re-join
  python3 render.py path/to/storyboard.json --audio-only      # rebuild sound, keep picture
  python3 render.py path/to/storyboard.json --preview         # half size, 15 fps: ~6-8x faster check
  python3 render.py path/to/storyboard.json --gpu             # experimental skia OpenGL drawing (desktop GPUs)
  python3 render.py path/to/storyboard.json --encoder nvenc   # auto|x264|nvenc|qsv|amf|videotoolbox
Run scripts/setup_check.py once per machine: it checks tools and benchmarks the best settings.

Paths inside the storyboard are relative to the storyboard's folder.
Needs: python3, Pillow, numpy, ffmpeg/ffprobe. Optional TTS: festival (text2wave), espeak-ng,
or ElevenLabs (env ELEVENLABS_API_KEY + network). See references/render-pipeline.md.
"""
import argparse, hashlib, json, math, os, random, shutil, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SR = 48000
SKILL_DIR = Path(__file__).resolve().parent.parent
FONT_DIRS = [str(SKILL_DIR / "assets" / "fonts"), "/usr/share/fonts", "/usr/local/share/fonts",
             str(Path.home() / ".fonts"), "C:/Windows/Fonts", str(Path.home() / "AppData/Local/Microsoft/Windows/Fonts"),
             "/Library/Fonts", "/System/Library/Fonts"]
BUNDLED = {"inter:style=extrabold": "Inter-ExtraBold.otf", "inter:style=bold": "Inter-ExtraBold.otf"}
IS_WIN = os.name == "nt"


# ---------------------------------------------------------------- helpers
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r


def find_font(name):
    if name and Path(name).exists():
        return name
    b = BUNDLED.get((name or "").lower())
    if b and (SKILL_DIR / "assets" / "fonts" / b).exists():
        return str(SKILL_DIR / "assets" / "fonts" / b)
    try:
        r = subprocess.run(["fc-match", "-f", "%{file}", name or "sans:bold"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except FileNotFoundError:
        pass
    for pref in ("Inter-ExtraBold.otf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        for d in FONT_DIRS:
            if (Path(d) / pref).exists():
                return str(Path(d) / pref)
    for d in FONT_DIRS:
        if Path(d).exists():
            for p in Path(d).rglob("*Bold*.[ot]tf"):
                return str(p)
    return None


def hex_rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def ease(t, kind="inout"):
    t = min(max(t, 0.0), 1.0)
    if kind == "out":
        return 1 - (1 - t) ** 3
    if kind == "in":
        return t ** 3
    return 3 * t * t - 2 * t * t * t


def read_wav(path):
    with wave.open(str(path)) as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        data = np.frombuffer(w.readframes(n), dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float32)
    data /= 32768.0 if sw == 2 else 2147483648.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, len(data) - 1, int(len(data) * SR / sr))
        data = np.interp(x, np.arange(len(data)), data).astype(np.float32)
    return data


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


def trim_silence(a, thr=0.01):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s, e = max(idx[0] - int(0.02 * SR), 0), min(idx[-1] + int(0.06 * SR), len(a))
    return a[s:e]


# ---------------------------------------------------------------- encoders
ENCODERS = {
    # name: (ffmpeg codec, args builder(quality crf, maxrate, bufsize, preset))
    "x264": lambda q, mr, bs, pr: ["-c:v", "libx264", "-preset", pr, "-crf", str(q), "-maxrate", mr, "-bufsize", bs,
                                   "-profile:v", "high", "-pix_fmt", "yuv420p"],
    "nvenc": lambda q, mr, bs, pr: ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(q + 2),
                                    "-b:v", "0", "-maxrate", mr, "-bufsize", bs, "-profile:v", "high", "-pix_fmt", "yuv420p"],
    "qsv": lambda q, mr, bs, pr: ["-c:v", "h264_qsv", "-preset", "medium", "-b:v", _half(mr), "-maxrate", mr, "-bufsize", bs,
                                  "-profile:v", "high", "-pix_fmt", "nv12"],
    "amf": lambda q, mr, bs, pr: ["-c:v", "h264_amf", "-quality", "quality", "-rc", "vbr_peak", "-b:v", _half(mr),
                                  "-maxrate", mr, "-bufsize", bs, "-pix_fmt", "yuv420p"],
    "videotoolbox": lambda q, mr, bs, pr: ["-c:v", "h264_videotoolbox", "-b:v", _half(mr), "-maxrate", mr, "-pix_fmt", "yuv420p"],
}
HW_ORDER = ["nvenc", "qsv", "amf", "videotoolbox"]
HW_SESSION_LIMIT = {"nvenc": 3, "qsv": 4, "amf": 3, "videotoolbox": 2}   # safe concurrent sessions on consumer GPUs


def _half(rate):
    n = float(rate.rstrip("MmKk")); u = rate[-1] if rate[-1] in "MmKk" else ""
    return f"{n * 0.66:.1f}{u}"


def encoder_works(name):
    args = ENCODERS[name](20, "12M", "24M", "veryfast")
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=0.3"] + args + ["-f", "null", "-"],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def pick_encoder(pref, jobs):
    """auto: a hardware encoder only when the run uses few parallel encoders (session limits); drawing, not encoding,
    is the bottleneck, so x264 across many CPU processes is usually fastest overall."""
    pref = (pref or "auto").lower()
    if pref in ENCODERS and pref != "x264":
        return pref if encoder_works(pref) else "x264"
    if pref == "auto":
        for hw in HW_ORDER:
            if jobs <= HW_SESSION_LIMIT[hw] and encoder_works(hw):
                return hw
    return "x264"


# ---------------------------------------------------------------- voice
def tts(text, voice_cfg, cache_dir, shot_id, base):
    """Return mono float32 voice audio for one shot."""
    if not text.strip():
        return np.zeros(0, np.float32)
    own = base / "voice" / f"{shot_id}.wav"
    if own.exists():  # user-supplied (e.g. ElevenLabs export) always wins
        return trim_silence(read_wav(own))
    engine = voice_cfg.get("engine", "festival")
    key = hashlib.sha1(json.dumps([text, voice_cfg], sort_keys=True).encode()).hexdigest()[:16]
    out = cache_dir / f"{key}.wav"
    if not out.exists():
        tmp = cache_dir / f"{key}.raw.wav"
        if engine == "elevenlabs" and os.environ.get("ELEVENLABS_API_KEY"):
            import urllib.request
            vid = voice_cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=pcm_44100",
                data=json.dumps({"text": text, "model_id": voice_cfg.get("model", "eleven_multilingual_v2")}).encode(),
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
            pcm = urllib.request.urlopen(req, timeout=120).read()
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(pcm)
        elif engine in ("festival", "elevenlabs", "auto") and shutil.which("text2wave"):
            txt = cache_dir / f"{key}.txt"
            txt.write_text(text)
            voice = voice_cfg.get("voice", "cmu_us_slt_arctic_hts")
            stretch = voice_cfg.get("stretch", 1.0)
            run(["text2wave", "-eval", f"(voice_{voice})", "-eval",
                 f"(Parameter.set 'Duration_Stretch {stretch})", str(txt), "-o", str(tmp)])
        elif shutil.which("espeak-ng"):
            run(["espeak-ng", "-v", voice_cfg.get("espeak_voice", "en-us"), "-s",
                 str(voice_cfg.get("wpm", 150)), "-w", str(tmp), text])
        else:
            try:  # Windows / macOS system voices (pip install pyttsx3)
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", voice_cfg.get("wpm", 165))
                eng.save_to_file(text, str(tmp)); eng.runAndWait()
                if not tmp.exists() or tmp.stat().st_size < 1000:
                    raise RuntimeError("pyttsx3 produced no audio")
            except Exception as e:
                sys.exit(f"No TTS available ({e}): add voice/<shot>.wav files, install festival/espeak-ng or pyttsx3, "
                         "or set ELEVENLABS_API_KEY")
        # light polish: high-pass, gentle compression, normalise
        run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af",
             "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,"
             f"atempo={voice_cfg.get('tempo', 1.0)},loudnorm=I=-16:TP=-2",
             "-ar", str(SR), "-ac", "1", str(out)])
    return trim_silence(read_wav(out))


# ---------------------------------------------------------------- sound design (all synthesised, licence-free)
def _env(n, a, r):
    e = np.ones(n, np.float32)
    na, nr = min(int(a * SR), n), min(int(r * SR), n)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def _lowpass(x, cut):
    """One-pole low-pass; cut may be an array (Hz per sample)."""
    if np.isscalar(cut):
        a = 1 - math.exp(-2 * math.pi * cut / SR)
        try:
            from scipy.signal import lfilter
            return lfilter([a], [1, a - 1], x).astype(np.float32)
        except ImportError:
            pass
    cut = np.broadcast_to(np.asarray(cut, np.float32), x.shape)
    a = 1 - np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc); y[i] = acc
    return y


def sfx(name, rng):
    t = lambda d: np.arange(int(d * SR)) / SR
    if name == "whoosh":
        d = 0.7; n = int(d * SR); x = rng.standard_normal(n).astype(np.float32)
        cut = 300 + 5000 * np.sin(np.linspace(0, np.pi, n)) ** 2
        y = _lowpass(x, cut) - _lowpass(x, cut * 0.25)
        return 0.9 * y * np.sin(np.linspace(0, np.pi, n)) ** 1.5 / (np.abs(y).max() + 1e-6)
    if name == "hit":
        tt = t(1.2); f = 40 + 80 * np.exp(-tt * 18)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.5)
        click = rng.standard_normal(len(tt)) * np.exp(-tt * 60) * 0.5
        return (body + click).astype(np.float32) * 0.9
    if name == "tick":
        tt = t(0.06)
        return (np.sin(2 * np.pi * 2600 * tt) * np.exp(-tt * 140) * 0.6).astype(np.float32)
    if name == "riser":
        d = 1.5; tt = t(d); f = 200 * (8 ** (tt / d))
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
        noise = _lowpass(rng.standard_normal(len(tt)).astype(np.float32), 500 + 6000 * tt / d) * 0.6
        return ((tone + noise) * (tt / d) ** 2).astype(np.float32)
    if name == "freeze":
        tt = t(2.0); y = np.zeros_like(tt)
        for k, fr in enumerate([1568, 2093, 2637, 3136]):
            y += np.sin(2 * np.pi * fr * tt + k) * np.exp(-tt * (2 + k))
        y += _lowpass(rng.standard_normal(len(tt)).astype(np.float32), 9000) * np.exp(-tt * 9) * 0.3
        return (y * 0.22 * _env(len(tt), 0.005, 0.3)).astype(np.float32)
    if name == "pop":
        tt = t(0.12); f = 500 + 700 * tt / 0.12
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 35) * 0.5).astype(np.float32)
    if name == "splash":
        tt = t(1.0); n = len(tt)
        noise = rng.standard_normal(n).astype(np.float32)
        body = (_lowpass(noise, 3500) - _lowpass(noise, 300)) * np.exp(-tt * 6)
        thump = np.sin(2 * np.pi * (60 + 90 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 9) * 0.6
        y = body / (np.abs(body).max() + 1e-6) * 0.8 + thump
        for k in range(10):  # droplet blips
            st = int(rng.uniform(0.08, 0.7) * SR); L = int(0.05 * SR); f = rng.uniform(900, 2400)
            if st + L < n:
                bt = np.arange(L) / SR
                y[st:st + L] += np.sin(2 * np.pi * (f + 3000 * bt) * bt) * np.exp(-bt * 70) * 0.25
        return y.astype(np.float32) * 0.9
    if name == "bubbles":
        tt = t(1.6); y = np.zeros(len(tt), np.float32)
        for k in range(14):
            st = int(rng.uniform(0, 1.4) * SR); L = int(0.08 * SR); f = rng.uniform(500, 1400)
            bt = np.arange(L) / SR
            if st + L < len(y):
                y[st:st + L] += np.sin(2 * np.pi * (f + 4000 * bt) * bt) * np.exp(-bt * 45) * 0.3
        return y
    if name == "shrink":
        d = 1.0; tt = t(d); f = 1600 * (0.12 ** (tt / d))
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
        shimmer = _lowpass(rng.standard_normal(len(tt)).astype(np.float32), 7000) * 0.25
        return ((tone + shimmer) * np.sin(np.pi * tt / d) ** 0.7).astype(np.float32)
    if name == "reverse":
        return sfx("freeze", rng)[::-1].copy()
    return np.zeros(1, np.float32)


def music_bed(total, cfg, rng):
    """Generated ambient/tension bed. Returns stereo (n,2)."""
    n = int(total * SR); tt = np.arange(n) / SR
    mood = cfg.get("mood", "tense")
    bpm = cfg.get("bpm", 90); beat = 60 / bpm
    roots = {"tense": [110.0, 103.83, 98.0, 103.83], "wonder": [130.81, 174.61, 146.83, 196.0],
             "uplifting": [130.81, 196.0, 220.0, 174.61]}.get(mood, [110.0, 103.83, 98.0, 103.83])
    minor = mood == "tense"
    bar = beat * 4; L = np.zeros(n, np.float32); R = np.zeros(n, np.float32)
    for i, root in enumerate(roots * int(math.ceil(total / (bar * len(roots))) + 1)):
        s = int(i * bar * SR)
        if s >= n: break
        e = min(n, s + int(bar * SR * 1.25)); seg = tt[: e - s]
        env = _env(e - s, bar * 0.4, bar * 0.45)
        chord = [root, root * (1.189 if minor else 1.26), root * 1.498, root * 2]
        for k, f in enumerate(chord):
            det = 1.003 if k % 2 else 0.997
            L[s:e] += (np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * f * 2 * det * seg)) * env * 0.05
            R[s:e] += (np.sin(2 * np.pi * f * det * seg) + 0.3 * np.sin(2 * np.pi * f * 2 * seg)) * env * 0.05
    sub = np.sin(2 * np.pi * roots[0] / 2 * tt) * 0.06
    pulse = np.zeros(n, np.float32)
    k = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (45 + 60 * np.exp(-k * 30)) * k) * np.exp(-k * 12) * 0.35
    for b in np.arange(0, total, beat):
        s = int(b * SR); e = min(n, s + len(kick)); pulse[s:e] += kick[: e - s]
    hl = int(0.05 * SR)
    hn = rng.standard_normal(hl).astype(np.float32)
    hit = (hn - _lowpass(hn, 5000)) * np.exp(-np.arange(hl) / SR * 80) * 0.25
    hats = np.zeros(n, np.float32)
    for b in np.arange(beat / 2, total, beat):
        s = int(b * SR); e = min(n, s + hl); hats[s:e] += hit[: e - s]
    mixL = L + sub + pulse + hats * 0.8; mixR = R + sub + pulse + hats
    return np.stack([mixL, mixR], axis=1)


# ---------------------------------------------------------------- picture
class Painter:
    def __init__(self, sb, base):
        f = sb.get("format", {})
        self.W, self.H, self.fps = f.get("width", 1920), f.get("height", 1080), f.get("fps", 30)
        lg = sb.get("_logical", {})                      # set by --preview: scenes keep drawing in full-size units
        self.LW, self.LH = lg.get("width", self.W), lg.get("height", self.H)
        self.k = self.H / 1080.0                         # scale for fixed pixel sizes (text, shadows, shake)
        self.gpu = bool(sb.get("_gpu"))
        st = sb.get("style", {})
        self.font_path = find_font(st.get("font", "Inter:style=ExtraBold"))
        self.cap_font_path = find_font(st.get("caption_font", "Inter:style=ExtraBold"))
        self.accent = hex_rgb(st.get("accent", "#FFD23F"))
        self.text_color = hex_rgb(st.get("text_color", "#FFFFFF"))
        self.cap = sb.get("captions", {"burn_in": True, "max_words": 3})
        self.base = base
        self._fonts = {}
        self._imgs = {}
        self.post = sb.get("post", {})
        self._scene_mods = {}
        self.ctx = None

    def font(self, size, cap=False):
        k = (size, cap)
        if k not in self._fonts:
            p = self.cap_font_path if cap else self.font_path
            self._fonts[k] = ImageFont.truetype(p, size) if p else ImageFont.load_default()
        return self._fonts[k]

    def source(self, shot):
        p = shot.get("image")
        if p and (self.base / p).exists():
            key = str(self.base / p)
            if key not in self._imgs:
                im = Image.open(key).convert("RGB")
                # cover-fit at 1.25x so motion never shows an edge
                s = max(self.W * 1.25 / im.width, self.H * 1.25 / im.height)
                self._imgs[key] = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            return self._imgs[key]
        # placeholder card: shows the prompt so the gap is obvious
        im = Image.new("RGB", (int(self.W * 1.25), int(self.H * 1.25)), (18, 20, 28))
        d = ImageDraw.Draw(im)
        d.text((80, 80), f"[{shot['id']}] missing asset", font=self.font(48), fill=(255, 90, 90))
        words, line, y = shot.get("prompt", "").split(), "", 170
        for w in words:
            if len(line) + len(w) > 70:
                d.text((80, y), line, font=self.font(30), fill=(200, 200, 210)); y += 44; line = ""
            line += w + " "
        d.text((80, y), line, font=self.font(30), fill=(200, 200, 210))
        return im

    def scene_img(self, shot, t, dur):
        """Procedural frame from a scene function: "scene": "scenes.py:s01"."""
        import importlib.util
        mod_path, fn = shot["scene"].split(":")
        if mod_path not in self._scene_mods:
            sys.path.insert(0, str(Path(__file__).parent))
            sys.path.insert(0, str(self.base))
            spec = importlib.util.spec_from_file_location(Path(mod_path).stem, self.base / mod_path)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            self._scene_mods[mod_path] = mod
        if self.ctx is None:
            from anim_kit import SceneContext
            self.ctx = SceneContext(self.LW, self.LH, self.fps, scale=self.W / self.LW, gpu=self.gpu)
        im = getattr(self._scene_mods[mod_path], fn)(t, dur, self.ctx)
        if im.size != (self.W, self.H):
            im = im.resize((self.W, self.H), Image.BICUBIC)
        return im.convert("RGBA")

    def frame(self, shot, t, dur, words_timing, first, last, rng):
        if shot.get("scene"):
            img = self.scene_img(shot, t, dur)
            if shot.get("shake_at") is not None and shot["shake_at"] <= t < shot["shake_at"] + 0.5:
                k = 1 - (t - shot["shake_at"]) / 0.5
                dx, dy = rng.uniform(-1, 1) * 16 * k * self.k, rng.uniform(-1, 1) * 11 * k * self.k
                img = img.transform(img.size, Image.AFFINE, (1.02, 0, dx - self.W * 0.01, 0, 1.02, dy - self.H * 0.01), Image.BICUBIC)
        else:
            src = self.source(shot)
            sw, sh = src.size
            p = ease(t / max(dur, 1e-3), "inout")
            motion = shot.get("motion", "zoom_in")
            amt = shot.get("motion_amount", 0.12)
            z0, z1, dx, dy = 1.0, 1.0, 0.0, 0.0
            if motion == "zoom_in": z0, z1 = 1.0, 1.0 + amt
            elif motion == "zoom_out": z0, z1 = 1.0 + amt, 1.0
            elif motion == "pan_left": dx = amt
            elif motion == "pan_right": dx = -amt
            elif motion == "push_up": dy = amt; z0, z1 = 1.02, 1.06
            elif motion == "crash_zoom":
                p = ease(min(t / 0.35, 1), "out"); z0, z1 = 1.0, 1.0 + amt * 2
            z = z0 + (z1 - z0) * p
            # visible window in source pixels (source is 1.25x cover, z=1 shows the central 80%)
            vw, vh = sw / 1.25 / z, sh / 1.25 / z
            cx = sw / 2 + (dx * (p - 0.5)) * sw * 0.18
            cy = sh / 2 + (dy * (0.5 - p)) * sh * 0.18
            fx, fy = shot.get("focus", [0.5, 0.5])
            cx += (fx - 0.5) * (sw - vw); cy += (fy - 0.5) * (sh - vh)
            if motion == "shake" or shot.get("shake_at") is not None and t >= shot["shake_at"] and t < shot["shake_at"] + 0.5:
                k = 1.0 if motion == "shake" else 1 - (t - shot["shake_at"]) / 0.5
                cx += rng.uniform(-1, 1) * 14 * k * self.k; cy += rng.uniform(-1, 1) * 10 * k * self.k
            cx = min(max(cx, vw / 2), sw - vw / 2); cy = min(max(cy, vh / 2), sh - vh / 2)
            img = src.resize((self.W, self.H), Image.BICUBIC,
                             box=(cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)).convert("RGBA")

        grade = shot.get("grade")
        if grade == "freeze" and t >= shot.get("grade_at", 0):
            k = ease((t - shot.get("grade_at", 0)) / 0.4, "out")
            cold = Image.new("RGBA", img.size, (120, 190, 255, int(70 * k)))
            img = Image.alpha_composite(img, cold)
        elif grade == "dark":  # fade the picture to near-black across the shot
            k = ease((t - shot.get("grade_at", 0.3)) / max(dur * 0.6, 0.1), "inout")
            img = Image.alpha_composite(img, Image.new("RGBA", img.size, (0, 0, 0, int(235 * k))))
        if self.post.get("vignette", True):
            img = Image.alpha_composite(img, self._vignette())
        if self.post.get("bloom"):
            from anim_kit import bloom, chroma
            b = self.post["bloom"]
            img = bloom(img, b.get("threshold", 170), b.get("strength", 0.6), b.get("radius", 18) * self.k)
            if self.post.get("chroma"):
                img = chroma(img, self.post["chroma"])
            img = img.convert("RGBA")
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # on-screen text
        tx = shot.get("text")
        if tx and t >= tx.get("at", 0):
            lt = t - tx.get("at", 0)
            size = int(tx.get("size", 150) * self.k)
            anim = tx.get("anim", "pop")
            if anim == "pop":
                sc = 0.6 + 0.4 * ease(lt / 0.22, "out") + 0.06 * math.sin(min(lt / 0.22, 1) * math.pi)
            else:
                sc = 1.0
            alpha = int(255 * ease(lt / 0.15, "out"))
            fnt = self.font(max(10, int(size * sc)))
            content = tx["content"]
            bb = d.multiline_textbbox((0, 0), content, font=fnt, align="center", spacing=int(size * 0.05))
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            pos = tx.get("position", "center")
            x = (self.W - tw) / 2
            y = {"top": self.H * 0.12, "center": (self.H - th) / 2 - self.H * 0.06,
                 "upper": self.H * 0.22}.get(pos, (self.H - th) / 2)
            col = self.accent if tx.get("accent", True) else self.text_color
            # soft shadow — blurred only inside the text's box (a full-frame blur cost ~40 ms/frame)
            pad = int(30 * self.k) + 10
            bw, bh = int(tw + 2 * pad), int(th + 2 * pad)
            sh_ = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(sh_).multiline_text((pad + 6 * self.k, pad + 8 * self.k - bb[1]), content, font=fnt,
                                               fill=(0, 0, 0, int(alpha * 0.7)), align="center", spacing=int(size * 0.05))
            ov.alpha_composite(sh_.filter(ImageFilter.GaussianBlur(10 * self.k)), (int(x - pad), int(y - pad)))
            d = ImageDraw.Draw(ov)
            d.multiline_text((x, y - bb[1]), content, font=fnt, fill=col[:3] + (alpha,), align="center",
                             spacing=int(size * 0.05), stroke_width=max(2, size // 30), stroke_fill=(0, 0, 0, alpha))

        # captions (word groups, active group highlighted)
        if self.cap.get("burn_in", True) and words_timing:
            grp = [g for g in words_timing if g[0] <= t < g[1]]
            if grp:
                g0, g1, text = grp[0]
                size = self.cap.get("size", int(self.H * 0.065))
                fnt = self.font(size, cap=True)
                txt = text.upper() if self.cap.get("upper", True) else text
                bb = d.textbbox((0, 0), txt, font=fnt)
                tw = bb[2] - bb[0]
                lt = t - g0
                sc_y = int(8 * self.k * (1 - ease(lt / 0.12, "out")))
                y = self.H * self.cap.get("y", 0.86) + sc_y
                if self.cap.get("box", True):
                    th = bb[3] - bb[1]; px, py = size * 0.35, size * 0.22
                    d.rounded_rectangle([(self.W - tw) / 2 - px, y - py, (self.W + tw) / 2 + px, y + th + py],
                                        radius=int(size * 0.3), fill=(0, 0, 0, self.cap.get("box_alpha", 150)))
                d.text(((self.W - tw) / 2, y - bb[1]), txt, font=fnt, fill=(255, 255, 255, 255),
                       stroke_width=max(3, size // 12), stroke_fill=(0, 0, 0, 255))
        img = Image.alpha_composite(img, ov)

        # transitions inside the shot file
        fade_black = 0.0
        if first and t < 0.4: fade_black = 1 - ease(t / 0.4)
        if last and dur - t < 0.6: fade_black = max(fade_black, ease(1 - (dur - t) / 0.6))
        if shot.get("transition_in") == "fade" and t < 0.25: fade_black = max(fade_black, 1 - ease(t / 0.25))
        out = img.convert("RGB")
        if fade_black > 0:
            out = Image.blend(out, Image.new("RGB", out.size, (0, 0, 0)), fade_black)
        if shot.get("transition_in") == "flash" and t < 0.18:
            out = Image.blend(out, Image.new("RGB", out.size, (255, 255, 255)), 1 - t / 0.18)
        if self.post.get("grain"):
            from anim_kit import grain
            out = grain(out, self.post["grain"], int(t * self.fps) + hash(shot["id"]) % 97)
        return out

    def _vignette(self):
        if not hasattr(self, "_vg"):
            yy, xx = np.mgrid[0:self.H, 0:self.W]
            r = np.sqrt(((xx - self.W / 2) / (self.W / 2)) ** 2 + ((yy - self.H / 2) / (self.H / 2)) ** 2)
            a = (np.clip(r - 0.75, 0, 1) * 200).clip(0, 140).astype(np.uint8)
            vg = np.zeros((self.H, self.W, 4), np.uint8); vg[..., 3] = a
            self._vg = Image.fromarray(vg, "RGBA")
        return self._vg


# ---------------------------------------------------------------- timeline
def stretch_audio(a, factor, cache):
    """Time-stretch mono audio by factor (>1 = faster) without changing pitch."""
    src, dst = cache / "_st_in.wav", cache / "_st_out.wav"
    write_wav(src, a)
    chain = []
    f = factor
    while f > 2.0: chain.append("atempo=2.0"); f /= 2.0
    while f < 0.5: chain.append("atempo=0.5"); f /= 0.5
    chain.append(f"atempo={f:.4f}")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", ",".join(chain), "-ac", "1", "-ar", str(SR), str(dst)])
    return read_wav(dst)


def plan(sb, base, cache):
    vcfg = sb.get("voice", {})
    lead = sb.get("timing", {}).get("lead", 0.12)
    tail = sb.get("timing", {}).get("tail", 0.18)
    shots = []
    for sh in sb["shots"]:
        vo = tts(sh.get("vo", ""), vcfg, cache, sh["id"], base)
        vo_d = len(vo) / SR
        shots.append({**sh, "_vo": vo, "_vo_d": vo_d, "_lead": lead})
    # fit speaking rate to voice.target_wpm (default 150) unless the user supplied recorded files
    target = vcfg.get("target_wpm", 150)
    words = sum(len(s_.get("vo", "").split()) for s_ in shots)
    spoken = sum(s_["_vo_d"] for s_ in shots)
    if target and spoken and not (base / "voice").exists():
        factor = (words / spoken * 60) / target
        factor = min(max(factor, 0.75), 1.33)
        if abs(factor - 1) > 0.03:
            print(f"voice: {words / spoken * 60:.0f} wpm -> {target} wpm (atempo {1 / factor:.3f})", flush=True)
            for s_ in shots:
                if len(s_["_vo"]):
                    s_["_vo"] = stretch_audio(s_["_vo"], 1 / factor, cache); s_["_vo_d"] = len(s_["_vo"]) / SR
    for s_ in shots:
        d = max(s_.get("min_duration", 1.0), (lead + s_["_vo_d"] + tail) if s_["_vo_d"] else 0)
        if s_.get("duration"):
            d = max(d, s_["duration"])
        s_["_dur"] = d
    fps = sb.get("format", {}).get("fps", 30)
    t = 0.0
    for sh in shots:  # snap to whole frames so picture and sound never drift
        fr = round(sh["_dur"] * fps); sh["_frames"] = fr; sh["_dur"] = fr / fps
        sh["_start"] = t; t += sh["_dur"]
    return shots, t


def caption_groups(sh, max_words):
    words = sh.get("vo", "").split()
    if not words or not sh["_vo_d"]:
        return []
    # split at punctuation first, then into balanced chunks of <= max_words (no one-word orphans)
    phrases, cur = [], []
    for w in words:
        cur.append(w)
        if w[-1] in ".,!?;:":
            phrases.append(cur); cur = []
    if cur: phrases.append(cur)
    groups = []
    for ph in phrases:
        k = math.ceil(len(ph) / max_words)
        base, extra = divmod(len(ph), k)  # e.g. 7 words, max 3 -> 3,2,2 (never 3,3,1)
        i = 0
        for j in range(k):
            n = base + (1 if j < extra else 0)
            groups.append(" ".join(ph[i:i + n])); i += n
    weights = [sum(len(w) + 2 for w in g.split()) + (6 if g[-1] in ".,!?;:" else 0) for g in groups]
    tot = sum(weights); t = sh["_lead"]; out = []
    for g, wgt in zip(groups, weights):
        d = sh["_vo_d"] * wgt / tot
        out.append((t, t + d, g.strip(".,;:") if g[-1] in ".,;:" else g)); t += d
    out[-1] = (out[-1][0], sh["_dur"], out[-1][2])  # last group holds to the cut
    return out


_WORKER = {}


def _painter(sb, base):
    key = id(sb)
    if key not in _WORKER:
        _WORKER.clear(); _WORKER[key] = Painter(sb, Path(base))
    return _WORKER[key]


def _encode_chunk(job):
    """Worker: draw frames [f0, f1) of one shot and encode them to their own file (separate process)."""
    sb, base, sh, i, n, outdir, f0, f1, enc_args, name = job
    P = _painter(sb, base)
    fps = P.fps
    groups = caption_groups(sh, sb.get("captions", {}).get("max_words", 3))
    tmpdir = Path(outdir) / sb.get("_shots_dir", "shots")
    tmp = tmpdir / f"{name}.part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{P.W}x{P.H}", "-r", str(fps), "-i", "-"] + enc_args + ["-r", str(fps), str(tmp)],
                         stdin=subprocess.PIPE)
    for f in range(f0, f1):
        rng = random.Random(i * 100003 + f)  # deterministic per frame, whichever process draws it
        p.stdin.write(P.frame(sh, f / fps, sh["_dur"], groups, i == 0, i == n - 1, rng).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"encode failed for {name}")
    os.replace(tmp, tmpdir / f"{name}.mp4")
    return name, (f1 - f0) / fps


def render_picture(sb, base, shots, outdir, only=None, stills=False, jobs=None, encoder="auto"):
    tmpdir = outdir / sb.get("_shots_dir", "shots"); tmpdir.mkdir(parents=True, exist_ok=True)
    if stills:
        P = Painter(sb, base)
        maxw = sb.get("captions", {}).get("max_words", 3)
        for i, sh in enumerate(shots):
            groups = caption_groups(sh, maxw)
            for frac in sh.get("still_at", [0.6]):
                f = int(sh["_frames"] * frac)
                P.frame(sh, sh["_dur"] * frac, sh["_dur"], groups, i == 0, i == len(shots) - 1,
                        random.Random(i * 100003 + f)).save(outdir / f"still_{sh['id']}_{int(frac*100)}.png")
        return None
    jobs = jobs or os.cpu_count() or 1
    enc = sb.get("encode", {})
    codec = pick_encoder(encoder if encoder != "auto" else enc.get("encoder", "auto"), jobs)
    enc_args = ENCODERS[codec](enc.get("crf", 20), enc.get("maxrate", "10M"), enc.get("bufsize", enc.get("maxrate", "10M")),
                               enc.get("preset", "veryfast"))
    # split shots into chunks so every core stays busy even with few, long shots
    total_frames = sum(sh["_frames"] for sh in shots)
    target = max(int(sb.get("_chunk_frames", 0)) or math.ceil(total_frames / (jobs * 3)), 12)
    names, todo = [], []
    for i, sh in enumerate(shots):
        nchunks = max(1, round(sh["_frames"] / target))
        bounds = [round(sh["_frames"] * k / nchunks) for k in range(nchunks + 1)]
        light = {k: v for k, v in sh.items() if k != "_vo"}
        for c in range(nchunks):
            name = f"{sh['id']}_{c:03d}"
            names.append(name)
            if only and sh["id"] not in only and (tmpdir / f"{name}.mp4").exists():
                continue
            todo.append((sb, str(base), light, i, len(shots), str(outdir), bounds[c], bounds[c + 1], enc_args, name))
    print(f"render: {len(todo)} chunks, {jobs} workers, encoder {codec}", flush=True)
    todo.sort(key=lambda j: -(j[7] - j[6]))
    if jobs > 1 and len(todo) > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn" if IS_WIN or sb.get("_gpu") else "fork")  # GL contexts and Windows need spawn
        with ctx.Pool(min(jobs, len(todo))) as pool:
            for k, (nm, d) in enumerate(pool.imap_unordered(_encode_chunk, todo), 1):
                print(f"  {k}/{len(todo)} {nm} {d:.2f}s", flush=True)
    else:
        for j in todo:
            nm, d = _encode_chunk(j); print(f"  {nm} {d:.2f}s", flush=True)
    lst = tmpdir / "list.txt"
    lst.write_text("".join(f"file '{nm}.mp4'\n" for nm in names))
    silent = outdir / ("picture-preview.mp4" if sb.get("_preview") else "picture.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
    return silent


def render_audio(sb, shots, total, outdir):
    rng = np.random.default_rng(7)
    n = int(total * SR) + SR
    vo = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    duck = np.ones(n, np.float32)
    mute = np.ones(n, np.float32)
    for sh in shots:
        s = int((sh["_start"] + sh["_lead"]) * SR)
        v = sh["_vo"]; vo[s:s + len(v)] += v[: max(0, n - s)]
        if len(v):
            a, b = s, min(n, s + len(v))
            duck[max(0, a - int(0.15 * SR)):b + int(0.25 * SR)] = sb.get("music", {}).get("duck", 0.45)
        for item in sh.get("sfx", []):
            name, _, at = item.partition("@")
            at = float(at or 0); gain = 1.0
            if "*" in name: name, g = name.split("*"); gain = float(g)
            clip = sfx(name, rng) * gain * sb.get("sfx_gain", 0.8)
            s2 = int((sh["_start"] + at) * SR)
            if name == "riser":  # risers end on the given time
                s2 -= len(clip)
            s2 = max(0, s2); e2 = min(n, s2 + len(clip)); fx[s2:e2] += clip[: e2 - s2]
        if sh.get("music_drop"):
            a = int(sh["_start"] * SR); b = int((sh["_start"] + sh["_dur"]) * SR)
            mute[a:b] = 0.0
    # smooth the ducking/mute envelopes
    k = int(0.08 * SR); ker = np.ones(k, np.float32) / k
    duck = np.convolve(duck, ker, mode="same"); mute = np.convolve(mute, ker, mode="same")
    mcfg = sb.get("music", {})
    if mcfg.get("file") and Path(mcfg["file"]).exists():
        m = read_wav(mcfg["file"]); m = np.tile(m, int(n / len(m)) + 1)[:n]; m = np.stack([m, m], 1)
    else:
        m = music_bed(n / SR + 0.05, mcfg, rng)[:n]
    if len(m) < n:
        m = np.pad(m, ((0, n - len(m)), (0, 0)))
    mg = 10 ** (mcfg.get("volume_db", -6) / 20)
    fade = np.ones(n, np.float32); fl = int(0.8 * SR); end = int(total * SR)
    fade[:int(0.3 * SR)] = np.linspace(0, 1, int(0.3 * SR))
    fade[end - fl:end] = np.linspace(1, 0, fl); fade[end:] = 0
    music = m * (duck * mute * fade * mg)[:, None]
    mix = music + vo[:, None] * 1.0 + fx[:, None] * 0.9
    mix = mix[:end]
    raw = outdir / "mix.raw.wav"; write_wav(raw, mix / (np.abs(mix).max() + 1e-6) * 0.9)
    final = outdir / "mix.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-ar", str(SR), str(final)])
    return final


def write_srt(shots, path, max_words):
    def ts(x):
        ms = int(round(x * 1000)); return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    lines, k = [], 1
    for sh in shots:
        for a, b, g in caption_groups(sh, max(max_words, 6)):
            lines.append(f"{k}\n{ts(sh['_start']+a)} --> {ts(sh['_start']+b)}\n{g}\n"); k += 1
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--shots", default="")
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--jobs", type=int, default=0, help="parallel worker processes (default: all CPU threads)")
    ap.add_argument("--preview", action="store_true", help="half size, 15 fps, separate output — for quick checks")
    ap.add_argument("--gpu", action="store_true", help="experimental: draw scenes with skia OpenGL (needs pip glfw + display)")
    ap.add_argument("--encoder", default="auto", help="auto|x264|nvenc|qsv|amf|videotoolbox")
    a = ap.parse_args()
    prof_path = SKILL_DIR / "render_profile.json"          # written by setup_check.py for this machine
    if prof_path.exists():
        prof = json.loads(prof_path.read_text())
        a.jobs = a.jobs or prof.get("jobs", 0)
        a.gpu = a.gpu or bool(prof.get("gpu"))
        if a.encoder == "auto": a.encoder = prof.get("encoder", "auto")
    sbp = Path(a.storyboard).resolve(); base = sbp.parent
    sb = json.loads(sbp.read_text(encoding="utf-8"))
    if a.preview:
        f = sb.setdefault("format", {})
        sb["_logical"] = {"width": f.get("width", 1920), "height": f.get("height", 1080)}
        f["width"], f["height"] = f.get("width", 1920) // 2, f.get("height", 1080) // 2
        f["fps"] = 15
        sb["_preview"] = True; sb["_shots_dir"] = "shots-preview"
        sb.setdefault("encode", {}).update({"crf": 24, "maxrate": "3M", "bufsize": "3M"})
    if a.gpu:
        sb["_gpu"] = True
        a.jobs = a.jobs or 2   # one GPU: a couple of drawing processes is the sweet spot
    outdir = base / sb.get("out_dir", "out"); outdir.mkdir(exist_ok=True)
    cache = outdir / "cache"; cache.mkdir(exist_ok=True)
    shots, total = plan(sb, base, cache)
    print(f"plan: {len(shots)} shots, {total:.2f}s", flush=True)
    if a.stills:
        render_picture(sb, base, shots, outdir, stills=True); print("stills written to", outdir); return
    only = set(filter(None, a.shots.split(",")))
    pic = outdir / ("picture-preview.mp4" if a.preview else "picture.mp4")
    if not a.audio_only or not pic.exists():
        pic = render_picture(sb, base, shots, outdir, only=only or None, jobs=a.jobs or None, encoder=a.encoder)
    snd = render_audio(sb, shots, total, outdir)
    slug = sb.get("slug", "video") + ("-preview" if a.preview else "")
    final = outdir / f"{slug}.mp4"; tmp = outdir / f"{slug}.part.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(pic), "-i", str(snd), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(tmp)])
    os.replace(tmp, final)
    write_srt(shots, outdir / f"{slug}.srt", sb.get("captions", {}).get("max_words", 3))

    # QA numbers
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)]).stdout)
    size_mb = final.stat().st_size / 1e6
    ln = run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    lufs = tp = None
    for line in ln.splitlines()[::-1]:
        s = line.strip()
        if s.startswith("I:") and lufs is None: lufs = float(s.split()[1])
        if s.startswith("Peak:") and tp is None: tp = float(s.split()[1])
    words = sum(len(sh.get("vo", "").split()) for sh in shots)
    vo_time = sum(sh["_vo_d"] for sh in shots)
    target = sb.get("target_seconds")
    qa = {
        "file": final.name, "duration_s": round(dur, 2), "target_s": target,
        "duration_error_pct": round((dur - target) / target * 100, 1) if target else None,
        "shots": len(shots), "avg_shot_s": round(total / len(shots), 2),
        "words": words, "wpm_over_video": round(words / dur * 60, 1),
        "wpm_while_speaking": round(words / vo_time * 60, 1) if vo_time else None,
        "pattern_interrupts": sum(1 for sh in shots if sh.get("pi")),
        "missing_assets": [sh["id"] for sh in shots if not sh.get("scene") and not (sh.get("image") and (base / sh["image"]).exists())],
        "integrated_lufs": lufs, "true_peak_dbtp": tp,
        "size_mb": round(size_mb, 1), "video_mbps": round(size_mb * 8 / dur, 1),
        "voice_engine": "user files" if (base / "voice").exists() else sb.get("voice", {}).get("engine", "festival"),
        "per_shot": [{"id": sh["id"], "start": round(sh["_start"], 2), "dur": round(sh["_dur"], 2),
                      "vo_s": round(sh["_vo_d"], 2), "words": len(sh.get("vo", "").split())} for sh in shots],
    }
    (outdir / "qa.json").write_text(json.dumps(qa, indent=2))
    print(json.dumps({k: v for k, v in qa.items() if k != "per_shot"}, indent=2))


if __name__ == "__main__":
    main()
