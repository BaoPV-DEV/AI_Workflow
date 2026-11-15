from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("Chưa cài ffmpeg (Windows: winget install Gyan.FFmpeg)")
    return exe


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout)[-1500:]
        raise RuntimeError(f"Lệnh lỗi: {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    return r


def probe_duration(path: Path) -> float:
    exe = shutil.which("ffprobe") or "ffprobe"
    r = run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "json", path])
    return float(json.loads(r.stdout)["format"]["duration"])


@lru_cache
def encoders() -> str:
    try:
        return run([ffmpeg(), "-hide_banner", "-encoders"]).stdout
    except Exception:
        return ""


@lru_cache
def pick_encoder(pref: str = "auto") -> str:
    if pref != "auto":
        return pref
    for enc in ("h264_nvenc", "h264_qsv"):
        if enc in encoders() and _encoder_works(enc):
            return enc
    return "libx264"


def _encoder_works(enc: str) -> bool:
    """NVENC có trong ffmpeg chưa chắc driver hỗ trợ: thử mã hoá 1 khung hình."""
    try:
        run([ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1",
             "-c:v", enc, "-f", "null", "-"], timeout=30)
        return True
    except Exception:
        return False


def encode_args(enc: str, crf: int = 20, preset: str = "veryfast") -> list[str]:
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(crf), "-pix_fmt", "yuv420p"]
    if enc == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf), "-pix_fmt", "nv12"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
