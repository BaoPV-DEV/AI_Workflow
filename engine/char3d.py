"""Nhân vật 3D bằng Blender (bộ hero3d từ repo BaoPV-DEV/Skills) cho AI Workflow.

Mỗi nhân vật: 1 file mô tả library/cast3d/<id>.json → render 1 lần ra ảnh động (PNG trong suốt) ở
workspace/_cast3d/<id>/<anim>_<view>_<light>/ → mọi video dùng lại, không render lại.
Trong manifest: "cast": {"An": {"model3d": "mia"}} → cảnh stickman_stage vẽ nhân vật 3D thay người que.

Blender cần Python 3.11 hoặc 3.13 (bpy không có bản cho 3.12), nên chạy trong môi trường riêng .venv3d.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

from . import config

KIT = Path(__file__).resolve().parent / "hero3d"
SPECS = config.ROOT / "library" / "cast3d"
WIN = sys.platform == "win32"
VENV = config.ROOT / ".venv3d"
MPFB_REPO = "https://github.com/makehumancommunity/mpfb2"
PY_WIN = "3.13.9"  # bản Python tải về khi máy chưa có 3.11/3.13

# Bộ động tác render sẵn. Góc 3/4 cho cử chỉ (lật ngang khi quay mặt bên kia), góc nghiêng cho đi/chạy.
PROFILES = {
    "co_ban": [("idle", "front34"), ("talk", "front34"), ("walk", "side"), ("wave", "front34"),
               ("point", "front34"), ("celebrate", "front34")],
    "day_du": [("idle", "front34"), ("talk", "front34"), ("walk", "side"), ("run", "side"), ("wave", "front34"),
               ("point", "front34"), ("celebrate", "front34"), ("look_up", "front34"), ("arms_up", "front34"),
               ("push", "side"), ("crouch", "front34"), ("fall", "side")],
}
FRAMES = {"idle": 24, "walk": 24, "run": 16, "arms_up": 18, "push": 18, "fall": 24, "wave": 16, "point": 16,
          "look_up": 20, "crouch": 16, "celebrate": 16, "talk": 24}
QUALITY = {"nhap": {"res": 480, "samples": 10, "fast": True}, "chuan": {"res": 720, "samples": 24, "fast": False},
           "cao": {"res": 960, "samples": 32, "fast": False}}


def _cfg() -> dict:
    return config.settings().get("char3d") or {}


def out_dir() -> Path:
    return config.workspace() / "_cast3d"


def _venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if WIN else "bin/python")


@lru_cache(maxsize=4)
def _has_bpy(py: str) -> bool:
    try:
        return subprocess.run([py, "-c", "import bpy"], capture_output=True, timeout=120).returncode == 0
    except Exception:
        return False


def blender_python() -> str | None:
    for c in (_cfg().get("python"), os.environ.get("CHAR_BPY"), str(_venv_python())):
        if c and Path(c).exists() and _has_bpy(str(c)):
            return str(c)
    return None


def mpfb_data() -> str | None:
    for c in (_cfg().get("mpfb"), os.environ.get("MPFB_DATA"), str(config.ROOT / ".cache" / "mpfb2" / "src" / "mpfb" / "data")):
        if c and (Path(c) / "3dobjs" / "base.obj").exists():
            return str(c)
    return None


def gpu() -> str:
    exe = shutil.which("nvidia-smi")
    if exe:
        r = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    return ""


def status() -> dict:
    py, data, g = blender_python(), mpfb_data(), gpu()
    return {"ready": bool(py and data), "python": py, "mpfb": data, "gpu": g,
            "sec_per_frame": 2 if g else 12,  # ước lượng ở chất lượng "chuẩn" (theo bảng đo của repo Skills)
            "characters": characters()}


# ---------------------------------------------------------------- cài đặt (1 lần)
def _say(msg: str):
    print(msg, flush=True)


def _find_py311_313() -> str | None:
    cands = []
    if WIN:
        cands += [["py", "-3.13"], ["py", "-3.11"]]
        for v in ("313", "311"):
            cands.append([str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / f"Python{v}" / "python.exe")])
    cands += [["python3.13"], ["python3.11"]]
    if sys.version_info[:2] in ((3, 11), (3, 13)):
        cands.insert(0, [sys.executable])
    for c in cands:
        try:
            r = subprocess.run(c + ["-c", "import sys;print(sys.executable)"], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            continue
    return None


def _install_python_win() -> str:
    import urllib.request
    url = f"https://www.python.org/ftp/python/{PY_WIN}/python-{PY_WIN}-amd64.exe"
    exe = Path(os.environ.get("TEMP", ".")) / f"python-{PY_WIN}.exe"
    _say(f"⬇ Tải Python {PY_WIN} (~28 MB) cho Blender…")
    urllib.request.urlretrieve(url, exe)
    target = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python313"
    subprocess.run([str(exe), "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0", "Include_test=0",
                    f"TargetDir={target}"], check=True)
    return str(target / "python.exe")


def setup() -> dict:
    """Cài Blender (bpy) vào .venv3d và tải dữ liệu cơ thể MPFB2 (~75 MB). Chạy lại an toàn."""
    if not blender_python():
        base = _find_py311_313()
        if not base:
            if not WIN:
                raise RuntimeError("Cần Python 3.11 hoặc 3.13 để cài Blender (bpy). Cài rồi chạy lại.")
            base = _install_python_win()
        _say(f"🐍 Dùng {base} cho Blender")
        if not _venv_python().exists():
            subprocess.run([base, "-m", "venv", str(VENV)], check=True)
        _say("⬇ Cài Blender (pip install bpy, ~400 MB, có thể mất 5-15 phút)…")
        r = subprocess.run([str(_venv_python()), "-m", "pip", "install", "--upgrade", "bpy", "numpy", "pillow"])
        if r.returncode:
            raise RuntimeError("pip install bpy thất bại (xem nhật ký ở trên)")
        _has_bpy.cache_clear()
    if not mpfb_data():
        dst = config.ROOT / ".cache" / "mpfb2"
        if not shutil.which("git"):
            raise RuntimeError("Cần git để tải dữ liệu cơ thể MPFB2 (https://git-scm.com)")
        _say("⬇ Tải dữ liệu cơ thể MakeHuman/MPFB2 (CC0, ~75 MB)…")
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", MPFB_REPO, str(dst)], check=True)
        subprocess.run(["git", "-C", str(dst), "sparse-checkout", "set", "src/mpfb/data"], check=True)
    st = status()
    _say(f"✔ Sẵn sàng. Card đồ hoạ: {st['gpu'] or 'không có NVIDIA → render bằng CPU (chậm hơn)'}")
    return st


# ---------------------------------------------------------------- nhân vật
def spec_path(cid: str) -> Path:
    return SPECS / f"{Path(cid).name}.json"


def load_spec(cid: str) -> dict:
    f = spec_path(cid)
    if not f.exists():
        raise FileNotFoundError(f"Chưa có nhân vật 3D '{cid}'. Xem: vf char3d list")
    return json.loads(f.read_text(encoding="utf-8"))


def characters() -> list[dict]:
    res = []
    for f in sorted(SPECS.glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        d = out_dir() / s["id"]
        sheet = d / "sheet.png"
        res.append({"id": s["id"], "name": s.get("name", s["id"]), "role": s.get("role", ""),
                    "sheet": f"/files/_cast3d/{s['id']}/sheet.png?{int(sheet.stat().st_mtime)}" if sheet.exists() else "",
                    "sets": [m["key"] for m in sprite_sets(s["id"])]})
    return res


def new(cid: str, base: str = "mia", **changes) -> dict:
    """Tạo nhân vật mới từ một mẫu có sẵn (đổi id/tên; sửa chi tiết trong file JSON)."""
    import re
    cid = re.sub(r"[^a-z0-9_]", "_", cid.lower()).strip("_")
    if spec_path(cid).exists():
        raise FileExistsError(f"Đã có nhân vật '{cid}'")
    s = load_spec(base)
    s.update({"id": cid, "name": changes.get("name") or cid.replace("_", " ").title()}, **{k: v for k, v in changes.items() if v and k != "name"})
    spec_path(cid).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def _run_builder(spec: dict, args: list[str]) -> None:
    py, data = blender_python(), mpfb_data()
    if not (py and data):
        raise RuntimeError("Chưa cài Blender cho nhân vật 3D. Chạy: vf char3d setup (hoặc Studio → Công cụ → Nhân vật 3D → Cài đặt)")
    tmp = out_dir() / f"_{spec['id']}.spec.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    cmd = [py, str(KIT / "build_character.py"), "--char", str(tmp), "--data", data, "--out", str(out_dir()), *args]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:  # chỉ in dòng có ích (tiến độ từng khung), bỏ log nội bộ của Blender
        if line.lstrip().startswith(("sheet ", spec["id"] + "/", spec["id"] + ":", "done", "Traceback", "Error", "ERROR")) or "Error" in line:
            print(line.rstrip(), flush=True)
    if p.wait():
        raise RuntimeError(f"Blender lỗi (mã {p.returncode})")
    tmp.unlink(missing_ok=True)


def sheet(cid: str, quality: str = "nhap") -> Path:
    """Bảng xem trước (trước, 3/4, nghiêng, sau, mặt) để duyệt trước khi render động tác."""
    import importlib.util
    s = load_spec(cid)
    q = QUALITY[quality]
    _run_builder(s, ["--sheet", "--res", str(min(q["res"], 720)), "--samples", str(q["samples"])] + (["--fast"] if q["fast"] else []))
    spec_ = importlib.util.spec_from_file_location("make_character", KIT / "make_character.py")
    mc = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mc)
    out = mc.make_sheet(out_dir() / s["id"] / "_sheet", s)
    print(f"✔ Bảng nhân vật: {out}")
    return out


def plan(cid: str, profile: str = "co_ban", light: str = "day", only: str = "") -> list[list[str]]:
    if only:
        return [x.split(":") for x in only.split(",") if x]
    return [[a, v, light] for a, v in PROFILES[profile]]


def estimate(jobs: list, quality: str = "chuan") -> dict:
    n = sum(FRAMES.get(j[0], 16) for j in jobs)
    per = (2 if gpu() else 12) * {"nhap": 0.25, "chuan": 0.6, "cao": 1.0}[quality]
    return {"frames": n, "minutes": round(n * per / 60, 1)}


def sprites(cid: str, profile: str = "co_ban", light: str = "day", quality: str = "chuan", only: str = "") -> list[str]:
    """Render ảnh động cho nhân vật (1 lần; video sau dùng lại). Bộ đã có thì bỏ qua."""
    s = load_spec(cid)
    jobs = plan(cid, profile, light, only)
    have = {m["key"] for m in sprite_sets(cid)}
    todo = [j for j in jobs if "_".join(j) not in have]
    if not todo:
        print("✔ Đã đủ ảnh động, không cần render thêm.")
        return []
    q = QUALITY[quality]
    est = estimate(todo, quality)
    print(f"🎬 Render {len(todo)} động tác · {est['frames']} khung · ước tính ~{est['minutes']} phút", flush=True)
    t0 = time.time()
    _run_builder(s, ["--only", ",".join(":".join(j) for j in todo), "--res", str(q["res"]), "--samples", str(q["samples"])]
                 + (["--fast"] if q["fast"] else []))
    print(f"✔ Xong sau {round((time.time() - t0) / 60, 1)} phút")
    return ["_".join(j) for j in todo]


def sprite_sets(cid: str) -> list[dict]:
    d = out_dir() / Path(cid).name
    res = []
    if not d.exists():
        return res
    for m in sorted(d.glob("*_*_*/meta.json")):
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            continue
        n = len(list(m.parent.glob("[0-9]*.png")))
        if not n:
            continue
        res.append({"key": m.parent.name, "anim": meta["anim"], "view": meta["view"], "light": meta["light"],
                    "frames": min(n, meta.get("frames", n)), "fps": meta.get("fps", 12), "loop": meta.get("loop", True),
                    "size": meta["size"], "height_m": meta.get("height_m", 1.75), "ortho": meta.get("ortho", 2.6),
                    "feet": meta.get("feet", []), "head": meta.get("head", []),
                    "base": m.parent.resolve().as_uri() + "/", "mtime": int(m.stat().st_mtime)})
    return res


def scene_info(cast: dict) -> dict:
    """input.char3d cho template: {tên trong cast: {sets: […]}} với nhân vật có model3d."""
    return {n: {"sets": sprite_sets(c["model3d"])} for n, c in (cast or {}).items() if isinstance(c, dict) and c.get("model3d")}


def fingerprint(cast: dict) -> list:
    return [(n, [(s["key"], s["frames"], s["mtime"]) for s in v["sets"]]) for n, v in scene_info(cast).items()]
