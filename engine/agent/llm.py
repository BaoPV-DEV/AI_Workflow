"""Gọi Claude API với prompt caching, định tuyến model theo vai trò và sổ ghi token."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from .. import config


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    calls: int = 0
    by_model: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    def add(self, model: str, u) -> None:
        d = {"input": u.input_tokens or 0, "output": u.output_tokens or 0,
             "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        self.input += d["input"]; self.output += d["output"]
        self.cache_read += d["cache_read"]; self.cache_write += d["cache_write"]
        self.calls += 1
        m = self.by_model.setdefault(model, {k: 0 for k in d})
        for k, v in d.items():
            m[k] += v

    def cost(self) -> float | None:
        prices = config.settings().get("agent", {}).get("prices", {})
        total = 0.0
        for model, d in self.by_model.items():
            p = prices.get(model) or {}
            if any(p.get(k) is None for k in ("input", "output")):
                return None
            total += sum(d[k] * (p.get(k) or 0) for k in d) / 1e6
        return total

    def line(self) -> str:
        c = self.cost()
        hit = self.cache_read / max(1, self.cache_read + self.cache_write + self.input) * 100
        return (f"token: vào {self.input:,} · ra {self.output:,} · cache đọc {self.cache_read:,} ({hit:.0f}%) · "
                f"cache ghi {self.cache_write:,} · {self.calls} lần gọi" + (f" · ≈ ${c:.4f}" if c is not None else ""))


class LLM:
    def __init__(self, role: str = "plan"):
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError("pip install anthropic  (hoặc dùng chế độ không API: vf prompt / vf import)") from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Chưa đặt ANTHROPIC_API_KEY. Không có key? Dùng: vf prompt ... rồi dán vào claude.ai, sau đó vf import")
        self.client = anthropic.Anthropic()
        a = config.settings().get("agent", {})
        self.model = a.get("models", {}).get(role, "claude-sonnet-5-5")
        self.max_tokens = a.get("max_tokens", 8000)
        self.budget = a.get("budget_tokens_per_run", 60000)
        self.usage = Usage()

    @staticmethod
    def cached_system(*blocks: str) -> list[dict]:
        """Phần tĩnh (quy tắc, catalog, schema) đặt trước và gắn cache_control ở khối cuối:
        lần gọi sau chỉ trả ~10% giá cho phần này."""
        out = [{"type": "text", "text": b} for b in blocks if b]
        if out:
            out[-1]["cache_control"] = {"type": "ephemeral"}
        return out

    @staticmethod
    def cached_tools(tools: list[dict]) -> list[dict]:
        tools = [dict(t) for t in tools]
        if tools:
            tools[-1]["cache_control"] = {"type": "ephemeral"}
        return tools

    def call(self, system: list[dict], messages: list[dict], tools: list[dict] | None = None,
             tool_choice: dict | None = None, max_tokens: int | None = None):
        if self.usage.total > self.budget:
            raise RuntimeError(f"Vượt ngân sách {self.budget:,} token cho lần chạy này ({self.usage.line()})")
        kw = dict(model=self.model, max_tokens=max_tokens or self.max_tokens, system=system, messages=messages)
        if tools:
            kw["tools"] = self.cached_tools(tools)
        if tool_choice:
            kw["tool_choice"] = tool_choice
        for attempt in range(4):
            try:
                resp = self.client.messages.create(**kw)
                break
            except Exception as e:  # quá tải / mạng: thử lại có giãn cách
                status = getattr(e, "status_code", None)
                if attempt == 3 or (status and status < 500 and status != 429):
                    raise
                time.sleep(2 ** attempt * 2)
        self.usage.add(self.model, resp.usage)
        self._log(resp)
        return resp

    def _log(self, resp) -> None:
        path = config.workspace() / ".usage.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        u = resp.usage
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "model": self.model,
                                "in": u.input_tokens, "out": u.output_tokens,
                                "cache_read": getattr(u, "cache_read_input_tokens", 0),
                                "cache_write": getattr(u, "cache_creation_input_tokens", 0)}) + "\n")
