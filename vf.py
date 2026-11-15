#!/usr/bin/env python3
"""vf – dòng lệnh của AI Workflow. Chạy `python vf.py -h` để xem lệnh."""
from __future__ import annotations

import argparse
import json
import shutil
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _only(a):
    return a.scenes.split(",") if getattr(a, "scenes", None) else None


def cmd_doctor(a):
    from engine import config
    from engine.util import encoders, pick_encoder

    ok = lambda b: "✔" if b else "✘"
    print(f"{ok(shutil.which('ffmpeg'))} ffmpeg   encoder: {pick_encoder(config.settings()['render'].get('encoder', 'auto'))}")
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
    import os
    print(f"{ok(os.environ.get('ANTHROPIC_API_KEY'))} ANTHROPIC_API_KEY (không có vẫn dùng được: vf prompt + vf import)")


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
    d, errs, llm = plan(a.topic, project_id=a.id, **_plan_kw(a))
    print(f"✔ Project: {d}")
    print("📊 " + llm.usage.line())
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
    for lang in a.to.split(","):
        d = translate(a.project, lang.strip())
        print(f"✔ {lang}: {d}")


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
    s = add("translate", cmd_translate, "dịch sang ngôn ngữ khác (project mới)"); s.add_argument("project"); s.add_argument("--to", required=True)
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
    s = add("studio", cmd_studio, "mở Web Studio"); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-open", action="store_true")
    a = p.parse_args(argv)
    try:
        return a.fn(a) or 0
    except Exception as e:  # thông báo gọn, không traceback dài
        if "--debug" in sys.argv or __import__("os").environ.get("VF_DEBUG"):
            raise
        print(f"✘ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
