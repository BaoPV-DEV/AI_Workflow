"""Chế độ tự động: xu hướng → ý tưởng → kịch bản → (dịch) → giọng → render → báo cáo.

Cần bộ não tự gọi được: Claude Code (tài khoản Claude Pro/Max) hoặc API key.
Claude Desktop (MCP) thì làm từng bước trong chat thay vì lệnh này.
"""
from __future__ import annotations

import datetime as dt
import json

from . import config, pipeline
from .agent import director
from .util import log


def run(geo: str = "VN", lang: str = "vi", count: int = 2, genre: str | None = None, langs: list[str] | None = None,
        seconds: int = 45, style: str | None = None, aspect: str | None = None, niche: str = "",
        render: bool = True, draft: bool = False, topics: list[str] | None = None) -> dict:
    report = {"started": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "geo": geo, "lang": lang, "videos": []}
    if topics:
        picks = [{"topic": t, "genre": genre or "animation", "hook": "", "angle": "", "score": 0} for t in topics]
    else:
        log(f"🔎 Tìm xu hướng ({geo}, {lang}) và chấm điểm ý tưởng…")
        res = director.ideas(geo, lang, count=max(count * 2, 5), genre=genre, niche=niche)
        report["ideas"] = res.get("ideas", [])
        picks = [i for i in res.get("ideas", []) if i.get("risk") != "high"][:count]
        for i in res.get("ideas", []):
            log(f"   {i.get('score', 0):>2}/10 [{i.get('risk', '?')}] {i['topic']}")
    if not picks:
        raise RuntimeError("Không có ý tưởng an toàn nào để làm.")

    for n, idea in enumerate(picks, 1):
        entry = {"topic": idea["topic"], "idea": idea, "projects": []}
        report["videos"].append(entry)
        log(f"\n🎬 [{n}/{len(picks)}] {idea['topic']}")
        try:
            notes = "; ".join(x for x in (idea.get("hook") and f"hook gợi ý: {idea['hook']}",
                                            idea.get("angle") and f"góc: {idea['angle']}",
                                            idea.get("title") and f"tiêu đề: {idea['title']}") if x)
            d, errs = director.plan(idea["topic"], genre=idea.get("genre") or genre or "animation",
                                    style=style or idea.get("style") or None, aspect=aspect, lang=lang, seconds=seconds,
                                    notes=notes, facts="; ".join(idea.get("facts_to_check") or []) or None)
            if errs:
                log("   ⚠ kịch bản còn lỗi, bỏ qua: " + "; ".join(errs[:3]))
                entry["error"] = errs
                continue
            targets = [d]
            for L in langs or []:
                log(f"   🌐 dịch sang {L}")
                targets.append(director.translate(d, L))
            for t in targets:
                item = {"project": t.name}
                pipeline.voice(t)
                if render:
                    item["video"] = str(pipeline.render(t, draft=draft))
                entry["projects"].append(item)
        except Exception as e:  # một video lỗi không làm hỏng cả lượt
            entry["error"] = f"{type(e).__name__}: {e}"
            log(f"   ✘ {entry['error']}")

    out = config.workspace() / "_auto"
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    (out / f"{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Lượt tự động {report['started']} ({geo}, {lang})", ""]
    for v in report["videos"]:
        md.append(f"## {v['topic']}")
        if v.get("idea", {}).get("why_now"):
            md.append(f"- Vì sao lúc này: {v['idea']['why_now']}")
        for p in v["projects"]:
            md.append(f"- {p['project']}: {p.get('video', '(chưa render)')}")
        if v.get("error"):
            md.append(f"- Lỗi: {v['error']}")
        if v.get("idea", {}).get("facts_to_check"):
            md.append("- Cần kiểm tra lại trước khi đăng: " + "; ".join(v["idea"]["facts_to_check"]))
        md.append("")
    (out / f"{stamp}.md").write_text("\n".join(md), encoding="utf-8")
    log(f"\n📄 Báo cáo: {out / (stamp + '.md')}")
    return report
