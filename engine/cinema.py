"""Chế độ Điện ảnh: chạy nguyên pipeline của repo BaoPV-DEV/Skills (skill ai-video-production-pipeline) trong AI Workflow.

Claude Code viết storyboard.json + scenes.py (animation từng khung bằng anim_kit, nhân vật 3D Blender) theo đúng skill gốc;
AI Workflow tạo giọng đọc (edge-tts, miễn phí, đa ngôn ngữ) thành voice/<shot>.wav; render.py của skill dựng video
(hạt, parallax, ánh sáng, hậu kỳ, nhạc + SFX tự tổng hợp) và xuất qa.json.

Dự án nằm ở workspace/_cinema/<slug>/ (giống videos/<slug>/ của repo gốc).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from . import char3d, config

SKILL = config.ROOT / ".claude" / "skills" / "ai-video-production-pipeline"
RENDER = SKILL / "scripts" / "render.py"
DEPS = ["numpy", "pillow", "skia-python", "scipy", "opencv-python-headless"]


def root() -> Path:
    d = config.workspace() / "_cinema"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_dir(slug: str) -> Path:
    return root() / Path(slug).name


def _py() -> str:
    from .winhide import console_python
    return console_python()


# ---------------------------------------------------------------- cài đặt
def deps_ok() -> bool:
    try:
        r = subprocess.run([_py(), "-c", "import skia, numpy, PIL"], capture_output=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def ensure_shared() -> Path:
    """videos/_shared/cast_sprites của skill gốc → trỏ về workspace/_cast3d (nhân vật 3D đã render trong Studio)."""
    shared = root() / "_shared"
    shared.mkdir(exist_ok=True)
    link, target = shared / "cast_sprites", char3d.out_dir()
    target.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        return link
    if sys.platform == "win32":  # junction: không cần quyền admin như symlink
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    else:
        os.symlink(target, link, target_is_directory=True)
    return link


def setup() -> dict:
    if not deps_ok():
        print("⬇ Cài thư viện dựng hình (skia-python, numpy, opencv, scipy)…", flush=True)
        r = subprocess.run([_py(), "-m", "pip", "install", "--upgrade", *DEPS])
        if r.returncode:
            raise RuntimeError("pip install thất bại (xem nhật ký ở trên)")
    if not shutil.which("ffprobe"):
        print("⚠ Không thấy ffprobe trong PATH: render.py cần ffmpeg bản đầy đủ (có ffprobe).", flush=True)
    ensure_shared()
    print("✔ Chế độ Điện ảnh sẵn sàng", flush=True)
    return status()


def status() -> dict:
    return {"ready": deps_ok() and bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")),
            "ffprobe": bool(shutil.which("ffprobe")), "projects": projects(),
            "characters": [c for c in char3d.characters() if c["sets"]]}


# ---------------------------------------------------------------- dự án
def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()[:40].strip("-")
    return s or f"video-{int(time.time())}"


def _sb(d: Path) -> dict:
    try:
        return json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def projects() -> list[dict]:
    res = []
    for d in sorted(root().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        sb, out = _sb(d), d / "out"
        vids = sorted((p.name for p in out.glob("*.mp4") if not p.name.startswith("picture") and ".part." not in p.name),
                      key=lambda n: "preview" in n) if out.exists() else []
        stills = sorted(p.name for p in out.glob("still_*.png")) if out.exists() else []
        qa = {}
        if (out / "qa.json").exists():
            try:
                qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            except Exception:
                pass
        files = {n: (d / n).exists() for n in ("storyboard.md", "audit.md", "package.md", "qa-report.md", "scenes.py")}
        res.append({"slug": d.name, "title": sb.get("title") or d.name, "seconds": sb.get("target_seconds"),
                    "profile": sb.get("profile"), "shots": len(sb.get("shots", [])), "has_storyboard": bool(sb),
                    "voiced": (d / "voice").exists() and any((d / "voice").glob("*.wav")),
                    "videos": vids, "stills": stills[:24], "qa": {k: qa.get(k) for k in ("duration_s", "duration_error_pct",
                    "wpm_while_speaking", "pattern_interrupts", "integrated_lufs", "size_mb") if k in qa}
                    | {"missing_assets": len(qa.get("missing_assets") or [])},
                    "files": files, "mtime": int(d.stat().st_mtime)})
    return res


def delete(slug: str) -> None:
    d = project_dir(slug)
    trash = config.workspace() / "_trash" / f"cinema_{d.name}_{int(time.time())}"
    trash.parent.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash))


# ---------------------------------------------------------------- Claude viết theo skill gốc
def _prompt(d: Path, topic: str, seconds: int, lang: str, aspect: str, cid: str, extra: str) -> str:
    W, H = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    sets = [s["key"] for s in char3d.sprite_sets(cid)] if cid else []
    cast = (f"""
NHÂN VẬT: dùng nhân vật 3D đã render sẵn '{cid}' (KHÔNG thiết kế hay render nhân vật mới, KHÔNG chạy make_character.py).
- scenes.py: `_ak.SPRITE_ROOT = Path(__file__).resolve().parent.parent / "_shared" / "cast_sprites"` (thư mục này đã có sẵn).
- Bộ ảnh động có sẵn (tên đầy đủ "{cid}/<bộ>"): {", ".join(sets)}. Chỉ dùng đúng các bộ này; quay mặt bên kia thì `flip=True`.
- Đèn của sprite là 'day' (hoặc như tên bộ): chỉnh màu cảnh cho hợp, không đòi bộ đèn khác.""" if sets else """
NHÂN VẬT: chưa có nhân vật 3D render sẵn → dùng hero() vector của anim_kit hoặc cảnh không người.""")
    return f"""Dùng skill ai-video-production-pipeline (đọc .claude/skills/ai-video-production-pipeline/SKILL.md và các file references nó chỉ tới) ở CHẾ ĐỘ AUTO: không dừng ở checkpoint, tự chọn phương án tốt nhất và ghi lý do vào file của bước đó.

CHỦ ĐỀ: {topic}
THỜI LƯỢNG MỤC TIÊU: {seconds} giây · KHUNG: {aspect} ({W}x{H}, 30 fps)
NGÔN NGỮ lời thoại, chữ trên màn hình, phụ đề và gói SEO: {lang} (bỏ qua mặc định tiếng Anh của skill).
THƯ MỤC DỰ ÁN (thay cho videos/<slug>/): {d.as_posix()}
{f"YÊU CẦU THÊM: {extra}" if extra else ""}
{cast}

PHẠM VI: làm Bước 2 → 5 (không có kênh mẫu thì bỏ Bước 1, ghi project-brief.md ngắn): ideas.md → outline.md → storyboard.md + storyboard.json + scenes.py (animation từng khung bằng anim_kit, mục 2b của render-pipeline.md; KHÔNG dùng ảnh AI/ảnh tĩnh) → audit.md (kiểm duyệt chính sách, tự viết lại) → package.md (SEO).
- storyboard.json: "slug": "{d.name}", "format": {{"width": {W}, "height": {H}, "fps": 30}}, "voice": {{"engine": "file", "target_wpm": null}} — giọng đọc do AI Workflow tạo sẵn thành voice/<shot_id>.wav, KHÔNG tự tạo giọng.
- Kiểm tra bố cục (sau khi có storyboard.json + scenes.py): tạo giọng bằng `{Path(_py()).as_posix()} {(config.ROOT / "vf.py").as_posix()} cinema voice {d.name}`, rồi trong thư mục dự án chạy `{Path(_py()).as_posix()} {RENDER.as_posix()} storyboard.json --stills`; mở vài ảnh out/still_*.png xem chữ/phụ đề/vùng an toàn, sửa scenes.py. Sửa lời thoại thì chạy lại lệnh tạo giọng.
- KHÔNG render video đầy đủ (Studio tự render sau). Không sửa file ngoài thư mục dự án.
Xong in một dòng: DONE {d.name}"""


def write(topic: str, seconds: int = 60, lang: str = "vi", aspect: str = "16:9", cid: str = "", extra: str = "") -> str:
    """Claude Code chạy skill gốc → storyboard; rồi tạo giọng và ảnh xem thử. Trả về slug."""
    from .agent.llm import backend, run_cli
    if backend() != "cli":
        raise RuntimeError("Chế độ Điện ảnh cần Claude Code (AI: Claude Code trong Cài đặt) vì Claude phải tự viết và chạy code cảnh.")
    ensure_shared()
    slug = slugify(topic)
    d = project_dir(slug)
    if d.exists() and (d / "storyboard.json").exists():
        slug = f"{slug}-{time.strftime('%H%M')}"
        d = project_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / "brief.json").write_text(json.dumps({"topic": topic, "seconds": seconds, "lang": lang, "aspect": aspect,
                                              "char3d": cid, "extra": extra}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✍ Claude đang làm kịch bản + storyboard + code cảnh theo skill gốc (thường 10–30 phút)…", flush=True)
    py = Path(_py()).as_posix()
    tools = ",".join(["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite",
                      f"Bash({py}:*)", f"Bash(cd {d.as_posix()}:*)", "Bash(python:*)", "Bash(python3:*)",
                      "Bash(ffmpeg:*)", "Bash(ffprobe:*)", "Bash(ls:*)", "Bash(mkdir:*)"])
    out = run_cli(_prompt(d, topic, seconds, lang, aspect, cid, extra), role="cinema", tools=tools,
                  permission="acceptEdits", timeout=60 * 60)
    if not (d / "storyboard.json").exists():
        raise RuntimeError(f"Claude chưa tạo được storyboard.json. Trả lời cuối: {str(out.get('result'))[-400:]}")
    print("✔ Đã có storyboard. Tạo giọng đọc…", flush=True)
    voices(slug)
    render(slug, stills=True)
    return slug


# ---------------------------------------------------------------- giọng đọc (AI Workflow)
def voices(slug: str) -> int:
    """voice/<shot_id>.wav bằng edge-tts (fallback gTTS) theo ngôn ngữ dự án; shot đổi lời mới tạo lại."""
    from .tts import synth
    d = project_dir(slug)
    sb = _sb(d)
    brief = json.loads((d / "brief.json").read_text(encoding="utf-8")) if (d / "brief.json").exists() else {}
    lang = brief.get("lang") or sb.get("lang") or "vi"
    t = config.settings().get("tts", {})
    vdir = d / "voice"
    vdir.mkdir(exist_ok=True)
    idx_f = vdir / ".hash.json"
    idx = json.loads(idx_f.read_text(encoding="utf-8")) if idx_f.exists() else {}
    n = 0
    for s in sb.get("shots", []):
        text, sid = (s.get("vo") or "").strip(), s["id"]
        wav = vdir / f"{sid}.wav"
        if not text:
            wav.unlink(missing_ok=True)
            continue
        h = hashlib.sha1(f"{text}|{lang}|{t.get('engine')}|{config.default_voice(lang)}".encode()).hexdigest()[:12]
        if wav.exists() and idx.get(sid) == h:
            continue
        synth(text, wav, t.get("engine", "auto"), config.default_voice(lang), t.get("rate", "+0%"), t.get("piper_model", ""), lang)
        idx[sid] = h
        n += 1
        print(f"  🎙 {sid}: {text[:60]}", flush=True)
    idx_f.write_text(json.dumps(idx), encoding="utf-8")
    print(f"✔ Giọng đọc: {n} shot mới", flush=True)
    return n


# ---------------------------------------------------------------- dựng (render.py của skill)
def render(slug: str, stills: bool = False, preview: bool = False, shots: str = "") -> Path:
    d = project_dir(slug)
    if not (d / "storyboard.json").exists():
        raise FileNotFoundError(f"Không có storyboard.json trong {d}")
    voices(slug)
    ensure_shared()
    cmd = [_py(), str(RENDER), "storyboard.json", "--jobs", str(char3d.threads())]
    cmd += ["--stills"] if stills else []
    cmd += ["--preview"] if preview else []
    cmd += ["--shots", shots] if shots else []
    print(f"🎬 {'Ảnh xem thử' if stills else 'Dựng video'} · {char3d.threads()} luồng CPU, ưu tiên thấp", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.Popen(cmd, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env=env, **char3d._low_priority())
    for line in p.stdout:
        print(line.rstrip(), flush=True)
    if p.wait():
        raise RuntimeError(f"render.py lỗi (mã {p.returncode})")
    out = d / "out"
    return out
