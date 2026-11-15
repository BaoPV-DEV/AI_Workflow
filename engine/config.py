"""Đọc settings.yaml, style và thư viện. Mọi module lấy cấu hình qua đây."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
TEMPLATES = ROOT / "templates"
LIBRARY = ROOT / "library"
SCHEMA = ROOT / "schema" / "manifest.schema.json"

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}


@lru_cache
def settings() -> dict:
    data = yaml.safe_load((CONFIG / "settings.yaml").read_text(encoding="utf-8")) or {}
    local = CONFIG / "settings.local.yaml"  # ghi đè riêng máy, bị git ignore
    if local.exists():
        _merge(data, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return data


def _merge(base: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v


def workspace() -> Path:
    return ROOT / settings().get("workspace", "workspace")


@lru_cache
def style(name: str) -> dict:
    path = CONFIG / "styles" / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Không có style '{name}'. Có: {', '.join(list_styles())}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_styles() -> list[str]:
    return sorted(p.stem for p in (CONFIG / "styles").glob("*.yaml"))


@lru_cache
def library(name: str) -> dict:
    return json.loads((LIBRARY / f"{name}.json").read_text(encoding="utf-8"))


def resolution(manifest: dict) -> tuple[int, int]:
    if manifest.get("resolution"):
        w, h = manifest["resolution"].split("x")
        return int(w), int(h)
    return ASPECTS[manifest.get("aspect_ratio") or settings().get("default_aspect", "9:16")]
