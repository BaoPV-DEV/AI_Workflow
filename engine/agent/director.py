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


def plan(topic: str, genre: str = "animation", project_id: str | None = None, **kw) -> tuple[Path, list[str], LLM]:
    llm = LLM("plan")
    static, user = build_prompt(topic, genre=genre, **kw)
    system = llm.cached_system(*static)
    tool = {"name": "submit_manifest", "description": "Nộp project_manifest.json hoàn chỉnh.",
            "input_schema": authored_schema()}
    msgs = [{"role": "user", "content": user}]
    choice = {"type": "tool", "name": "submit_manifest"}
    data, errs = None, []
    for _ in range(3):  # 1 lần + tối đa 2 lần tự sửa
        resp = llm.call(system, msgs, tools=[tool], tool_choice=choice)
        use = next(b for b in resp.content if b.type == "tool_use")
        data = use.input
        data.setdefault("lang", kw.get("lang") or config.settings().get("default_lang"))
        data.setdefault("aspect_ratio", kw.get("aspect") or config.settings().get("default_aspect"))
        if kw.get("style"):
            data.setdefault("style", kw["style"])
        errs = manifest.validate({**data, "project_id": slugify(data.get("project_id") or "x")})
        if not errs:
            break
        msgs += [{"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]},
                 {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                               "content": "Sửa các lỗi sau rồi nộp lại toàn bộ:\n" + "\n".join(errs[:15])}]}]
    d = new_project(data, project_id or slugify(topic))
    return d, errs, llm


def edit(project, instruction: str, on_event=None) -> str:
    d = manifest.project_dir(project)
    llm = LLM("edit")
    system = llm.cached_system(
        "Bạn sửa project_manifest.json của một video theo yêu cầu. Dùng công cụ; chỉ chạm vào cảnh cần sửa; "
        "không viết lại cả video. Xong thì trả lời 1 câu ngắn bằng ngôn ngữ của người dùng.\n"
        + (config.CONFIG / "prompts" / "base.md").read_text(encoding="utf-8"))
    agent = Agent(llm, system, manifest_tools(d), max_turns=10, on_event=on_event)
    return agent.run(instruction)


TEXT_KEYS = ("heading", "subheading", "kicker", "title", "label", "sub", "quote", "author", "headline",
             "ticker", "source", "items", "events", "bars", "left", "right", "say", "text", "emphasize", "vs")


def translate(project, to_lang: str) -> Path:
    src, data = manifest.load(project)
    llm = LLM("translate")
    payload = []
    for s in data["scenes"]:
        props = {k: v for k, v in (s.get("props") or {}).items() if k in TEXT_KEYS}
        says = [b.get("say") for b in s.get("acting") or []]
        payload.append({"id": s["scene_id"], "voice_text": s.get("voice_text", ""), "props": props,
                        **({"says": says} if any(says) else {})})
    tool = {"name": "submit", "description": "Bản dịch",
            "input_schema": {"type": "object", "required": ["scenes"], "properties": {"scenes": {"type": "array", "items": {"type": "object"}}}}}
    system = llm.cached_system(
        "Dịch lời đọc và chữ trên màn hình của video. Giữ nguyên cấu trúc JSON và id. Lời đọc tự nhiên khi đọc to, "
        "độ dài tương đương bản gốc; chữ trên màn hình ngắn gọn. Không dịch tên riêng/thương hiệu. Trả qua công cụ submit.")
    resp = llm.call(system, [{"role": "user", "content": f"Ngôn ngữ đích: {to_lang}\n" + json.dumps(payload, ensure_ascii=False)}],
                    tools=[tool], tool_choice={"type": "tool", "name": "submit"})
    out = next(b for b in resp.content if b.type == "tool_use").input["scenes"]
    by_id = {str(x.get("id")): x for x in out}
    new = manifest.strip_engine_fields(data)
    for s in new["scenes"]:
        tr = by_id.get(str(s["scene_id"]))
        if not tr:
            continue
        s["voice_text"] = tr.get("voice_text", s.get("voice_text"))
        s.setdefault("props", {}).update(tr.get("props") or {})
        for b, say in zip(s.get("acting") or [], tr.get("says") or []):
            if say:
                b["say"] = say
            if isinstance(b.get("at"), str) and not b["at"].endswith("%"):
                b["at"] = f"{round(_pct(b['at'], data, s), 0):.0f}%"  # từ gốc không còn trong bản dịch
    new["lang"] = to_lang
    new.pop("voice", None)
    dst = config.workspace() / f"{src.name}_{to_lang}"
    if dst.exists():
        shutil.rmtree(dst / "build", ignore_errors=True)
    (dst / "assets").mkdir(parents=True, exist_ok=True)
    for f in (src / "assets").glob("*"):
        if f.is_file() and not f.name.startswith("s0") and not f.suffix == ".wav":
            shutil.copy2(f, dst / "assets" / f.name)
    new["project_id"] = dst.name
    manifest.save(dst, new)
    print("📊 " + llm.usage.line())
    return dst


def _pct(at: str, data: dict, scene: dict) -> float:
    """Đổi mốc 'từ' sang % dựa trên timing bản gốc (nếu đã có)."""
    from ..align import resolve_at
    orig = next((s for s in data["scenes"] if s["scene_id"] == scene["scene_id"]), {})
    dur = orig.get("duration") or 1
    return 100 * resolve_at(at, orig.get("word_timings") or [], dur, 0) / dur
