"""Quay template HTML/CSS/SVG/GSAP thành video bằng Playwright, từng khung hình (tất định).

Hợp đồng template: nạp ../_lib/runtime.js, đăng ký VF.scene({setup(input), draw(t)}).
Animation CSS / Web Animations / GSAP được runtime tua đúng thời điểm, nên không bị giật
dù máy yếu (không quay thời gian thực).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .. import config
from ..util import encode_args, ffmpeg
from .base import Adapter, Job, register

_PW = None
_BROWSER = None
LIB = config.TEMPLATES / "html_scenes" / "_lib"


def browser():
    global _PW, _BROWSER
    if _BROWSER:
        return _BROWSER
    from playwright.sync_api import sync_playwright

    _PW = sync_playwright().start()
    pref = config.settings().get("visual", {}).get("browser_channel")
    tries = [pref] if pref else [None, "msedge", "chrome"]
    last = None
    for ch in tries:
        try:
            _BROWSER = _PW.chromium.launch(channel=ch, args=["--disable-gpu-vsync", "--force-color-profile=srgb"]) \
                if ch else _PW.chromium.launch(args=["--force-color-profile=srgb"])
            return _BROWSER
        except Exception as e:  # thử trình duyệt tiếp theo
            last = e
    raise RuntimeError(f"Không mở được trình duyệt. Chạy: python -m playwright install chromium\n{last}")


def close():
    global _PW, _BROWSER
    if _BROWSER:
        _BROWSER.close()
        _PW.stop()
    _PW = _BROWSER = None


def template_path(job: Job) -> Path:
    if job.scene.get("visual_type") == "svg_graphic":
        return config.TEMPLATES / "html_scenes" / "svg_wrapper.html"
    return config.TEMPLATES / "html_scenes" / f"{job.scene['template_name']}.html"


def scene_input(job: Job) -> dict:
    s = job.scene
    props = dict(s.get("props") or {})
    if s.get("visual_type") == "svg_graphic":
        props["svg"] = s.get("svg_code", "")
    return {
        "props": props, "style": job.style, "cast": job.cast, "acting": s.get("acting_resolved", []),
        "words": s.get("word_timings", []), "duration": job.duration, "width": job.width,
        "height": job.height, "camera": s.get("camera", "none"), "text": s.get("voice_text", ""),
        "assets": (job.project_dir / "assets").as_uri() + "/",
        "actions": config.library("actions")["actions"],
        "captions": s.get("_captions"),
    }


def open_page(job: Job):
    b = browser()
    scale = 0.5 if job.draft else 1
    page = b.new_page(viewport={"width": job.width, "height": job.height}, device_scale_factor=scale)
    page.add_init_script(f"window.VF_INPUT = {json.dumps(scene_input(job), ensure_ascii=False)};")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(template_path(job).as_uri())
    page.wait_for_function("window.__vfReady === true", timeout=20000)
    if errors:
        raise RuntimeError(f"Template lỗi JS: {errors[0]}")
    return page


def still(job: Job, t: float, out: Path) -> Path:
    page = open_page(job)
    try:
        page.evaluate(f"window.__vfSeek({t})")
        page.screenshot(path=str(out), type="jpeg", quality=85)
    finally:
        page.close()
    return out


@register
class HtmlAdapter(Adapter):
    visual_types = ("html_animation", "svg_graphic")

    def fingerprint(self, job: Job) -> list:
        return [template_path(job), LIB / "runtime.js", LIB / "stickman.js", job.style, job.cast]

    def render(self, job: Job) -> Path:
        fps = job.fps if not job.draft else max(12, job.fps // 2)
        n = max(1, round(job.duration * fps))
        page = open_page(job)
        w, h = (job.width // 2, job.height // 2) if job.draft else (job.width, job.height)
        cmd = [ffmpeg(), "-y", "-v", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(fps),
               "-i", "-", "-vf", f"scale={w}:{h}:flags=lanczos,format=yuv420p",
               *encode_args(job.encoder, job.crf, job.preset), "-r", str(fps), str(job.out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(n):
                page.evaluate(f"window.__vfSeek({i / fps})")
                proc.stdin.write(page.screenshot(type="jpeg", quality=92))
        finally:
            page.close()
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="ignore")
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg lỗi khi quay cảnh: {err[-800:]}")
        return job.out

