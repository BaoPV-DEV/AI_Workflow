"""Web Studio local – chỉ dùng thư viện chuẩn Python. Chạy: python vf.py studio"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from engine import align, catalog, config, manifest, pipeline, studio_api

WEB = Path(__file__).parent
JOBS: dict[str, dict] = {}
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".wav": "audio/wav",
        ".mp3": "audio/mpeg", ".jpg": "image/jpeg", ".png": "image/png", ".srt": "text/plain; charset=utf-8"}
VERSION = "studio-3"

# ---- tự tắt khi không còn tab nào mở (đóng tab = đóng cổng)
TABS: dict[str, float] = {}
SEEN_TAB = False
LAST_BYE = 0.0
STALE = 90      # tab ẩn bị trình duyệt giảm tần suất hẹn giờ tới ~1 phút/lần, nên chờ 90 giây
GRACE = 8       # sau khi tab báo đóng: chờ chút để F5 / mở lại không bị tắt nhầm


def _busy() -> bool:
    return any(not j["done"] for j in JOBS.values())


def _watchdog():
    import time
    while True:
        time.sleep(2)
        if not config.settings().get("studio", {}).get("auto_exit", True) or not SEEN_TAB:
            continue
        now = time.time()
        for t, seen in list(TABS.items()):
            if now - seen > STALE:
                TABS.pop(t, None)
        if not TABS and now - LAST_BYE > GRACE and not _busy():
            print("👋 Đã đóng tab Studio: tắt máy chủ (mở lại bằng shortcut AI Workflow Studio).", flush=True)
            os._exit(0)


def run_job(args: list[str]) -> str:
    jid = uuid.uuid4().hex[:8]
    job = JOBS[jid] = {"cmd": " ".join(args), "log": "", "done": False, "code": None}

    def go():
        p = subprocess.Popen([sys.executable, "-u", str(config.ROOT / "vf.py"), *args], cwd=config.ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in p.stdout:
            job["log"] += line
        job["code"] = p.wait()
        job["done"] = True

    threading.Thread(target=go, daemon=True).start()
    return jid


MOODS = ["neutral", "happy", "sad", "surprised", "angry", "scared", "tired", "curious", "proud", "love", "laugh"]
MOVES = ["stay", "enter_left", "enter_right", "exit_left", "exit_right", "left", "center", "right"]
HOLDS = ["book", "phone", "coin", "money", "gift", "bulb", "sign", "laptop", "cup", "flag", "sword", "key", "star",
         "trophy", "magnifier", "map", "briefcase", "microphone", "pen", "pizza", "umbrella"]
EMOTES = ["!", "?", "❤", "💡", "💢", "💧", "zzz", "♪", "✨", "💦", "..."]


def status(d: Path, data: dict) -> dict:
    """Tiến độ của project: đã có giọng, ảnh xem trước, video chưa – để giao diện hiện đúng bước tiếp theo."""
    scenes = data.get("scenes", [])
    keys = [manifest.scene_key(s) for s in scenes]
    mt = lambda p: int(p.stat().st_mtime) if p.exists() else 0
    thumbs = {k: mt(d / "preview" / f"{k}.jpg") for k in keys if (d / "preview" / f"{k}.jpg").exists()}
    audio = {k: f"/files/{d.name}/assets/{k}.wav" for k, s in zip(keys, scenes)
             if s.get("duration") and (d / "assets" / f"{k}.wav").exists()}
    out = d / "out"
    videos = sorted((p.name for p in out.glob("*.mp4")), key=lambda n: "_draft" in n) if out.exists() else []
    return {"scenes": len(scenes), "voiced": len(audio), "thumbs": thumbs, "audio": audio,
            "videos": {v: mt(out / v) for v in videos}, "duration": round(sum(s.get("duration", 0) for s in scenes), 1),
            "mtime": mt(d / manifest.MANIFEST)}


def run_fn(fn, *args, **kw) -> str:
    """Chạy hàm Python trong luồng nền, lưu kết quả JSON vào job (cho ý tưởng AI…)."""
    jid = uuid.uuid4().hex[:8]
    job = JOBS[jid] = {"cmd": fn.__name__, "log": "", "done": False, "code": None, "result": None}

    def go():
        try:
            job["result"] = fn(*args, **kw)
            job["code"] = 0
        except Exception as e:
            job["log"] += f"✘ {e}\n"
            job["code"] = 1
        job["done"] = True

    threading.Thread(target=go, daemon=True).start()
    return jid


def brain() -> dict:
    import os
    from engine.agent.llm import backend, claude_cli
    return {"backend": backend(), "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")), "cli": claude_cli() or ""}


def scene_input(pid: str, sid: str) -> dict:
    """Giống engine.visual.html.scene_input nhưng dùng được cả khi chưa có giọng đọc."""
    d, data = manifest.load(pid)
    c = pipeline._ctx(data)
    s = next(x for x in data["scenes"] if str(x.get("scene_id")) == sid or manifest.scene_key(x) == sid)
    s = dict(s)
    if not s.get("duration"):
        n = len((s.get("voice_text") or "").split())
        s["duration"] = max(2.5, n / 2.5 + 0.3)
        s["word_timings"] = align.estimate(s.get("voice_text") or "", s["duration"] - 0.3)
    cast = pipeline.build_cast(data, c["style"])
    props = dict(s.get("props") or {})
    if s.get("visual_type") == "svg_graphic":
        props["svg"] = s.get("svg_code", "")
    tpl = "svg_wrapper" if s.get("visual_type") == "svg_graphic" else s.get("template_name")
    return {"template": tpl, "visual_type": s.get("visual_type"), "src": s.get("src"),
            "input": {"props": props, "style": c["style"], "cast": cast, "acting": pipeline.resolve_acting(s, cast),
                      "words": s.get("word_timings") or [], "duration": s["duration"], "width": c["w"], "height": c["h"],
                      "camera": s.get("camera", "none"), "text": s.get("voice_text", ""),
                      "assets": f"/files/{d.name}/assets/", "actions": config.library("actions")["actions"]}}


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _file(self, path: Path):
        if not path.is_file():
            return self._json({"error": "không có file"}, 404)
        data = path.read_bytes()
        rng = self.headers.get("Range")
        ctype = MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if rng and rng.startswith("bytes="):  # cho phép tua video
            a, _, b = rng[6:].partition("-")
            a, b = int(a or 0), int(b) if b else len(data) - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
            data = data[a:b + 1]
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _q(self) -> dict:
        from urllib.parse import parse_qs
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def do_DELETE(self):
        u = urlparse(self.path).path
        try:
            if u.startswith("/api/p/"):
                studio_api.delete_project(u.split("/")[3])
                return self._json({"ok": True})
            if u == "/api/series":
                return self._json(studio_api.series_delete(self._q().get("name", "")))
            if u == "/api/tools/files":
                studio_api.tools_delete(self._q().get("name", ""))
                return self._json({"ok": True})
            return self._json({"error": "không có"}, 404)
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _safe(base: Path, rel: str) -> Path:
        p = (base / unquote(rel)).resolve()
        if base.resolve() not in p.parents and p != base.resolve():
            raise PermissionError(rel)
        return p

    def do_GET(self):
        u = urlparse(self.path).path
        try:
            if u in ("/", "/index.html"):
                return self._file(WEB / "index.html")
            if u.startswith("/web/"):
                return self._file(self._safe(WEB, u[5:]))
            if u == "/api/version":
                return self._json({"version": VERSION, "root": str(config.ROOT)})
            if u == "/api/home":
                return self._json(studio_api.home())
            if u == "/api/library":
                return self._json(studio_api.library())
            if u == "/api/plan":
                return self._json(studio_api.plan_get())
            if u == "/api/research/saved":
                return self._json(studio_api.research_saved())
            if u == "/api/research/file":
                return self._json(studio_api.research_load(self._q().get("name", "")))
            if u == "/api/settings":
                return self._json({"values": studio_api.settings_get(), "brain": brain(), "styles": config.list_styles(),
                                   "root": str(config.ROOT), "workflows": studio_api.workflows()})
            if u == "/api/gpu":
                url = config.settings().get("visual", {}).get("comfyui_url", "")
                return self._json({"url": url, **studio_api.gpu_ping(url), "workflows": studio_api.workflows()})
            if u == "/api/tools/files":
                d = studio_api.tools_dir()
                return self._json([{"name": f.name, "size": f.stat().st_size, "mtime": int(f.stat().st_mtime)}
                                   for f in sorted(d.iterdir(), key=lambda f: -f.stat().st_mtime) if f.is_file()])
            if u.startswith("/api/p/") and u.endswith("/thumb"):
                at = self._q().get("at")
                t = studio_api.thumbnail(u.split("/")[3], float(at) if at else None)
                return self._file(t) if t else self._json({"error": "chưa có"}, 404)
            if u.startswith("/tpl/"):
                return self._file(self._safe(config.TEMPLATES / "html_scenes", u[5:]))
            if u.startswith("/files/"):
                return self._file(self._safe(config.workspace(), u[7:]))
            if u == "/api/meta":
                acts = config.library("actions")
                return self._json({"styles": {s: config.style(s) for s in config.list_styles()},
                                   "templates": catalog.templates(with_demo=True),
                                   "actions": {k: v.get("label", k) for k, v in acts["actions"].items()},
                                   "characters": config.library("characters")["characters"],
                                   "moods": MOODS, "moves": MOVES, "holds": HOLDS, "emotes": EMOTES,
                                   "voices": config.settings().get("tts", {}).get("voices", {}),
                                   "languages": config.library("languages")["languages"], "brain": brain(),
                                   "presets": config.library("presets")["presets"],
                                   "platforms": config.library("presets")["platforms"]})
            if u == "/api/projects":
                out = []
                for m in sorted(config.workspace().glob("*/" + manifest.MANIFEST), key=lambda p: -p.stat().st_mtime):
                    data = json.loads(m.read_text(encoding="utf-8"))
                    out.append({"id": m.parent.name, "title": data.get("title", ""), **status(m.parent, data)})
                return self._json(out)
            if u.startswith("/api/p/"):
                parts = u.split("/")[3:]
                if len(parts) == 1:
                    d, data = manifest.load(parts[0])
                    return self._json({"manifest": data, "errors": manifest.validate(data), "status": status(d, data)})
                if parts[1] == "scene":
                    return self._json(scene_input(parts[0], parts[2]))
            if u == "/api/jobs":
                return self._json({k: {kk: v[kk] for kk in ("cmd", "done", "code")} for k, v in JOBS.items()})
            if u.startswith("/api/jobs/"):
                return self._json(JOBS.get(u.split("/")[-1], {"error": "không có job"}))
            if u == "/api/trends":
                from urllib.parse import parse_qs
                from engine import trends
                q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                return self._json(trends.collect(q.get("geo", "VN"), q.get("lang", "vi"), fresh=q.get("fresh") == "1"))
            if u == "/api/brain":
                return self._json(brain())
            if u == "/api/usage":
                p = config.workspace() / ".usage.jsonl"
                rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
                return self._json({k: sum(r.get(k) or 0 for r in rows) for k in ("in", "out", "cache_read", "cache_write")} | {"calls": len(rows)})
            return self._json({"error": "không có"}, 404)
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_PUT(self):
        u = urlparse(self.path).path
        try:
            if u.startswith("/api/p/"):
                pid = u.split("/")[3]
                d = manifest.project_dir(pid)
                data = self._body()
                manifest.save(d, data)
                return self._json({"ok": True, "errors": manifest.validate(data)})
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path).path
        if u == "/api/upload":
            name = Path(self._q().get("name", "file")).name
            n = int(self.headers.get("Content-Length") or 0)
            dest = studio_api.tools_dir() / name
            with dest.open("wb") as f:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            return self._json({"name": name})
        b = self._body()
        try:
            if u.startswith("/api/p/") and u.endswith("/run"):
                pid = u.split("/")[3]
                step = b.get("step", "all")
                args = {"draft": ["render", pid, "--draft"]}.get(step, [step, pid])
                if b.get("scenes"):
                    args += ["--scenes", b["scenes"]]
                if b.get("force"):
                    args.append("--force")
                return self._json({"job": run_job(args)})
            if u.startswith("/api/p/") and u.endswith("/ask"):
                return self._json({"job": run_job(["edit", u.split("/")[3], b["text"]])})
            if u.startswith("/api/p/") and u.endswith("/translate"):
                return self._json({"job": run_job(["translate", u.split("/")[3], "--to", b["to"], *(["--render"] if b.get("render") else [])])})
            if u == "/api/new":
                args = ["new", b["topic"], "--genre", b.get("genre", "animation"), "--seconds", str(b.get("seconds", 45))]
                for k in ("style", "aspect", "lang"):
                    if b.get(k):
                        args += [f"--{k}", b[k]]
                return self._json({"job": run_job(args)})
            if u in ("/api/ping", "/api/bye"):
                import time
                global SEEN_TAB, LAST_BYE
                tab = str(b.get("tab", ""))[:40]
                if u == "/api/ping" and tab:
                    TABS[tab] = time.time()
                    SEEN_TAB = True
                elif tab:
                    TABS.pop(tab, None)
                    LAST_BYE = time.time()
                return self._json({"ok": True, "tabs": len(TABS), "busy": _busy()})
            if u == "/api/shutdown":
                threading.Timer(0.3, lambda: os._exit(0)).start()
                return self._json({"ok": True})
            if u == "/api/series":
                return self._json(studio_api.series_add(b.get("name", "").strip()))
            if u == "/api/plan":
                return self._json(studio_api.plan_set(b.get("items", [])))
            if u == "/api/research":
                from engine import trends
                return self._json({"job": run_fn(trends.research, b.get("markets") or ["vi"], b.get("window", "30 ngày qua"),
                                                 b.get("format", "Video dài + Shorts"), int(b.get("count", 8)),
                                                 b.get("niche", ""), bool(b.get("fresh")))})
            if u == "/api/write":
                from engine.agent.director import plan
                kw = {k: b.get(k) for k in ("style", "aspect", "lang", "tone", "series", "platforms", "subtitle_langs", "burn_captions")}
                kw["seconds"] = int(float(b.get("minutes") or 1) * 60)
                kw["notes"] = " ".join(x for x in (b.get("preset_notes"), b.get("extra")) if x)

                def write_job():
                    d, errs = plan(b["topic"], genre=b.get("genre") or "explainer", **{k: v for k, v in kw.items() if v not in (None, "", [])})
                    return {"project_id": d.name, "errors": errs}
                return self._json({"job": run_fn(write_job)})
            if u == "/api/narration":
                from engine import narration
                from engine.agent.director import new_project
                data = narration.build(b["text"], b.get("title", ""), b.get("lang") or "vi", b.get("aspect") or "9:16",
                                       b.get("style") or None)
                if b.get("series"):
                    data["series"] = b["series"]
                d = new_project(data, b.get("title") or None)
                return self._json({"project_id": d.name, "scenes": len(data["scenes"]), "errors": manifest.validate(data)})
            if u.startswith("/api/p/") and u.endswith("/publish"):
                return self._json({"job": run_fn(studio_api.publish_pack, u.split("/")[3], b.get("platform", "YouTube"))})
            if u.startswith("/api/p/") and u.endswith("/thumb_pro"):
                return self._json({"job": run_fn(studio_api.thumbnail_pro, u.split("/")[3], b.get("text"), b.get("badge"), b.get("at"))})
            if u.startswith("/api/p/") and u.endswith("/subs"):
                return self._json({"job": run_fn(studio_api.extra_subtitles, u.split("/")[3], b.get("langs", []))})
            if u.startswith("/api/p/") and u.endswith("/series"):
                d, data = manifest.load(u.split("/")[3])
                if b.get("series"):
                    data["series"] = b["series"]
                else:
                    data.pop("series", None)
                manifest.save(d, data)
                return self._json({"ok": True})
            if u == "/api/tools/run":
                return self._json({"job": run_fn(studio_api.tool_run, b["kind"], b["src"], b.get("opt", {}))})
            if u == "/api/gpu":
                studio_api.settings_set({"visual.comfyui_url": b.get("url", "")})
                return self._json(studio_api.gpu_ping(b.get("url", "")))
            if u == "/api/settings":
                return self._json(studio_api.settings_set(b.get("values", {})))
            if u == "/api/ideas":
                from engine.agent.director import ideas
                return self._json({"job": run_fn(ideas, b.get("geo", "VN"), b.get("lang", "vi"), int(b.get("count", 6)),
                                                 b.get("genre") or None, b.get("niche", ""))})
            if u == "/api/auto":
                args = ["auto", "--geo", b.get("geo", "VN"), "--lang", b.get("lang", "vi"), "--count", str(b.get("count", 1)),
                        "--seconds", str(b.get("seconds", 45))]
                for k in ("genre", "langs", "style", "aspect", "niche", "topics"):
                    if b.get(k):
                        args += [f"--{k}", str(b[k])]
                if b.get("draft"):
                    args.append("--draft")
                return self._json({"job": run_job(args)})
            if u == "/api/mcp-install":
                r = subprocess.run([sys.executable, str(config.ROOT / "vf.py"), "mcp-install"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", cwd=config.ROOT)
                return self._json({"ok": r.returncode == 0, "log": r.stdout + r.stderr})
            if u == "/api/prompt":
                from engine.agent.director import manual_prompt
                return self._json({"prompt": manual_prompt(b["topic"], genre=b.get("genre", "animation"), style=b.get("style") or None,
                                                           aspect=b.get("aspect") or None, lang=b.get("lang") or None,
                                                           seconds=int(b.get("seconds", 45)))})
            if u == "/api/import":
                from engine.agent.director import import_manifest
                d, errs = import_manifest(b["text"], b.get("id") or None)
                return self._json({"id": d.name, "errors": errs})
            return self._json({"error": "không có"}, 404)
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def _stop_old(port: int) -> bool:
    """Studio cũ còn chạy trên cổng này? Bản mới có /api/shutdown; bản rất cũ thì không tắt được từ xa."""
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", data=b"{}",
                                                      headers={"Content-Type": "application/json"}), timeout=2)
        print("↻ Đã tắt Studio cũ đang chạy, khởi động bản mới…")
        return True
    except Exception:
        return False


def serve(port: int = 8765, open_browser: bool = True):
    config.workspace().mkdir(exist_ok=True)
    srv = None
    for attempt in range(2):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
            break
        except OSError:
            if attempt == 0 and _stop_old(port):
                import time
                time.sleep(1.2)
                continue
            print(f"✘ Cổng {port} đang bị một Studio cũ chiếm. Đóng cửa sổ Studio cũ (hoặc khởi động lại máy) rồi mở lại.")
            return
    url = f"http://127.0.0.1:{port}"
    print(f"🎛  Web Studio: {url}  (đóng tab Studio là tự tắt; Ctrl+C để tắt ngay)")
    threading.Thread(target=_watchdog, daemon=True).start()
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
