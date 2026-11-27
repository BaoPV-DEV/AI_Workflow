#!/usr/bin/env python3
"""Check this machine for the render pipeline, benchmark it, and save the fastest settings.

    python setup_check.py            # check + benchmark (≈1 min), writes ../render_profile.json
    python setup_check.py --quick    # checks only

render.py reads render_profile.json for its defaults (workers, encoder, GPU drawing).
Works on Windows, Linux and macOS.
"""
import argparse, importlib, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent / "render_profile.json"
OK, WARN, BAD = "✔", "!", "✘"


def line(sym, name, detail=""):
    print(f"  {sym} {name:<28} {detail}")


def ram_gb():
    try:
        import psutil
        return psutil.virtual_memory().total / 1e9
    except ImportError:
        pass
    try:
        if os.name == "nt":
            import ctypes
            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("t", ctypes.c_ulonglong)] + [(f"x{i}", ctypes.c_ulonglong) for i in range(6)]
            m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.t / 1e9
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except Exception:
        return 0


def nvidia():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=15)
        return r.stdout.strip() or None
    except Exception:
        return None


def bench_scene(ctx, frames=12):
    """Representative frame: night city, rain, hero, rays, bokeh, vignette (similar to real scenes)."""
    import anim_kit as K
    rain = K.Rain(ctx.W, ctx.H, n=1400, seed=1)
    city = None
    t0 = None
    for i in range(frames + 2):
        if i == 2:
            t0 = time.perf_counter()          # skip warm-up frames (one-time layer building)
        t = i / 30
        s = ctx.surface(); c = s.getCanvas()
        K.sky(c, ctx.W, ctx.H)
        if city is None:
            city = K.make_city_layer(ctx.W, ctx.H, 3, 0.64, 0.3, 0.7, 150, 300, ("#1d1638", "#07060f"), 0.15, 0.9)
        c.drawImage(city, -0.2 * ctx.W, 0)
        K.light_rays(c, ctx.W, ctx.H, t)
        K.bokeh(c, ctx.W, ctx.H, t)
        K.draw_road(c, ctx.W, ctx.H, 0.64, t)
        rain.draw(c, t)
        K.hero(c, ctx.W / 2, ctx.H * 0.9, 420, t=t)
        K.vignette(c, ctx.W, ctx.H)
        im = K.to_pil(s)
        im = K.bloom(im, 200, 0.8, 24)
        K.grain(im, 0.03, i)
    return (time.perf_counter() - t0) / frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    threads = os.cpu_count() or 1
    print(f"\nSystem: {platform.system()} {platform.release()} · Python {platform.python_version()} · "
          f"{threads} CPU threads · {ram_gb():.1f} GB RAM")
    gpu = nvidia()
    print(f"NVIDIA GPU: {gpu or 'none detected'}")

    print("\nTools")
    problems = []
    for exe in ("ffmpeg", "ffprobe"):
        p = shutil.which(exe)
        line(OK if p else BAD, exe, p or "MISSING — install ffmpeg and add it to PATH")
        if not p: problems.append(exe)
    for mod, need, hint in (("numpy", True, "pip install numpy"), ("PIL", True, "pip install pillow"),
                            ("skia", True, "pip install skia-python"), ("scipy", False, "pip install scipy (faster audio)"),
                            ("cv2", False, "pip install opencv-python-headless (≈3x faster post effects)"),
                            ("glfw", False, "pip install glfw (needed for --gpu drawing)"),
                            ("pyttsx3", False, "pip install pyttsx3 (Windows/macOS offline voice)")):
        try:
            m = importlib.import_module(mod)
            line(OK, mod, getattr(m, "__version__", ""))
        except ImportError:
            line(BAD if need else WARN, mod, hint)
            if need: problems.append(mod)
    tts = [n for n, ok in (("ElevenLabs (API key set)", bool(os.environ.get("ELEVENLABS_API_KEY"))),
                           ("festival", bool(shutil.which("text2wave"))), ("espeak-ng", bool(shutil.which("espeak-ng"))))
           if ok]
    try:
        import pyttsx3  # noqa
        tts.append("system voice (pyttsx3)")
    except ImportError:
        pass
    line(OK if tts else WARN, "voice engines", ", ".join(tts) or "none — put recordings in voice/<shot>.wav")
    import render
    line(OK, "font", render.find_font("Inter:style=ExtraBold") or "default")
    bl = shutil.which("blender")
    try:
        import bpy  # noqa
        line(OK, "Blender (bpy module)", f"{bpy.app.version_string} — 3D hero sprites")
    except ImportError:
        line(OK if bl else WARN, "Blender", bl or "pip install bpy (or install Blender) — needed only to build 3D hero sprites")

    if problems:
        print(f"\n{BAD} Fix the missing items above first: {', '.join(problems)}"); return 1

    print("\nVideo encoders (real test encode)")
    encs = {}
    for name in ["x264"] + render.HW_ORDER:
        encs[name] = render.encoder_works(name)
        line(OK if encs[name] else "·", name, "works" if encs[name] else "not available")
    if gpu and not encs.get("nvenc"):
        print("    note: this NVIDIA chip has no NVENC encoder (e.g. MX150/MX250/MX330/MX450/GT 1030) — that's expected.")

    import anim_kit as K
    gpu_draw = K.init_gpu()
    line(OK if gpu_draw else "·", "skia GPU drawing (--gpu)", "available" if gpu_draw else "not available (CPU drawing)")

    profile = {"jobs": threads, "encoder": "auto", "gpu": False}
    if not a.quick:
        print("\nBenchmark (1080p frame with rain, city, hero, rays, bloom)")
        K._GR = None
        cpu_ms = bench_scene(K.SceneContext(1920, 1080)) * 1000
        line(OK, "CPU, 1 process", f"{cpu_ms:.0f} ms/frame")
        best_ms, best = cpu_ms / max(1, threads * 0.75), "cpu"
        gpu_ms = None
        if gpu_draw:
            K.init_gpu()
            try:
                gpu_ms = bench_scene(K.SceneContext(1920, 1080, gpu=True)) * 1000
                line(OK, "GPU drawing, 1 process", f"{gpu_ms:.0f} ms/frame")
                # one GPU shared by 2 processes; CPU parallel scales with threads
                if gpu_ms / 1.6 < best_ms:
                    best_ms, best = gpu_ms / 1.6, "gpu"
            except Exception as e:
                line(WARN, "GPU drawing", f"failed during benchmark ({e}) — staying on CPU")
        profile.update({"gpu": best == "gpu", "jobs": 2 if best == "gpu" else threads})
        fps_eff = 1000 / best_ms
        print(f"\nEstimated full-quality render speed: {fps_eff:.1f} frames/s "
              f"({'GPU drawing' if best == 'gpu' else f'{threads} CPU processes'})")
        for label, sec in (("20 s video", 20), ("60 s Short", 60), ("10 min video", 600)):
            full = sec * 30 / fps_eff
            prev = sec * 15 / (fps_eff * 3.5)
            print(f"  {label:<13} full ≈ {full/60:5.1f} min   --preview ≈ {prev/60:5.1f} min")
    PROFILE.write_text(json.dumps(profile, indent=2))
    print(f"\nSaved {PROFILE.name}: {profile}")
    print("render.py now uses these defaults; override with --jobs / --gpu / --encoder.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
