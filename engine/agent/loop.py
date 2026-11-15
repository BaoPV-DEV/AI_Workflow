"""Vòng lặp agent tool-use tổng quát – phiên bản thu nhỏ của cách Claude Code làm việc.

  user -> model -> (tool_use...) -> chạy công cụ local -> tool_result -> model -> ... -> end_turn

Tiết kiệm token: lịch sử được cắt gọn (kết quả công cụ cũ thay bằng tóm tắt) và phần
system + tools được cache.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .llm import LLM


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., object]

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


class Agent:
    def __init__(self, llm: LLM, system: list[dict], tools: list[Tool], max_turns: int = 12,
                 on_event: Callable[[str], None] | None = None):
        self.llm, self.system, self.max_turns = llm, system, max_turns
        self.tools = {t.name: t for t in tools}
        self.messages: list[dict] = []
        self.emit = on_event or (lambda s: print(s, flush=True))

    def _run_tool(self, name: str, args: dict) -> tuple[str, bool]:
        t = self.tools.get(name)
        if not t:
            return f"Không có công cụ {name}", True
        try:
            out = t.fn(**args)
            return (out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)), False
        except Exception as e:
            return f"{type(e).__name__}: {e}", True

    def _compact(self) -> None:
        """Rút gọn kết quả công cụ đã cũ (giữ 2 lượt gần nhất) để không phình context."""
        user_turns = [i for i, m in enumerate(self.messages) if m["role"] == "user" and isinstance(m["content"], list)]
        for i in user_turns[:-2]:
            for b in self.messages[i]["content"]:
                if b.get("type") == "tool_result" and isinstance(b.get("content"), str) and len(b["content"]) > 200:
                    b["content"] = b["content"][:160] + " …(đã rút gọn)"

    def run(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        final = ""
        for turn in range(self.max_turns):
            self._compact()
            resp = self.llm.call(self.system, self.messages, tools=[t.spec() for t in self.tools.values()])
            self.messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
            texts = [b.text for b in resp.content if b.type == "text" and b.text.strip()]
            if texts:
                final = "\n".join(texts)
                self.emit("🤖 " + final)
            if resp.stop_reason != "tool_use":
                break
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    self.emit(f"  🔧 {b.name}({json.dumps(b.input, ensure_ascii=False)[:120]})")
                    out, err = self._run_tool(b.name, b.input)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out, **({"is_error": True} if err else {})})
            self.messages.append({"role": "user", "content": results})
        else:
            self.emit(f"⚠ Dừng sau {self.max_turns} lượt")
        self.emit("📊 " + self.llm.usage.line())
        return final
