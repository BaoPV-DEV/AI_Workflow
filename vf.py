#!/usr/bin/env python3
"""vf – dòng lệnh của AI Workflow. Chạy `python vf.py -h` để xem lệnh."""
from __future__ import annotations

import argparse
import json
import shutil
import sys

from engine import winhide

winhide.setup()  # mở bằng Studio.vbs (pythonw): không terminal, log ra .cache/studio.log
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")


def _only(a):
    return a.scenes.split(",") if getattr(a, "scenes", None) else None


def cmd_doctor(a):
    from engine import config
    from engine.util import encoders, pick_encoder

    ok = lambda b: "✔" if b else "✘"
    try:
        from engine.util import ffmpeg, has_filter
        from engine.pipeline import caption_mode, _ctx
        exe = ffmpeg()
        print(f"✔ ffmpeg: {exe}")
        print(f"✔ encoder: {pick_encoder(config.settings()['render'].get('encoder', 'auto'))} · phụ đề: "
              f"{'ffmpeg/libass' if has_filter('ass') else 'vẽ trong khung hình (không có libass)'}")
    except Exception as e:
        print(f"✘ ffmpeg: {e}")
    for mod, hint in [("playwright", "pip install playwright && python -m playwright install chromium"),
                      ("edge_tts", "pip install edge-tts"), ("faster_whisper", "pip install faster-whisper (tuỳ chọn)"),
                      ("anthropic", "pip install anthropic (tuỳ chọn – chỉ cần cho vf new/edit/translate)"),
                      ("jsonschema", "pip install jsonschema"), ("yaml", "pip install pyyaml")]:
        try:
            __import__(mod)
            print(f"✔ {mod}")
        except ImportError:
            print(f"✘ {mod}  → {hint}")
    try:
        from engine.visual import html
        html.browser()
        print("✔ trình duyệt headless")
        html.close()
    except Exception as e:
        print(f"✘ trình duyệt: {e}")
    from engine.agent.llm import backend
    be = backend()
    names = {"api": "API key", "cli": "Claude Code (gói Claude của bạn)", "manual": "chưa kết nối – vẫn dùng được Claude Desktop hoặc vf prompt + vf import"}
    print(f"{ok(be != 'manual')} AI tự gọi: {names[be]}")


def cmd_catalog(a):
    from engine import catalog
    t = catalog.write()
    print(t if a.show else f"✔ Đã ghi CATALOG.md ({len(t)} ký tự ≈ {len(t) // 4} token)")


def _plan_kw(a):
    return dict(genre=a.genre, style=a.style, aspect=a.aspect, lang=a.lang, seconds=a.seconds, notes=a.notes or "")


def cmd_prompt(a):
    from engine.agent.director import manual_prompt
    t = manual_prompt(a.topic, **_plan_kw(a))
    if a.out:
        open(a.out, "w", encoding="utf-8").write(t)
        print(f"✔ Đã ghi {a.out} – dán vào claude.ai, lưu JSON trả về rồi chạy: vf import <file>")
    else:
        print(t)


def cmd_new(a):
    from engine.agent.director import plan
    from engine.agent.llm import backend
    print(f"🧠 Bộ não: {backend()}", flush=True)
    d, errs = plan(a.topic, project_id=a.id, **_plan_kw(a))
    print(f"✔ Project: {d}")
    if errs:
        print("⚠ Còn lỗi:\n  " + "\n  ".join(errs))
    else:
        print(f"Tiếp: python vf.py preview {d.name}  →  python vf.py all {d.name}")


def cmd_import(a):
    from engine.agent.director import import_manifest
    text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    d, errs = import_manifest(text, a.id)
    print(f"✔ Project: {d}")
    print("⚠ Lỗi:\n  " + "\n  ".join(errs) if errs else f"Hợp lệ. Tiếp: python vf.py all {d.name}")


def cmd_check(a):
    from engine import manifest
    _, data = manifest.load(a.project)
    errs = manifest.validate(data)
    words = sum(len((s.get("voice_text") or "").split()) for s in data["scenes"])
    print(f"{len(data['scenes'])} cảnh · {words} từ · ước lượng {words / 2.5:.0f}s")
    print("✔ Hợp lệ" if not errs else "✘ " + "\n✘ ".join(errs))
    return 1 if errs else 0


def cmd_show(a):
    """In manifest gọn (bỏ timing) – để Claude đọc ít token nhất."""
    from engine import manifest
    _, data = manifest.load(a.project)
    lean = manifest.strip_engine_fields(data)
    for s in lean["scenes"]:
        s.pop("speech", None)
    if a.scene:
        lean = next(s for s in lean["scenes"] if str(s["scene_id"]) == a.scene)
        print(json.dumps(lean, ensure_ascii=False, indent=1))
    elif a.full:
        print(json.dumps(lean, ensure_ascii=False, separators=(",", ":")))
    else:
        head = {k: v for k, v in lean.items() if k != "scenes"}
        print(json.dumps(head, ensure_ascii=False, separators=(",", ":")))
        for s in lean["scenes"]:
            tpl = s.get("template_name") or s.get("visual_type")
            print(f"{s['scene_id']}|{tpl}|{len(s.get('acting') or [])} beat|{s.get('voice_text', '')}")


def cmd_edit(a):
    from engine.agent.director import edit
    edit(a.project, a.instruction)


def cmd_translate(a):
    from engine.agent.director import translate
    from engine import pipeline
    for lang in a.to.split(","):
        d = translate(a.project, lang.strip())
        print(f"✔ {lang}: {d.name}")
        if a.render:
            pipeline.voice(d)
            pipeline.render(d)


def cmd_voice(a):
    from engine import pipeline
    pipeline.voice(a.project, _only(a), a.force)


def cmd_preview(a):
    from engine import pipeline
    pipeline.preview(a.project, a.at, _only(a))


def cmd_visuals(a):
    from engine import pipeline
    pipeline.visuals(a.project, _only(a), a.force, a.draft, a.workers)


def cmd_render(a):
    from engine import pipeline
    pipeline.render(a.project, draft=a.draft, captions_on=False if a.no_captions else None)


def cmd_all(a):
    from engine import pipeline
    pipeline.voice(a.project)
    pipeline.render(a.project, draft=a.draft, captions_on=False if a.no_captions else None)


def cmd_list(a):
    from engine import config, manifest
    for d in sorted(config.workspace().glob("*/" + manifest.MANIFEST)):
        data = json.loads(d.read_text(encoding="utf-8"))
        outs = [p.name for p in (d.parent / "out").glob("*.mp4")] if (d.parent / "out").exists() else []
        dur = sum(s.get("duration", 0) for s in data.get("scenes", []))
        print(f"{d.parent.name:32} {len(data.get('scenes', [])):3} cảnh  {dur:6.1f}s  {data.get('style', '-'):14} {', '.join(outs) or '(chưa render)'}")


def cmd_usage(a):
    from engine import config
    p = config.workspace() / ".usage.jsonl"
    if not p.exists():
        print("Chưa có lần gọi API nào.")
        return
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    tot = {k: sum(r.get(k) or 0 for r in rows) for k in ("in", "out", "cache_read", "cache_write")}
    print(f"{len(rows)} lần gọi · vào {tot['in']:,} · ra {tot['out']:,} · cache đọc {tot['cache_read']:,} · cache ghi {tot['cache_write']:,}")


def cmd_trends(a):
    from engine import trends
    t = trends.collect(a.geo, a.lang, fresh=a.fresh)
    print(f"Lấy lúc {t['fetched']} · {len(t['items'])} mục" + (f" · lỗi: {t['errors']}" if t["errors"] else ""))
    print(trends.compact(t["items"], a.limit))


def cmd_ideas(a):
    from engine.agent.director import ideas
    res = ideas(a.geo, a.lang, a.count, a.genre, a.niche or "", a.fresh)
    for i in res.get("ideas", []):
        print(f"\n[{i.get('score')}/10 · {i.get('risk')} · {i.get('genre')}] {i['topic']}")
        for k in ("title", "hook", "angle", "why_now"):
            if i.get(k):
                print(f"   {k}: {i[k]}")
    print(f"\nLàm video: vf new \"<topic>\" --genre <genre>   hoặc   vf auto --topics \"<topic>\"")


def cmd_auto(a):
    from engine import auto
    auto.run(a.geo, a.lang, a.count, a.genre, [x.strip() for x in (a.langs or "").split(",") if x.strip()],
             a.seconds, a.style, a.aspect, a.niche or "", not a.no_render, a.draft,
             [x.strip() for x in a.topics.split("|")] if a.topics else None)


def cmd_mcp_install(a):
    """Đăng ký MCP server vào Claude Desktop (Windows / macOS)."""
    import os
    from pathlib import Path
    from engine import config
    entry = {"command": sys.executable, "args": [str(config.ROOT / "mcp_server.py")],
             "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}
    cands = []
    if sys.platform == "win32":
        cands.append(Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json")
        pk = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
        if pk.exists():  # bản Claude cài từ Microsoft Store
            cands += [p / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json" for p in pk.glob("Claude_*")]
    elif sys.platform == "darwin":
        cands.append(Path.home() / "Library/Application Support/Claude/claude_desktop_config.json")
    else:
        cands.append(Path.home() / ".config/Claude/claude_desktop_config.json")
    done = []
    for f in cands:
        if not f.parent.exists() and f != cands[0]:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            cfg = json.loads(f.read_text(encoding="utf-8-sig")) if f.exists() else {}
        except json.JSONDecodeError:
            print(f"✘ {f} không phải JSON hợp lệ, bỏ qua (sửa tay rồi chạy lại)")
            continue
        cfg.setdefault("mcpServers", {})["ai-workflow"] = entry
        f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        done.append(str(f))
    for f in done:
        print(f"✔ Đã thêm 'ai-workflow' vào {f}")
    print("→ Thoát hẳn Claude Desktop (cả biểu tượng ở khay hệ thống) rồi mở lại. Chat: \"Tìm chủ đề hot và làm 1 video\".")


def cmd_brain(a):
    from engine.agent.llm import backend, claude_cli
    import os
    be = backend()
    print(f"Bộ não đang dùng: {be}")
    print(f"  API key: {'có' if os.environ.get('ANTHROPIC_API_KEY') else 'không'} · Claude Code: {claude_cli() or 'chưa cài'}")
    if be == "manual":
        from engine.agent.llm import MANUAL_HELP
        print(MANUAL_HELP)


def cmd_schedule(a):
    """Tạo lịch chạy tự động mỗi ngày (Windows Task Scheduler)."""
    from engine import config
    if sys.platform != "win32":
        print(f"Thêm vào crontab: 0 7 * * * cd {config.ROOT} && {sys.executable} vf.py auto {a.args}")
        return
    import subprocess
    tr = f'cmd /c cd /d "{config.ROOT}" && "{sys.executable}" vf.py auto {a.args} >> workspace\\_auto\\log.txt 2>&1'
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", "AI Workflow Auto", "/TR", tr, "/ST", a.time],
                       capture_output=True, text=True)
    print(r.stdout or r.stderr)


def cmd_audit(a):
    from engine import studio_api
    r = studio_api.policy_audit(a.project)
    names = {"CHAN": "CHẶN", "RUI_RO": "RỦI RO", "LUU_Y": "LƯU Ý"}
    for i, it in enumerate(r["issues"]):
        print(f"[{i}] {names.get(it['level'], it['level'])} · cảnh {it['scene_id']} · {it['item']} — {it['problem']}")
        if it.get("rewrite"):
            print(f"     → {it['rewrite']}")
    print(f"Nhãn AI: {r.get('ai_disclosure')}\nNội dung lặp: {r.get('inauthentic_risk')}\nQuảng cáo: {r.get('ad_friendly')}\n{r.get('status')}")
    if a.apply and r["issues"]:
        done = studio_api.audit_apply(a.project)["applied"]
        print(f"✔ Đã áp {len(done)} câu viết lại. Tạo lại giọng: vf voice {a.project}")


def cmd_skills_sync(a):
    """Kéo bản mới của repo Skills (BaoPV-DEV/Skills) và cập nhật tài liệu tham chiếu của skill video-strategy."""
    import shutil
    import subprocess
    from engine import config
    url = a.repo or (config.settings().get("skills") or {}).get("repo", "https://github.com/BaoPV-DEV/Skills.git")
    cache = config.ROOT / ".cache" / "skills_repo"
    if (cache / ".git").exists():
        subprocess.run(["git", "-C", str(cache), "pull", "-q", "--ff-only"], check=True)
    else:
        cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(cache)], check=True)
    src = cache / ".claude" / "skills" / "ai-video-production-pipeline" / "references"
    dst = config.ROOT / ".claude" / "skills" / "video-strategy" / "references"
    for n in ("channel-analysis-framework.md", "seo-and-retention-rules.md", "policy-checklist.md"):
        shutil.copy2(src / n, dst / n)
    # bộ dựng nhân vật 3D (make_character.py đã chỉnh đường dẫn cho AI Workflow nên giữ nguyên)
    shutil.copy2(cache / ".claude" / "skills" / "ai-video-production-pipeline" / "scripts" / "hero3d" / "build_character.py",
                 config.ROOT / "engine" / "hero3d" / "build_character.py")
    rev = subprocess.run(["git", "-C", str(cache), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    f = dst / "SOURCE.md"
    import re
    f.write_text(re.sub(r"\(commit \w+\)", f"(commit {rev})", f.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"✔ Đã cập nhật tài liệu từ Skills @ {rev}. Bản rút gọn cho AI (config/prompts/policy.md, publish.md) sửa tay nếu quy tắc đổi nhiều.")


def cmd_char3d(a):
    from engine import char3d
    if a.action == "setup":
        char3d.setup()
    elif a.action == "status":
        st = char3d.status()
        print(f"Blender: {st['python'] or '✘ chưa cài (vf char3d setup)'}\nDữ liệu cơ thể: {st['mpfb'] or '✘ chưa tải'}\n"
              f"Card NVIDIA: {st['gpu'] or 'không → render CPU, ~12 giây/khung ở chất lượng chuẩn'}")
    elif a.action == "list":
        for c in char3d.characters():
            print(f"{c['id']:14s} {c['name']:16s} {'động tác: ' + ', '.join(c['sets']) if c['sets'] else '(chưa render)'}")
    elif a.action == "new":
        s = char3d.new(a.id, a.base or "mia", name=a.name)
        print(f"✔ Tạo library/cast3d/{s['id']}.json từ mẫu '{a.base or 'mia'}'. Sửa file đó (tóc, quần áo, màu…), rồi: vf char3d sheet {s['id']}")
    elif a.action == "sheet":
        char3d.sheet(a.id, a.quality or "nhap")
    elif a.action == "sprites":
        char3d.sprites(a.id, a.profile, a.light, a.quality or "chuan", a.only or "")
        from engine import catalog
        catalog.write()


def cmd_studio(a):
    from web.server import serve
    serve(a.port, open_browser=not a.no_open)


def main(argv=None):
    p = argparse.ArgumentParser(prog="vf", description="AI Workflow – pipeline video AI tối ưu token")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        return s

    add("doctor", cmd_doctor, "kiểm tra cài đặt")
    s = add("catalog", cmd_catalog, "sinh CATALOG.md gọn cho Claude"); s.add_argument("--show", action="store_true")
    for name, fn, h in [("new", cmd_new, "chủ đề -> manifest bằng Claude API"),
                        ("prompt", cmd_prompt, "in prompt để dán vào claude.ai (không tốn API)")]:
        s = add(name, fn, h)
        s.add_argument("topic")
        s.add_argument("--genre", default="animation", choices=["animation", "motion_graphic", "news", "explainer"])
        s.add_argument("--style"); s.add_argument("--aspect", choices=["9:16", "16:9", "1:1"]); s.add_argument("--lang")
        s.add_argument("--seconds", type=int, default=45); s.add_argument("--notes")
        s.add_argument("--id" if name == "new" else "--out")
    s = add("import", cmd_import, "nhập manifest JSON (file hoặc - để dán)"); s.add_argument("file"); s.add_argument("--id")
    s = add("check", cmd_check, "kiểm tra manifest"); s.add_argument("project")
    s = add("show", cmd_show, "in manifest gọn (ít token)"); s.add_argument("project"); s.add_argument("--scene"); s.add_argument("--full", action="store_true")
    s = add("edit", cmd_edit, "sửa video bằng lời (agent, model rẻ)"); s.add_argument("project"); s.add_argument("instruction")
    s = add("translate", cmd_translate, "dịch sang ngôn ngữ khác (project mới)"); s.add_argument("project"); s.add_argument("--to", required=True); s.add_argument("--render", action="store_true")
    for name, fn, h in [("voice", cmd_voice, "tạo giọng + mốc từ"), ("preview", cmd_preview, "ảnh tĩnh mỗi cảnh + _sheet.jpg"),
                        ("visuals", cmd_visuals, "chỉ quay hình các cảnh"), ("render", cmd_render, "ghép video cuối"),
                        ("all", cmd_all, "voice + visuals + render")]:
        s = add(name, fn, h)
        s.add_argument("project")
        s.add_argument("--scenes", help="vd s001,s004")
        s.add_argument("--force", action="store_true")
        s.add_argument("--draft", action="store_true", help="nửa độ phân giải, nhanh gấp ~3 lần")
        s.add_argument("--workers", type=int)
        s.add_argument("--at", type=float, default=0.62)
        s.add_argument("--no-captions", action="store_true")
    add("list", cmd_list, "liệt kê project")
    add("usage", cmd_usage, "tổng token đã dùng")
    for name, fn, h in [("trends", cmd_trends, "xem chủ đề đang thịnh hành"), ("ideas", cmd_ideas, "AI lọc xu hướng thành ý tưởng video"),
                        ("auto", cmd_auto, "tự động: xu hướng → kịch bản → giọng → video")]:
        s = add(name, fn, h)
        s.add_argument("--geo", default="VN", help="quốc gia Google Trends: VN, US, JP…")
        s.add_argument("--lang", default="vi", help="ngôn ngữ video / Wikipedia")
        s.add_argument("--fresh", action="store_true")
        s.add_argument("--limit", type=int, default=40)
        s.add_argument("--count", type=int, default=6 if name == "ideas" else 2)
        s.add_argument("--genre", choices=["animation", "motion_graphic", "news", "explainer"])
        s.add_argument("--niche", help="chủ đề kênh, vd 'khoa học đời sống'")
        s.add_argument("--langs", help="thêm bản ngôn ngữ khác, vd en,ja")
        s.add_argument("--seconds", type=int, default=45)
        s.add_argument("--style"); s.add_argument("--aspect", choices=["9:16", "16:9", "1:1"])
        s.add_argument("--topics", help="bỏ qua xu hướng, làm các chủ đề này (ngăn cách bằng |)")
        s.add_argument("--no-render", action="store_true"); s.add_argument("--draft", action="store_true")
    add("mcp-install", cmd_mcp_install, "đăng ký vào Claude Desktop (dùng tài khoản Claude, không cần API)")
    add("brain", cmd_brain, "xem AI đang dùng: API / Claude Code / thủ công")
    s = add("schedule", cmd_schedule, "chạy vf auto mỗi ngày"); s.add_argument("--time", default="07:13"); s.add_argument("args", nargs="?", default="--count 2")
    s = add("audit", cmd_audit, "kiểm duyệt chính sách YouTube/TikTok (+ --apply để tự sửa lời)"); s.add_argument("project"); s.add_argument("--apply", action="store_true")
    s = add("skills-sync", cmd_skills_sync, "cập nhật tài liệu từ repo Skills"); s.add_argument("--repo")
    s = add("char3d", cmd_char3d, "nhân vật 3D Blender: setup | status | list | new | sheet | sprites")
    s.add_argument("action", choices=["setup", "status", "list", "new", "sheet", "sprites"]); s.add_argument("id", nargs="?")
    s.add_argument("--base", help="mẫu gốc khi tạo mới (vd mia, rain_hero)"); s.add_argument("--name")
    s.add_argument("--profile", default="co_ban", choices=["co_ban", "day_du"]); s.add_argument("--light", default="day")
    s.add_argument("--quality", choices=["nhap", "chuan", "cao"]); s.add_argument("--only", help="vd walk:side:day,talk:front34:day")
    s = add("studio", cmd_studio, "mở Web Studio"); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-open", action="store_true")
    a = p.parse_args(argv)
    try:
        return a.fn(a) or 0
    except Exception as e:  # thông báo gọn, không traceback dài
        if "--debug" in sys.argv or __import__("os").environ.get("VF_DEBUG"):
            raise
        print(f"✘ {e}", file=sys.stderr)
        winhide.alert(f"Lỗi: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
