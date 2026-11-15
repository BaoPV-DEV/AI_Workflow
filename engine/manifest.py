"""Tải, kiểm tra và lưu project_manifest.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config

MANIFEST = "project_manifest.json"
ENGINE_FIELDS = ("audio_path", "duration", "word_timings")


class ManifestError(ValueError):
    pass


def project_dir(project: str | Path) -> Path:
    p = Path(project)
    if p.is_dir():
        return p.resolve()
    cand = config.workspace() / str(project)
    if cand.is_dir():
        return cand
    raise ManifestError(f"Không tìm thấy project '{project}' (đã thử {cand})")


def load(project: str | Path) -> tuple[Path, dict]:
    d = project_dir(project)
    path = d / MANIFEST
    if not path.exists():
        raise ManifestError(f"Thiếu {path}")
    data = parse(path.read_text(encoding="utf-8"))
    return d, data


def parse(text: str) -> dict:
    """Nhận JSON, kể cả khi bị bọc trong ```json ... ``` (dán từ chat)."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ManifestError(f"JSON lỗi dòng {e.lineno} cột {e.colno}: {e.msg}") from e


def save(d: Path, data: dict) -> Path:
    path = d / MANIFEST
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def validate(data: dict) -> list[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ). Gồm cả lỗi schema và lỗi ngữ nghĩa."""
    errors: list[str] = []
    try:
        import jsonschema

        schema = json.loads(config.SCHEMA.read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator(schema)
        for err in sorted(v.iter_errors(data), key=lambda e: list(e.path)):
            loc = "/".join(str(x) for x in err.path) or "(gốc)"
            errors.append(f"{loc}: {err.message}")
    except ImportError:
        pass

    ids = set()
    templates = {p.stem for p in (config.TEMPLATES / "html_scenes").glob("*.html")}
    acts = set(config.library("actions")["actions"]) | set(config.library("actions").get("aliases", {}))
    cast = set((data.get("cast") or {}).keys())
    for i, s in enumerate(data.get("scenes", [])):
        sid = s.get("scene_id", i + 1)
        if sid in ids:
            errors.append(f"scenes/{i}: scene_id {sid} bị trùng")
        ids.add(sid)
        vt = s.get("visual_type")
        if vt == "html_animation":
            t = s.get("template_name")
            if t not in templates:
                errors.append(f"scenes/{i}: template '{t}' không có. Có: {', '.join(sorted(templates))}")
        if vt == "svg_graphic" and not s.get("svg_code"):
            errors.append(f"scenes/{i}: svg_graphic cần svg_code")
        if vt in ("image", "video") and not s.get("src"):
            errors.append(f"scenes/{i}: {vt} cần src")
        for b in s.get("acting", []) or []:
            if b.get("act") not in acts:
                errors.append(f"scenes/{i}: act '{b.get('act')}' không có trong library/actions.json")
            if b.get("who") and b["who"] not in cast:
                errors.append(f"scenes/{i}: who '{b['who']}' không có trong cast")
    return errors


def scene_key(scene: dict) -> str:
    sid = scene.get("scene_id")
    return f"s{sid:03d}" if isinstance(sid, int) else str(sid)


def strip_engine_fields(data: dict) -> dict:
    """Bản rút gọn để gửi cho Claude: bỏ timing/âm thanh, tiết kiệm token."""
    out = {k: v for k, v in data.items() if k != "scenes"}
    out["scenes"] = [{k: v for k, v in s.items() if k not in ENGINE_FIELDS} for s in data.get("scenes", [])]
    return out
