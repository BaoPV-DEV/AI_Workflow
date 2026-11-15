"""Đạo diễn AI: chủ đề -> manifest; sửa bằng lời; dịch. Có chế độ không cần API key."""
from __future__ import annotations

import copy
import json
import re
import shutil
import unicodedata
from pathlib import Path

from .. import catalog, config, manifest
from .llm import LLM
from .loop import Agent
from .tools import manifest_tools

GENRES = ("animation", "motion_graphic", "news", "explainer")


def slugify(s: str, n: int = 40) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:n] or "video"


def authored_schema() -> dict:
    """Schema manifest đã giải $ref và bỏ trường engine tự điền (gọn hơn, model không phí token)."""
    raw = json.loads(config.SCHEMA.read_text(encoding="utf-8"))
    defs = raw.pop("$defs", {})

    def res(x):
        if isinstance(x, dict):
            if "$ref" in x:
                return res(copy.deepcopy(defs[x["$ref"].split("/")[-1]]))
            return {k: res(v) for k, v in x.items() if k not in ("$schema", "title")}
        if isinstance(x, list):
            return [res(v) for v in x]
        return x

    s = res(raw)
    for f in manifest.ENGINE_FIELDS:
        s["properties"]["scenes"]["items"]["properties"].pop(f, None)
    return s


def build_prompt(topic: str, genre: str = "animation", style: str | None = None, aspect: str | None = None,
                 lang: str | None = None, seconds: int = 45, notes: str = "") -> tuple[list[str], str]:
    st = config.settings()
    P = config.CONFIG / "prompts"
    static = [(P / "base.md").read_text(encoding="utf-8"),
              (P / f"{genre}.md").read_text(encoding="utf-8") if (P / f"{genre}.md").exists() else "",
              catalog.text()]
    words = int(seconds * 2.5)
    user = (f"CHỦ ĐỀ: {topic}\n"
            f"- Ngôn ngữ lời đọc: {lang or st.get('default_lang', 'vi')}\n"
            f"- Tỉ lệ: {aspect or st.get('default_aspect', '9:16')} · Style: {style or 'tự chọn hợp chủ đề'}\n"
            f"- Thời lượng mục tiêu: ~{seconds} giây (~{words} từ lời đọc, ~{max(3, seconds // 5)} cảnh)\n"
            + (f"- Ghi chú: {notes}\n" if notes else ""))
    return static, user


def manual_prompt(topic: str, **kw) -> str:
    """Prompt đầy đủ để dán vào claude.ai (dùng gói Pro, không tốn API)."""
    static, user = build_prompt(topic, **kw)
    return ("\n\n".join(s for s in static if s) + "\n\n" + user +
            "\nTrả về DUY NHẤT một khối ```json chứa project_manifest.json hợp lệ.\n")


def new_project(data: dict, project_id: str | None = None) -> Path:
    pid = slugify(project_id or data.get("project_id") or data.get("title") or "video")
    d = config.workspace() / pid
    k = 2
    while (d / manifest.MANIFEST).exists() and not project_id:
        d = config.workspace() / f"{pid}_{k}"
        k += 1
    (d / "assets").mkdir(parents=True, exist_ok=True)
    data["project_id"] = d.name
    manifest.save(d, data)
    return d


def import_manifest(text: str, project_id: str | None = None) -> tuple[Path, list[str]]:
    data = manifest.parse(text)
    d = new_project(data, project_id)
    return d, manifest.validate(data)


def plan(topic: str, genre: str = "animation", project_id: str | None = None, **kw) -> tuple[Path, list[str]]:
    """Chủ đề -> manifest. Bộ não: API key hoặc Claude Code (tài khoản Claude), tự sửa lỗi tối đa 2 lần."""
    from .llm import complete_json

    facts = kw.pop("facts", None)
    extra = {k: kw.pop(k) for k in ("series", "platforms", "subtitle_langs", "burn_captions") if k in kw}
    tone = kw.pop("tone", None)
    if tone:
        kw["notes"] = (kw.get("notes") or "") + f" Giọng văn / khán giả: {tone}."
    if extra.get("platforms"):
        kw["notes"] = (kw.get("notes") or "") + f" Đăng lên: {', '.join(extra['platforms'])}."
    static, user = build_prompt(topic, genre=genre, **kw)
    if facts:
        user += f"- Sự thật cần kiểm chứng trước khi viết (tra web nếu có thể): {facts}\n"

    def fill(data):
        data.setdefault("lang", kw.get("lang") or config.settings().get("default_lang"))
        data.setdefault("aspect_ratio", kw.get("aspect") or config.settings().get("default_aspect"))
        if kw.get("style"):
            data.setdefault("style", kw["style"])
        return data

    def check(data):
        return manifest.validate({**fill(data), "project_id": slugify(data.get("project_id") or "x")})

    data = complete_json("plan", static, user, authored_schema(), "submit_manifest", web=True, repair=check)
    fill(data)
    for k, v in extra.items():
        if v not in (None, "", []):
            data[k] = v
    data.setdefault("source", "ai")
    errs = check(data)
    d = new_project(data, project_id or slugify(topic))
    return d, errs


def edit(project, instruction: str, on_event=None) -> str:
    from .llm import backend, run_cli, NoBackend, MANUAL_HELP

    d = manifest.project_dir(project)
    be = backend()
    if be == "cli":  # Claude Code tự sửa file theo CLAUDE.md của repo
        rel = d.relative_to(config.ROOT).as_posix() if d.is_relative_to(config.ROOT) else str(d)
        out = run_cli(f"Project video: {d.name} (file {rel}/project_manifest.json).\nYêu cầu: {instruction}\n"
                      f"Làm theo CLAUDE.md: xem bằng `python vf.py show {d.name}`, chỉ sửa đúng cảnh cần sửa, "
                      f"xong chạy `python vf.py check {d.name}`. Trả lời 1 câu ngắn.",
                      "edit", tools="Read,Edit,Bash(python vf.py:*)", permission="acceptEdits")
        msg = out.get("result", "")
        (on_event or print)("🤖 " + msg)
        return msg
    if be != "api":
        raise NoBackend(MANUAL_HELP)
    llm = LLM("edit")
    system = llm.cached_system(
        "Bạn sửa project_manifest.json của một video theo yêu cầu. Dùng công cụ; chỉ chạm vào cảnh cần sửa; "
        "không viết lại cả video. Xong thì trả lời 1 câu ngắn bằng ngôn ngữ của người dùng.\n"
        + (config.CONFIG / "prompts" / "base.md").read_text(encoding="utf-8"))
    agent = Agent(llm, system, manifest_tools(d), max_turns=10, on_event=on_event)
    return agent.run(instruction)


TEXT_KEYS = ("heading", "subheading", "kicker", "title", "label", "sub", "quote", "author", "headline",
             "ticker", "source", "items", "events", "bars", "left", "right", "say", "text", "emphasize", "vs")


def translate(project, to_lang: str, texts: list[dict] | None = None) -> Path:
    """Tạo bản dịch thành project mới <id>_<lang>. texts có sẵn (vd do Claude Desktop dịch) thì không gọi AI."""
    src, data = manifest.load(project)
    payload = []
    for s in data["scenes"]:
        props = {k: v for k, v in (s.get("props") or {}).items() if k in TEXT_KEYS}
        says = [b.get("say") for b in s.get("acting") or []]
        payload.append({"id": s["scene_id"], "voice_text": s.get("voice_text", ""), "props": props,
                        **({"says": says} if any(says) else {})})
    if texts is None:
        from .llm import complete_json
        info = config.language(to_lang)
        schema = {"type": "object", "required": ["scenes"], "properties": {"scenes": {"type": "array", "items": {
            "type": "object", "required": ["id", "voice_text"],
            "properties": {"id": {"type": ["integer", "string"]}, "voice_text": {"type": "string"},
                           "props": {"type": "object"}, "says": {"type": "array"}}}}}}
        system = ["Dịch lời đọc và chữ trên màn hình của video. Giữ nguyên cấu trúc JSON và id. Lời đọc tự nhiên khi "
                  "đọc to, độ dài tương đương bản gốc (cùng thời lượng); chữ trên màn hình ngắn gọn. Số viết bằng chữ "
                  "khi cần đọc đúng. Không dịch tên riêng/thương hiệu. Không thêm bớt ý."]
        user = f"Ngôn ngữ đích: {info['name']} ({to_lang})\n" + json.dumps(payload, ensure_ascii=False)
        texts = complete_json("translate", system, user, schema, "submit")["scenes"]
    by_id = {str(x.get("id")): x for x in texts}
    new = manifest.strip_engine_fields(data)
    for s in new["scenes"]:
        s.pop("speech", None); s.pop("tts", None)
        tr = by_id.get(str(s["scene_id"]))
        if not tr:
            continue
        s["voice_text"] = tr.get("voice_text", s.get("voice_text"))
        s.setdefault("props", {}).update(tr.get("props") or {})
        for b, say in zip(s.get("acting") or [], tr.get("says") or []):
            if say:
                b["say"] = say
        for b in s.get("acting") or []:  # mốc theo từ không còn trong bản dịch -> đổi sang %
            if isinstance(b.get("at"), str) and not b["at"].endswith("%"):
                b["at"] = f"{round(_pct(b['at'], data, s)):.0f}%"
        for k in ("at",):
            v = s.get("props", {}).get(k)
            if isinstance(v, str) and not v.endswith("%"):
                s["props"][k] = f"{round(_pct(v, data, s)):.0f}%"
            if isinstance(v, list):
                s["props"][k] = [x if not isinstance(x, str) or x.endswith("%") else f"{round(_pct(x, data, s)):.0f}%" for x in v]
        for it in s.get("props", {}).get("items", []) if isinstance(s.get("props", {}).get("items"), list) else []:
            if isinstance(it, dict) and isinstance(it.get("at"), str) and not it["at"].endswith("%"):
                it["at"] = f"{round(_pct(it['at'], data, s)):.0f}%"
    code = config.language(to_lang)["code"]
    new["lang"] = code
    new.pop("voice", None)
    dst = config.workspace() / f"{src.name}_{code.replace('-', '_').lower()}"
    shutil.rmtree(dst / "build", ignore_errors=True)
    (dst / "assets").mkdir(parents=True, exist_ok=True)
    for f in (src / "assets").glob("*"):
        if f.is_file() and f.suffix != ".wav":
            shutil.copy2(f, dst / "assets" / f.name)
    new["project_id"] = dst.name
    if new.get("title"):
        new["title"] = f"{new['title']} ({code})"
    manifest.save(dst, new)
    return dst


def ideas(geo: str = "VN", lang: str = "vi", count: int = 6, genre: str | None = None, niche: str = "",
          fresh: bool = False) -> dict:
    """Xu hướng -> ý tưởng video đã lọc & chấm điểm."""
    from .. import trends
    from .llm import complete_json

    t = trends.collect(geo, lang, fresh=fresh)
    if not t["items"]:
        raise RuntimeError("Không lấy được xu hướng nào: " + "; ".join(f"{k}: {v}" for k, v in t["errors"].items()))
    system, user = trends.ideas_prompt(trends.compact(t["items"]), count, lang, genre, niche)
    res = complete_json("ideas", [system], user, trends.IDEA_SCHEMA, "submit_ideas")
    res["fetched"] = t["fetched"]
    res["errors"] = t["errors"]
    return res


def _pct(at: str, data: dict, scene: dict) -> float:
    """Đổi mốc 'từ' sang % dựa trên timing bản gốc (nếu đã có)."""
    from ..align import resolve_at
    orig = next((s for s in data["scenes"] if s["scene_id"] == scene["scene_id"]), {})
    dur = orig.get("duration") or 1
    return 100 * resolve_at(at, orig.get("word_timings") or [], dur, 0) / dur
