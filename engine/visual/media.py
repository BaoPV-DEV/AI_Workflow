"""Ảnh tĩnh (Ken Burns), clip có sẵn, nền màu – chỉ dùng ffmpeg."""
from __future__ import annotations

from pathlib import Path

from ..util import encode_args, ffmpeg, run
from .base import Adapter, Job, register


def asset(job: Job, src: str) -> Path:
    for base in (job.project_dir / "assets", job.project_dir, job.project_dir.parent / "_shared"):
        p = (base / src)
        if p.exists():
            return p
    raise FileNotFoundError(f"Không thấy '{src}' trong assets/ của project")


def _size(job: Job):
    return (job.width // 2, job.height // 2) if job.draft else (job.width, job.height)


@register
class ImageAdapter(Adapter):
    visual_types = ("image",)

    def fingerprint(self, job: Job) -> list:
        return [asset(job, job.scene["src"])]

    def render(self, job: Job) -> Path:
        return kenburns(job, asset(job, job.scene["src"]), job.scene.get("camera") or "zoom_in")


def kenburns(job: Job, img: Path, camera: str) -> Path:
    w, h = _size(job)
    n = max(1, round(job.duration * job.fps))
    z = {"zoom_in": f"1+0.12*on/{n}", "zoom_out": f"1.12-0.12*on/{n}"}.get(camera, "1.08")
    x = {"pan_left": f"(iw-iw/zoom)*(1-on/{n})", "pan_right": f"(iw-iw/zoom)*on/{n}"}.get(camera, "(iw-iw/zoom)/2")
    vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
          f"zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d={n}:s={w}x{h}:fps={job.fps},format=yuv420p")
    run([ffmpeg(), "-y", "-v", "error", "-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(n),
         *encode_args(job.encoder, job.crf, job.preset), job.out])
    return job.out


@register
class VideoAdapter(Adapter):
    visual_types = ("video",)

    def fingerprint(self, job: Job) -> list:
        return [asset(job, job.scene["src"])]

    def render(self, job: Job) -> Path:
        w, h = _size(job)
        src = asset(job, job.scene["src"])
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={job.fps},format=yuv420p"
        run([ffmpeg(), "-y", "-v", "error", "-stream_loop", "-1", "-i", src, "-t", f"{job.duration:.3f}",
             "-an", "-vf", vf, *encode_args(job.encoder, job.crf, job.preset), job.out])
        return job.out


@register
class ColorAdapter(Adapter):
    visual_types = ("color",)

    def render(self, job: Job) -> Path:
        w, h = _size(job)
        c = (job.scene.get("props") or {}).get("color") or job.style.get("bg", "#000000")
        run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
             f"color=c={c.replace('#', '0x')}:s={w}x{h}:r={job.fps}:d={job.duration:.3f}",
             *encode_args(job.encoder, job.crf, job.preset), job.out])
        return job.out
