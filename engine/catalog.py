"""Sinh catalog cực gọn (~600 token) cho Claude thay vì để Claude đọc từng file template.

Nguồn duy nhất: thẻ <script data-doc> trong mỗi template, styles/*.yaml, library/*.json.
"""
from __future__ import annotations

import json
import re

from . import config


def templates(with_demo: bool = False) -> dict[str, dict]:
    out = {}
    for p in sorted((config.TEMPLATES / "html_scenes").glob("*.html")):
        src = p.read_text(encoding="utf-8")
        m = re.search(r'<script type="application/json" data-doc>\s*(\{.*?\})\s*</script>', src, re.S)
        if m and p.stem != "svg_wrapper":
            out[p.stem] = json.loads(m.group(1))
            if with_demo:
                d = re.search(r'<script type="application/json" data-demo>\s*(\{.*?\})\s*</script>', src, re.S)
                out[p.stem]["demo"] = json.loads(d.group(1)).get("props", {}) if d else {}
    return out


def text(compact: bool = True) -> str:
    lines = ["# CATALOG (sinh tự động bởi `vf catalog` – không sửa tay)", "", "## Templates (visual_type: html_animation)"]
    for name, d in templates().items():
        props = "; ".join(f"{k}: {v}" for k, v in d.get("props", {}).items())
        lines.append(f"- **{name}** – {d['desc']} | props: {props}" + (f" | cần: {d['needs']}" if d.get("needs") else ""))
    lines += ["", "## visual_type khác",
              "- svg_graphic: svg_code (SVG tự vẽ, viewBox theo khung; animation CSS được hỗ trợ)",
              "- image: src (file trong assets/), camera: zoom_in|zoom_out|pan_left|pan_right",
              "- video: src (clip trong assets/) · comfyui: prompt, workflow · color: props.color",
              "", "## Styles (manifest.style)"]
    for s in config.list_styles():
        lines.append(f"- {s}: {config.style(s).get('label', '')}")
    chars = config.library("characters")["characters"]
    acts = config.library("actions")
    lines += ["", "## Nhân vật (cast.<Tên>.preset)", ", ".join(chars),
              "", "## Acting (scene.acting[] cho stickman_stage)",
              "beat = {at: 'từ trong lời đọc'|'60%'|giây, act, who?, move?, mood?, hold?, say?, face?}",
              "act: " + ", ".join(acts["actions"]),
              "move: enter_left, enter_right, exit_left, exit_right, left, center, right, stay",
              "mood: neutral, happy, sad, surprised, angry, scared, tired, curious, proud",
              "hold: book, phone, coin, money, gift, bulb, sign, laptop, cup, flag, sword, key, star, trophy, magnifier, map, briefcase"]
    return "\n".join(lines) + "\n"


def write() -> str:
    out = config.ROOT / "CATALOG.md"
    t = text()
    out.write_text(t, encoding="utf-8")
    return t
