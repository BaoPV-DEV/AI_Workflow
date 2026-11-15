"""Công cụ thao tác manifest cho agent. Trả về JSON gọn nhất có thể (tiết kiệm token)."""
from __future__ import annotations

import json
from pathlib import Path

from .. import catalog, manifest
from .loop import Tool


def _find(data: dict, scene_id) -> tuple[int, dict]:
    for i, s in enumerate(data["scenes"]):
        if str(s.get("scene_id")) == str(scene_id):
            return i, s
    raise KeyError(f"Không có scene_id {scene_id}")


def _merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if v is None:
            a.pop(k, None)
        elif isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def manifest_tools(project_dir: Path) -> list[Tool]:
    def load():
        return manifest.load(project_dir)[1]

    def save(data):
        manifest.save(project_dir, data)
        errs = manifest.validate(data)
        return {"ok": not errs, "errors": errs[:8]}

    def list_scenes():
        d = load()
        head = {k: d.get(k) for k in ("project_id", "style", "aspect_ratio", "lang") if d.get(k)}
        head["cast"] = list((d.get("cast") or {}).keys())
        rows = [f"{s.get('scene_id')}|{s.get('visual_type')}|{s.get('template_name', '')}|{(s.get('voice_text') or '')[:60]}"
                for s in d["scenes"]]
        return json.dumps(head, ensure_ascii=False) + "\n" + "\n".join(rows)

    def get_scene(scene_id):
        _, s = _find(load(), scene_id)
        return {k: v for k, v in s.items() if k not in manifest.ENGINE_FIELDS + ("speech",)}

    def update_scene(scene_id, patch):
        d = load()
        _, s = _find(d, scene_id)
        if "voice_text" in patch:  # lời đổi -> phải đọc lại
            for k in manifest.ENGINE_FIELDS + ("speech",):
                s.pop(k, None)
        _merge(s, patch)
        return save(d)

    def add_scene(after_id, scene):
        d = load()
        i = -1 if after_id in (None, 0, "0") else _find(d, after_id)[0]
        ids = [s["scene_id"] for s in d["scenes"] if isinstance(s.get("scene_id"), int)]
        scene.setdefault("scene_id", max(ids, default=0) + 1)
        d["scenes"].insert(i + 1, scene)
        return {**save(d), "scene_id": scene["scene_id"]}

    def delete_scene(scene_id):
        d = load()
        i, _ = _find(d, scene_id)
        d["scenes"].pop(i)
        return save(d)

    def set_project(fields):
        d = load()
        _merge(d, {k: v for k, v in fields.items() if k != "scenes"})
        return save(d)

    def get_catalog():
        return catalog.text()

    def validate():
        errs = manifest.validate(load())
        return {"ok": not errs, "errors": errs}

    S = lambda props, req=(): {"type": "object", "properties": props, "required": list(req)}
    ID = {"type": ["integer", "string"]}
    return [
        Tool("list_scenes", "Danh sách cảnh rút gọn: id|visual_type|template|đầu lời đọc. Gọi đầu tiên.", S({}), list_scenes),
        Tool("get_scene", "Xem đầy đủ 1 cảnh (không gồm timing).", S({"scene_id": ID}, ["scene_id"]), get_scene),
        Tool("update_scene", "Sửa 1 cảnh bằng patch gộp sâu (giá trị null = xoá trường). Chỉ gửi trường cần đổi.",
             S({"scene_id": ID, "patch": {"type": "object"}}, ["scene_id", "patch"]), update_scene),
        Tool("add_scene", "Chèn cảnh mới sau after_id (0 = đầu video).", S({"after_id": ID, "scene": {"type": "object"}}, ["after_id", "scene"]), add_scene),
        Tool("delete_scene", "Xoá 1 cảnh.", S({"scene_id": ID}, ["scene_id"]), delete_scene),
        Tool("set_project", "Sửa trường cấp project: style, aspect_ratio, cast, music, voice, lang.", S({"fields": {"type": "object"}}, ["fields"]), set_project),
        Tool("get_catalog", "Template/props/act/style hợp lệ. Chỉ gọi khi cần tên chưa biết.", S({}), get_catalog),
        Tool("validate", "Kiểm tra manifest.", S({}), validate),
    ]
