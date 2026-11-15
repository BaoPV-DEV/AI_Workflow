from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


@lru_cache
def ffmpeg() -> str:
    """ffmpeg trong PATH, nếu không có thì dùng bản đi kèm gói imageio-ffmpeg (tự tải qua pip)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("Không tìm thấy ffmpeg. Chạy: pip install imageio-ffmpeg") from e


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout)[-1500:]
        raise RuntimeError(f"Lệnh lỗi: {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    return r


def probe_duration(path: Path) -> float:
    """Thời lượng file. WAV đọc trực tiếp; định dạng khác hỏi ffmpeg (không cần ffprobe)."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        import wave

        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise RuntimeError(f"Không đọc được thời lượng {path.name}")
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


@lru_cache
def has_filter(name: str) -> bool:
    try:
        out = run([ffmpeg(), "-hide_banner", "-filters"]).stdout
    except Exception:
        return False
    return any(len(l.split()) > 1 and l.split()[1] == name for l in out.splitlines())


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
