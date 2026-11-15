"""MCP server: cho Claude Desktop (tài khoản Claude, không cần API key) điều khiển AI Workflow trên máy bạn.

Cài vào Claude Desktop:  python vf.py mcp-install   (rồi thoát hẳn và mở lại Claude Desktop)
Sau đó chat: "Tìm chủ đề đang hot ở Việt Nam và làm 1 video người que 45 giây".

Claude tự viết kịch bản/dịch trong cuộc chat (dùng gói Claude của bạn); máy bạn lo giọng đọc, hình và ghép video.
Việc nặng (giọng, render) chạy nền: run_step trả job_id, theo dõi bằng job_status.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP, Image  # noqa: E402

from engine import catalog, config, manifest, trends  # noqa: E402
from engine.agent import director  # noqa: E402
from engine.agent.tools import manifest_tools  # noqa: E402

INSTRUCTIONS = """AI Workflow: dựng video ngắn (người que, motion graphics, tin tức) trên máy người dùng.
Quy trình chuẩn:
1. (tuỳ chọn) trending_topics → chọn chủ đề an toàn, giải thích được (bỏ chết chóc, chính trị, tin đồn, trẻ em).
2. get_guide(genre) → đọc quy tắc + catalog (tên template/act/style hợp lệ). Tra web để kiểm chứng số liệu nếu có thể.
3. Tự viết project_manifest.json rồi gọi create_video. Không viết audio_path/duration/word_timings.
4. run_step(id, "preview") → job_status → get_preview để xem ảnh từng cảnh; sửa bằng update_scene nếu cần.
5. run_step(id, "all") → job_status cho tới khi xong; báo đường dẫn video cho người dùng.
Đa ngôn ngữ: tự dịch rồi gọi create_translation(id, lang, scenes) → run_step(id_mới, "all").
Trả lời người dùng bằng ngôn ngữ của họ, ngắn gọn."""

mcp = FastMCP("ai-workflow", instructions=INSTRUCTIONS)
JOBS: dict[str, dict] = {}


@contextlib.contextmanager
def quiet():
    """Không để log của engine lọt vào stdout (stdout là kênh giao thức MCP)."""
    with contextlib.redirect_stdout(sys.stderr):
        yield


def _tool(project_id: str, name: str):
    d = manifest.project_dir(project_id)
    return {t.name: t for t in manifest_tools(d)}[name].fn


@mcp.tool()
def get_guide(genre: str = "animation") -> str:
    """Quy tắc viết kịch bản + catalog template/động tác/style/nhân vật. Gọi trước khi viết manifest.
    genre: animation | motion_graphic | news | explainer"""
    P = config.CONFIG / "prompts"
    parts = [(P / "base.md").read_text(encoding="utf-8")]
    if (P / f"{genre}.md").exists():
        parts.append((P / f"{genre}.md").read_text(encoding="utf-8"))
    parts.append(catalog.text())
    parts.append("Ví dụ manifest hoàn chỉnh:\n" + (ROOT / "examples" / "meo_thich_hop" / "project_manifest.json").read_text(encoding="utf-8"))
    return "\n\n".join(parts)


@mcp.tool()
def trending_topics(geo: str = "VN", lang: str = "vi", limit: int = 40, fresh: bool = False) -> str:
    """Chủ đề đang thịnh hành từ Google Trends (theo quốc gia geo, vd VN, US, JP), Wikipedia (theo ngôn ngữ lang)
    và Hacker News. Trả danh sách gọn để bạn chọn ý tưởng video."""
    with quiet():
        t = trends.collect(geo, lang, fresh=fresh)
    head = f"Lấy lúc {t['fetched']} · {len(t['items'])} mục"
    if t["errors"]:
        head += " · nguồn lỗi: " + "; ".join(t["errors"])
    return head + "\n" + trends.compact(t["items"], limit) + "\n\n" + (config.CONFIG / "prompts" / "ideas.md").read_text(encoding="utf-8")


@mcp.tool()
def create_video(manifest_json: str | dict, project_id: str = "") -> str:
    """Lưu kịch bản (project_manifest.json dạng JSON) thành project mới. Trả về id và lỗi cần sửa."""
    text = manifest_json if isinstance(manifest_json, str) else json.dumps(manifest_json, ensure_ascii=False)
    with quiet():
        d, errs = director.import_manifest(text, project_id or None)
    return json.dumps({"project_id": d.name, "folder": str(d), "errors": errs,
                       "next": "sửa lỗi bằng update_scene" if errs else "run_step(project_id, 'preview')"}, ensure_ascii=False)


@mcp.tool()
def list_videos() -> str:
    """Danh sách project: id, số cảnh, thời lượng, đã có video chưa."""
    rows = []
    for m in sorted(config.workspace().glob("*/" + manifest.MANIFEST), key=lambda p: -p.stat().st_mtime):
        data = json.loads(m.read_text(encoding="utf-8"))
        out = m.parent / "out"
        vids = [p.name for p in out.glob("*.mp4")] if out.exists() else []
        rows.append(f"{m.parent.name} | {data.get('title', '')} | {len(data.get('scenes', []))} cảnh | "
                    f"{sum(s.get('duration', 0) for s in data.get('scenes', [])):.0f}s | {data.get('lang', '')} | {', '.join(vids) or 'chưa render'}")
    return "\n".join(rows) or "Chưa có video nào."


@mcp.tool()
def show_video(project_id: str, scene_id: str = "") -> str:
    """Xem project (1 dòng/cảnh) hoặc chi tiết một cảnh."""
    if scene_id:
        return json.dumps(_tool(project_id, "get_scene")(scene_id), ensure_ascii=False, indent=1)
    return _tool(project_id, "list_scenes")()


@mcp.tool()
def update_scene(project_id: str, scene_id: str, patch: dict) -> str:
    """Sửa một cảnh bằng patch gộp sâu (giá trị null = xoá trường). Chỉ gửi trường cần đổi."""
    return json.dumps(_tool(project_id, "update_scene")(scene_id, patch), ensure_ascii=False)


@mcp.tool()
def add_scene(project_id: str, after_scene_id: str, scene: dict) -> str:
    """Chèn cảnh mới sau after_scene_id ("0" = đầu video)."""
    return json.dumps(_tool(project_id, "add_scene")(after_scene_id, scene), ensure_ascii=False)


@mcp.tool()
def delete_scene(project_id: str, scene_id: str) -> str:
    """Xoá một cảnh."""
    return json.dumps(_tool(project_id, "delete_scene")(scene_id), ensure_ascii=False)


@mcp.tool()
def set_project(project_id: str, fields: dict) -> str:
    """Sửa trường cấp project: style, aspect_ratio, cast, music, voice, lang, title."""
    return json.dumps(_tool(project_id, "set_project")(fields), ensure_ascii=False)


@mcp.tool()
def list_languages() -> str:
    """Ngôn ngữ và giọng đọc hỗ trợ (mã dùng cho lang / voice)."""
    langs = config.library("languages")["languages"]
    return "\n".join(f"{k}: {v['name']} · giọng: {', '.join(v['voices'])}" for k, v in langs.items())


@mcp.tool()
def create_translation(project_id: str, lang: str, scenes: list[dict]) -> str:
    """Tạo bản ngôn ngữ khác thành project mới. Bạn tự dịch rồi truyền scenes =
    [{"id": scene_id, "voice_text": "...", "props": {chữ trên màn hình đã dịch}, "says": [thoại bong bóng]}].
    Lấy văn bản gốc bằng show_video(project_id, scene_id)."""
    with quiet():
        d = director.translate(project_id, lang, texts=scenes)
    return json.dumps({"project_id": d.name, "next": f"run_step('{d.name}', 'all')"}, ensure_ascii=False)


@mcp.tool()
def run_step(project_id: str, step: str = "all", scenes: str = "") -> str:
    """Chạy nền một bước: voice (giọng đọc) | preview (ảnh mỗi cảnh) | draft (video nháp nhanh) | all (video đầy đủ).
    scenes: vd "s001,s003" để chỉ làm vài cảnh. Trả job_id; gọi job_status để theo dõi."""
    manifest.project_dir(project_id)
    args = {"draft": ["render", project_id, "--draft"]}.get(step, [step, project_id])
    if scenes and step in ("voice", "preview"):
        args += ["--scenes", scenes]
    jid = uuid.uuid4().hex[:8]
    job = JOBS[jid] = {"project": project_id, "step": step, "log": "", "done": False, "code": None}

    def go():
        p = subprocess.Popen([sys.executable, "-u", str(ROOT / "vf.py"), *args], cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in p.stdout:
            job["log"] += line
        job["code"] = p.wait()
        job["done"] = True

    threading.Thread(target=go, daemon=True).start()
    return json.dumps({"job_id": jid, "hint": "gọi job_status(job_id) sau ~20-60 giây"}, ensure_ascii=False)


@mcp.tool()
def job_status(job_id: str) -> str:
    """Tiến độ job chạy nền: done, mã lỗi, 25 dòng log cuối, file kết quả."""
    j = JOBS.get(job_id)
    if not j:
        return "Không có job này (server có thể đã khởi động lại)."
    d = config.workspace() / j["project"]
    outs = [str(p) for p in (d / "out").glob("*.mp4")] if j["done"] and (d / "out").exists() else []
    return json.dumps({"done": j["done"], "ok": j["code"] == 0 if j["done"] else None, "step": j["step"],
                       "log_tail": "\n".join(j["log"].strip().splitlines()[-25:]), "videos": outs,
                       "preview": str(d / "preview" / "_sheet.jpg") if j["step"] == "preview" and j["done"] else None},
                      ensure_ascii=False)


@mcp.tool()
def get_preview(project_id: str, scene: str = "") -> Image:
    """Ảnh xem trước: cả video (_sheet) hoặc một cảnh (vd 's003'). Chạy run_step(id, 'preview') trước."""
    d = manifest.project_dir(project_id)
    p = d / "preview" / (f"{scene}.jpg" if scene else "_sheet.jpg")
    if not p.exists():
        raise FileNotFoundError("Chưa có ảnh xem trước: chạy run_step(project_id, 'preview') trước.")
    return Image(path=p)


_studio = None


@mcp.tool()
def open_studio(project_id: str = "") -> str:
    """Mở Web Studio trên máy người dùng để họ tự chỉnh/xem video."""
    global _studio
    import webbrowser
    if _studio is None or _studio.poll() is not None:
        _studio = subprocess.Popen([sys.executable, str(ROOT / "vf.py"), "studio", "--no-open"], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    webbrowser.open("http://127.0.0.1:8765")
    return "Đã mở Web Studio tại http://127.0.0.1:8765"


if __name__ == "__main__":
    mcp.run()
