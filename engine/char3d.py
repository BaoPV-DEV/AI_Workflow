"""Nhân vật 3D bằng Blender (bộ hero3d từ repo BaoPV-DEV/Skills) cho AI Workflow.

Mỗi nhân vật: 1 file mô tả library/cast3d/<id>.json → render 1 lần ra ảnh động (PNG trong suốt) ở
workspace/_cast3d/<id>/<anim>_<view>_<light>/ → mọi video dùng lại, không render lại.
Trong manifest: "cast": {"An": {"model3d": "mia"}} → cảnh stickman_stage vẽ nhân vật 3D thay người que.

Blender cần Python 3.11 hoặc 3.13 (bpy không có bản cho 3.12), nên chạy trong môi trường riêng .venv3d.
"""
from __future__ import annotations

import json
import os
import re
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
PY_WIN = "3.13.13"  # bản Python tải về khi máy chưa có 3.11/3.13

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


FAST_GPU = re.compile(r"RTX|GTX 1[6-9]\d\d|GTX [2-9]\d\d\d|\bA\d{2,4}\b|Tesla|TITAN", re.I)


def fast_gpu(name: str | None = None) -> bool:
    """Card đủ mạnh để Blender render nhanh hơn CPU rõ rệt. MX/GT/GTX đời cũ: ngang CPU, driver cũ dễ lỗi → dùng CPU."""
    name = gpu() if name is None else name
    return bool(name and FAST_GPU.search(name))


CPU_LEVELS = {"nhe": "Nhẹ – một nửa số nhân, máy vẫn mượt", "vua": "Vừa – chừa 2 nhân cho bạn (mặc định)", "toi_da": "Tối đa – nhanh nhất, máy chậm"}


def cpu_level() -> str:
    v = _cfg().get("cpu", "vua")
    return v if v in CPU_LEVELS else "vua"


def threads() -> int:
    n = os.cpu_count() or 4
    return {"nhe": max(1, n // 2), "vua": max(1, n - 2), "toi_da": n}[cpu_level()]


def _low_priority() -> dict:
    """Tiến trình render nhường CPU cho ứng dụng bạn đang dùng (máy không bị đơ dù CPU cao)."""
    if WIN:
        return {"creationflags": 0x40 if cpu_level() == "nhe" else 0x4000}  # IDLE / BELOW_NORMAL_PRIORITY_CLASS
    return {"preexec_fn": lambda: os.nice(19 if cpu_level() == "nhe" else 10)}


PATCH_MARK = "# AI Workflow: CHAR_THREADS"


def patch_kit() -> None:
    """Thêm giới hạn số luồng CPU vào build_character.py (giữ lại sau mỗi lần vf skills-sync)."""
    f = KIT / "build_character.py"
    s = f.read_text(encoding="utf-8")
    if PATCH_MARK in s:
        return
    anchor = '    scene.render.film_transparent = True\n'
    if anchor not in s:
        return
    s = s.replace(anchor, anchor + f'    if os.environ.get("CHAR_THREADS"):  {PATCH_MARK}\n'
                  '        scene.render.threads_mode = "FIXED"; scene.render.threads = max(1, int(os.environ["CHAR_THREADS"]))\n', 1)
    f.write_text(s, encoding="utf-8")


DEVICES = {"auto": "Tự động (card mạnh → card, còn lại → CPU)", "gpu": "Card rời NVIDIA (CPU rảnh hơn)", "cpu": "CPU"}


def device_choice() -> str:
    v = _cfg().get("device", "auto")
    return v if v in DEVICES else "auto"


def device() -> str:
    """Giá trị --device cho Blender: gpu | cpu."""
    c = device_choice()
    if c == "auto":
        return "gpu" if fast_gpu() else "cpu"
    return c


def gpu_check() -> dict:
    """Hỏi chính Blender xem card nào dùng được cho Cycles (CUDA/OptiX)."""
    py = blender_python()
    if not py:
        return {"ok": False, "devices": [], "msg": "Chưa cài Blender"}
    code = ("import bpy\np=bpy.context.preferences.addons['cycles'].preferences\nout=[]\n"
            "for b in ('OPTIX','CUDA','HIP','ONEAPI'):\n"
            "    try:\n        p.compute_device_type=b; p.get_devices()\n"
            "        out += [b+': '+d.name for d in p.devices if d.type!='CPU']\n    except Exception: pass\n"
            "print('DEVICES=' + '|'.join(dict.fromkeys(out)))")
    r = subprocess.run([py, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    line = next((l for l in r.stdout.splitlines() if l.startswith("DEVICES=")), "DEVICES=")
    devs = [d for d in line[8:].split("|") if d]
    g = gpu()
    msg = (f"Blender dùng được: {', '.join(devs)}" if devs else
           f"Blender không thấy card rời{f' ({g})' if g else ''}. Thường do driver NVIDIA quá cũ: cập nhật driver mới (nhánh 58x) rồi kiểm tra lại.")
    return {"ok": bool(devs), "devices": devs, "msg": msg}


def sec_per_frame() -> float:
    """Ước lượng ở chất lượng "chuẩn" (theo bảng đo của repo Skills: RTX 1-3s, CPU laptop/MX250 10-15s)."""
    if device() == "gpu":
        return 2.0 if fast_gpu() else 12.0  # MX/GT: tốc độ ngang CPU, nhưng CPU được rảnh
    n = os.cpu_count() or 4
    return 12.0 * n / threads()  # ít luồng hơn thì lâu hơn tương ứng


def status() -> dict:
    py, data, g = blender_python(), mpfb_data(), gpu()
    return {"ready": bool(py and data), "python": py, "mpfb": data, "gpu": g, "fast_gpu": fast_gpu(g), "device": device(),
            "cpu": cpu_level(), "cpu_levels": CPU_LEVELS, "threads": threads(), "cores": os.cpu_count(),
            "device_choice": device_choice(), "devices": DEVICES,
            "sec_per_frame": sec_per_frame(), "characters": characters()}


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
    _say(f"✔ Sẵn sàng. Card: {st['gpu'] or 'không có NVIDIA'} → Blender render bằng {'card đồ hoạ' if st['device'] != 'cpu' else 'CPU'}"
         f" (~{st['sec_per_frame']:.0f} giây/khung ở chất lượng chuẩn)")
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
    cmd = [py, str(KIT / "build_character.py"), "--char", str(tmp), "--data", data, "--out", str(out_dir()),
           "--device", device(), *args]
    patch_kit()
    env = {**os.environ, "CHAR_THREADS": str(threads())}
    dev = device()
    print(f"⚙ Thiết bị: {'card rời ' + (gpu() or '') if dev == 'gpu' else 'CPU'} · {threads()}/{os.cpu_count()} luồng CPU, ưu tiên thấp"
          " (đổi ở trang Nhân vật 3D)", flush=True)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                         env=env, **_low_priority())
    used_gpu = False
    for line in p.stdout:  # chỉ in dòng có ích (tiến độ từng khung), bỏ log nội bộ của Blender
        if line.startswith("Cycles GPU:"):
            used_gpu = True
            print("🟢 Đang render bằng card rời: " + line.split(":", 1)[1].strip(), flush=True)
        elif line.lstrip().startswith(("sheet ", spec["id"] + "/", spec["id"] + ":", "done", "Traceback", "Error", "ERROR")) or "Error" in line:
            if spec["id"] + ":" in line and dev == "gpu" and not used_gpu:
                print("⚠ Blender không dùng được card rời (driver NVIDIA cũ?) → đang render bằng CPU."
                      " Cập nhật driver rồi bấm 'Kiểm tra card rời' ở trang Nhân vật 3D.", flush=True)
            print(line.rstrip(), flush=True)
    if p.wait():
        raise RuntimeError(f"Blender lỗi (mã {p.returncode})")
    tmp.unlink(missing_ok=True)


def sheet(cid: str, quality: str = "nhap", force: bool = False) -> Path:
    """Bảng xem trước (trước, 3/4, nghiêng, sau, mặt) để duyệt trước khi render động tác."""
    s = load_spec(cid)
    q = QUALITY[quality]
    folder = out_dir() / s["id"] / "_sheet"
    views = [folder / f"{v}.png" for v in ("front", "front34", "side", "back", "face", "head_back")]
    fresh = all(f.exists() for f in views) and min(f.stat().st_mtime for f in views) > spec_path(cid).stat().st_mtime
    if force or not fresh:  # ảnh đã render sau lần sửa ngoại hình cuối thì chỉ ghép lại, khỏi chạy Blender
        _run_builder(s, ["--sheet", "--res", str(min(q["res"], 720)), "--samples", str(q["samples"])] + (["--fast"] if q["fast"] else []))
    # Ghép bảng bằng Python của Blender (.venv3d có sẵn Pillow), không bắt Studio phải cài thêm thư viện ảnh.
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); import make_character as mc; "
            "print(mc.make_sheet(__import__('pathlib').Path(sys.argv[2]), json.loads(open(sys.argv[3], encoding='utf-8').read())))")
    r = subprocess.run([blender_python(), "-c", code, str(KIT), str(folder), str(spec_path(cid))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"Ghép bảng nhân vật lỗi: {(r.stderr or r.stdout).strip().splitlines()[-1]}")
    out = Path(r.stdout.strip().splitlines()[-1])
    print(f"✔ Bảng nhân vật: {out}")
    return out


def plan(cid: str, profile: str = "co_ban", light: str = "day", only: str = "") -> list[list[str]]:
    if only:
        return [x.split(":") for x in only.split(",") if x]
    return [[a, v, light] for a, v in PROFILES[profile]]


def estimate(jobs: list, quality: str = "chuan") -> dict:
    n = sum(FRAMES.get(j[0], 16) for j in jobs)
    per = sec_per_frame() * {"nhap": 0.4, "chuan": 1.0, "cao": 1.6}[quality]
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


def apply_to_project(pid: str, cid: str) -> str:
    """Gán nhân vật 3D cho nhân vật chính của video (người xuất hiện nhiều nhất trong acting)."""
    from . import manifest
    from collections import Counter
    d, data = manifest.load(pid)
    cast = data.get("cast") or {}
    cnt = Counter(b.get("who") for s in data.get("scenes", []) for b in (s.get("acting") or []) if b.get("who"))
    main = (cnt.most_common(1)[0][0] if cnt else None) or next(iter(cast), None) or "hero"
    cast.setdefault(main, {})["model3d"] = cid
    data["cast"] = cast
    manifest.save(d, data)
    return main


def writer_note(cid: str) -> str:
    """Gợi ý cho Claude khi viết kịch bản có nhân vật 3D."""
    anims = sorted({x.split("_")[0] for x in next((c["sets"] for c in characters() if c["id"] == cid), [])})
    return (f"Nhân vật chính là nhân vật 3D người thật '{cid}' (chỉ hiện trong cảnh stickman_stage): dùng stickman_stage cho phần lớn"
            f" đoạn kể chuyện, 1 nhân vật chính xuyên suốt; ưu tiên các act tương ứng động tác đã có: {', '.join(anims) or 'idle, talk'}.")
