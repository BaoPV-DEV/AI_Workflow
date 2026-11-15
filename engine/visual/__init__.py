"""Adapter tầng hình ảnh (Plug & Play). Thêm adapter mới: viết class kế thừa Adapter rồi @register."""
from .base import Adapter, Job, get, register  # noqa: F401
from . import html, media, comfyui  # noqa: F401  (đăng ký adapter)
