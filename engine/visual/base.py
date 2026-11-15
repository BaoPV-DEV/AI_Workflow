from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_REGISTRY: dict[str, type["Adapter"]] = {}


@dataclass
class Job:
    """Mọi thứ một adapter cần để quay 1 cảnh thành clip không tiếng."""
    scene: dict
    project_dir: Path
    out: Path
    width: int
    height: int
    fps: int
    duration: float
    style: dict
    cast: dict = field(default_factory=dict)
    encoder: str = "libx264"
    crf: int = 20
    preset: str = "veryfast"
    draft: bool = False


class Adapter:
    visual_types: tuple[str, ...] = ()

    def render(self, job: Job) -> Path:  # pragma: no cover - interface
        raise NotImplementedError

    def fingerprint(self, job: Job) -> list:
        """Thứ làm thay đổi kết quả (để cache). Adapter có thể bổ sung file template..."""
        return []


def register(cls: type[Adapter]) -> type[Adapter]:
    for vt in cls.visual_types:
        _REGISTRY[vt] = cls
    return cls


def get(visual_type: str) -> Adapter:
    if visual_type not in _REGISTRY:
        raise ValueError(f"Không có adapter cho visual_type '{visual_type}'. Có: {', '.join(_REGISTRY)}")
    return _REGISTRY[visual_type]()
