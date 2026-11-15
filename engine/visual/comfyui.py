"""ComfyUI headless (local RTX hoặc RunPod/Vast). Trỏ visual.comfyui_url sang endpoint đang thuê.

Workflow: xuất từ ComfyUI bằng "Save (API Format)" vào templates/comfy_workflows/<tên>.json.
Trong file, đặt chuỗi {{prompt}}, {{width}}, {{height}}, {{seed}} ở chỗ cần thay.
Kết quả ảnh -> Ken Burns; kết quả video (Wan/LTX/AnimateDiff) -> cắt đúng thời lượng.
"""
from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config
from .base import Adapter, Job, register
from .media import VideoAdapter, kenburns


def _http(url: str, data: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


@register
class ComfyAdapter(Adapter):
    visual_types = ("comfyui",)

    def fingerprint(self, job: Job) -> list:
        wf = config.TEMPLATES / "comfy_workflows" / f"{job.scene.get('workflow', 'sdxl_image')}.json"
        return [wf, job.scene.get("prompt"), job.scene.get("seed")]

    def render(self, job: Job) -> Path:
        base = config.settings()["visual"]["comfyui_url"].rstrip("/")
        name = job.scene.get("workflow", "sdxl_image")
        wf_text = (config.TEMPLATES / "comfy_workflows" / f"{name}.json").read_text(encoding="utf-8")
        seed = job.scene.get("seed", random.randint(1, 2**31))
        prompt = (job.scene.get("prompt") or "") + ", " + job.style.get("image_prompt_suffix", "")
        for k, v in {"prompt": json.dumps(prompt)[1:-1], "width": job.width, "height": job.height, "seed": seed}.items():
            wf_text = wf_text.replace("{{" + k + "}}", str(v))
        pid = json.loads(_http(f"{base}/prompt", {"prompt": json.loads(wf_text)}))["prompt_id"]
        for _ in range(900):  # tối đa ~30 phút
            hist = json.loads(_http(f"{base}/history/{pid}")).get(pid)
            if hist and hist.get("outputs"):
                break
            time.sleep(2)
        else:
            raise TimeoutError("ComfyUI không trả kết quả")
        files = [f for o in hist["outputs"].values() for key in ("images", "gifs", "videos") for f in o.get(key, [])]
        if not files:
            raise RuntimeError("Workflow không có node lưu ảnh/video")
        f = files[-1]
        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
        dest = job.project_dir / "assets" / "gen" / f"{job.out.stem}_{f['filename']}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_http(f"{base}/view?{q}"))
        if dest.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            return kenburns(job, dest, job.scene.get("camera") or "zoom_in")
        job.scene = {**job.scene, "src": str(dest)}
        return VideoAdapter().render(job)
