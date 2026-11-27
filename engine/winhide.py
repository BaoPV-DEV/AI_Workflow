"""Chạy Studio không có cửa sổ terminal trên Windows (mở bằng Studio.vbs → pythonw.exe).

- Ghi log ra .cache/studio.log thay cho console (pythonw không có stdout).
- Mọi tiến trình con (python vf.py voice/render, ffmpeg, claude CLI…) chạy với CREATE_NO_WINDOW
  để không bật cửa sổ đen giữa chừng.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
LOG = Path(__file__).resolve().parent.parent / ".cache" / "studio.log"
_NO_CONSOLE = False  # True = tiến trình Studio chính chạy bằng pythonw (không ai thấy stdout)


def hidden() -> bool:
    return sys.platform == "win32" and (sys.stdout is None or os.environ.get("VF_HIDDEN") == "1")


def setup() -> None:
    if not hidden():
        return
    os.environ["VF_HIDDEN"] = "1"  # tiến trình con thừa kế
    global _NO_CONSOLE
    if sys.stdout is None:  # pythonw: không có console → ghi log ra file
        _NO_CONSOLE = True
        LOG.parent.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            LOG.unlink()
        f = open(LOG, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    orig = subprocess.Popen.__init__

    def _init(self, *a, **k):
        k["creationflags"] = k.get("creationflags", 0) | CREATE_NO_WINDOW
        orig(self, *a, **k)

    subprocess.Popen.__init__ = _init


def console_python() -> str:
    """python.exe cạnh pythonw.exe (để tác vụ con có stdout bình thường; cửa sổ đã bị ẩn bởi CREATE_NO_WINDOW)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


def alert(msg: str) -> None:
    """Báo lỗi bằng hộp thoại khi không có terminal để in ra."""
    if _NO_CONSOLE:  # tác vụ con đã có log hiện trong Studio, không bật hộp thoại trùng
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f"{msg}\n\nNhật ký: {LOG}", "AI Workflow Studio", 0x10)
        except Exception:
            pass
