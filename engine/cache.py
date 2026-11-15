"""Cache theo băm nội dung: chỉ làm lại cảnh nào thực sự đổi (0 token, tiết kiệm CPU)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FILE = ".vf_cache.json"


def digest(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path):
            h.update(p.read_bytes() if p.exists() else b"<missing>")
        else:
            h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode())
    return h.hexdigest()[:16]


class Cache:
    def __init__(self, project_dir: Path):
        self.path = project_dir / FILE
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}

    def fresh(self, key: str, h: str, output: Path) -> bool:
        return self.data.get(key) == h and output.exists() and output.stat().st_size > 0

    def put(self, key: str, h: str) -> None:
        self.data[key] = h
        self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
