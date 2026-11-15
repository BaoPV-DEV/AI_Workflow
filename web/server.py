"""Web Studio local – chỉ dùng thư viện chuẩn Python. Chạy: python vf.py studio"""
from __future__ import annotations

import json
import mimetypes
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from engine import align, catalog, config, manifest, pipeline

WEB = Path(__file__).parent
JOBS: dict[str, dict] = {}


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


MOODS = ["neutral", "happy", "sad", "surprised", "angry", "scared", "tired", "curious", "proud"]
MOVES = ["stay", "enter_left", "enter_right", "exit_left", "exit_right", "left", "center", "right"]
HOLDS = ["book", "phone", "coin", "money", "gift", "bulb", "sign", "laptop", "cup", "flag", "sword", "key", "star",
         "trophy", "magnifier", "map", "briefcase"]


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
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
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

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

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
                                   "moods": MOODS, "moves": MOVES, "holds": HOLDS,
                                   "voices": config.settings().get("tts", {}).get("voices", {})})
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
                return self._json({"job": run_job(["translate", u.split("/")[3], "--to", b["to"]])})
            if u == "/api/new":
                args = ["new", b["topic"], "--genre", b.get("genre", "animation"), "--seconds", str(b.get("seconds", 45))]
                for k in ("style", "aspect", "lang"):
                    if b.get(k):
                        args += [f"--{k}", b[k]]
                return self._json({"job": run_job(args)})
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


def serve(port: int = 8765, open_browser: bool = True):
    config.workspace().mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}"
    print(f"🎛  Web Studio: {url}  (Ctrl+C để tắt)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
