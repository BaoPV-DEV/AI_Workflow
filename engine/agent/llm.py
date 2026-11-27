"""Gọi Claude API với prompt caching, định tuyến model theo vai trò và sổ ghi token."""
from __future__ import annotations

import json
import os
import re
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
        self.model = api_model(role)
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


# ======================================================================
#  Chọn "bộ não": API key  |  Claude Code (gói Pro/Max)  |  thủ công
# ======================================================================
import shutil
import subprocess

DEFAULT_TIER = {"plan": "opus", "ideas": "sonnet", "edit": "haiku", "translate": "haiku", "subtitles": "haiku", "publish": "haiku", "audit": "sonnet"}


def tier(role: str) -> str:
    a = config.settings().get("agent", {})
    return (a.get("tiers") or {}).get(role) or (a.get("cli_models") or {}).get(role) or DEFAULT_TIER.get(role, "sonnet")


def api_model(role: str) -> str:
    a = config.settings().get("agent", {})
    legacy = (a.get("models") or {}).get(role)
    if legacy and not (a.get("tiers") or {}).get(role):
        return legacy
    t = tier(role)
    return (a.get("models_by_tier") or {}).get(t) or {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}.get(t, t)


class NoBackend(RuntimeError):
    pass


def claude_cli() -> str | None:
    exe = shutil.which("claude")
    if exe:
        return exe
    import os
    for p in (os.path.expanduser("~/.local/bin/claude.exe"), os.path.expanduser("~/.local/bin/claude")):
        if os.path.exists(p):
            return p
    return None


def backend() -> str:
    """api (ANTHROPIC_API_KEY) | cli (Claude Code đăng nhập bằng tài khoản Claude) | manual."""
    import os
    want = config.settings().get("agent", {}).get("backend", "auto")
    if want != "auto":
        return want
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "api"
    if claude_cli():
        return "cli"
    return "manual"


MANUAL_HELP = ("Chưa có bộ não AI để gọi tự động. Chọn một trong các cách:\n"
               "  1) Claude Desktop: chạy `vf mcp-install`, mở lại Claude Desktop và chat \"làm video về ...\"\n"
               "  2) Claude Code (gói Pro/Max): cài bằng `irm https://claude.ai/install.ps1 | iex`, chạy `claude` để đăng nhập\n"
               "  3) Không cài gì: `vf prompt \"chủ đề\"` → dán vào claude.ai → `vf import`\n"
               "  4) API key: đặt ANTHROPIC_API_KEY")


def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        a = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
        b = max(text.rfind("}"), text.rfind("]"))
        if a < 0 or b < a:
            raise ValueError("Không thấy JSON trong câu trả lời")
        text = text[a:b + 1]
    return json.loads(text)


def run_cli(prompt: str, role: str = "plan", tools: str = "", cwd: str | None = None,
            permission: str | None = None, timeout: int = 900, system_extra: str = "") -> dict:
    """Gọi Claude Code ở chế độ không giao diện; prompt đi qua stdin (tránh giới hạn độ dài dòng lệnh)."""
    exe = claude_cli()
    if not exe:
        raise NoBackend(MANUAL_HELP)
    a = config.settings().get("agent", {})
    model = tier(role)
    cmd = [exe, "-p", "Làm đúng theo yêu cầu trong nội dung được cung cấp qua stdin.",
           "--output-format", "json", "--model", model]
    if tools:
        cmd += ["--allowedTools", tools]
    else:
        cmd += ["--disallowedTools", "Bash,Edit,Write,NotebookEdit"]
    if permission:
        cmd += ["--permission-mode", permission]
    if system_extra:
        cmd += ["--append-system-prompt", system_extra]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=cwd or str(config.ROOT), timeout=timeout)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude Code lỗi (mã {r.returncode}): {(r.stderr or r.stdout)[-600:]}\n"
                           "Đã đăng nhập chưa? Mở PowerShell, gõ `claude` một lần để đăng nhập.")
    if out.get("is_error"):
        msg = str(out.get("result"))[:600]
        if re.search(r"authenticat|oauth|login|401|expired|credential", msg, re.I):
            msg += ("\n→ Phiên đăng nhập Claude Code đã hết hạn. Mở PowerShell, gõ `claude`, rồi gõ /login và đăng nhập"
                    " bằng tài khoản Claude (Pro/Max). Xong gõ /exit và bấm lại nút này, không cần mở lại Studio.")
        raise RuntimeError(f"Claude Code báo lỗi: {msg}")
    _log_cli(out, model)
    return out


def _log_cli(out: dict, model: str) -> None:
    path = config.workspace() / ".usage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    u = out.get("usage") or {}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "model": f"cli:{model}",
                            "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
                            "cache_read": u.get("cache_read_input_tokens", 0),
                            "cache_write": u.get("cache_creation_input_tokens", 0)}) + "\n")


def complete_json(role: str, system: list[str], user: str, schema: dict, name: str = "submit",
                  web: bool = False, repair=None, tries: int = 3):
    """Một lần hỏi → JSON theo schema, qua API (ép công cụ) hoặc Claude Code CLI.
    repair(data) -> list lỗi; nếu có lỗi sẽ hỏi lại kèm danh sách lỗi."""
    be = backend()
    if be == "manual":
        raise NoBackend(MANUAL_HELP)
    if be == "api":
        llm = LLM(role)
        sys_blocks = llm.cached_system(*system)
        tool = {"name": name, "description": "Nộp kết quả", "input_schema": schema}
        msgs = [{"role": "user", "content": user}]
        data = None
        for _ in range(tries):
            resp = llm.call(sys_blocks, msgs, tools=[tool], tool_choice={"type": "tool", "name": name})
            use = next(b for b in resp.content if b.type == "tool_use")
            data = use.input
            errs = repair(data) if repair else []
            if not errs:
                break
            msgs += [{"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]},
                     {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                                   "content": "Sửa các lỗi sau rồi nộp lại toàn bộ:\n" + "\n".join(errs[:15])}]}]
        print("📊 " + llm.usage.line(), flush=True)
        return data
    # ---- cli
    base = ("\n\n".join(s for s in system if s) + "\n\n" + user +
            "\n\nTRẢ LỜI: chỉ một khối ```json hợp lệ theo JSON Schema sau, không thêm lời nào khác:\n" +
            json.dumps(schema, ensure_ascii=False))
    prompt, data = base, None
    for _ in range(tries):
        out = run_cli(prompt, role, tools="WebSearch,WebFetch" if web else "")
        data = _extract_json(out.get("result", ""))
        errs = repair(data) if repair else []
        if not errs:
            break
        prompt = base + "\n\nLẦN TRƯỚC BẠN TRẢ VỀ:\n```json\n" + json.dumps(data, ensure_ascii=False) + \
            "\n```\nLỖI CẦN SỬA:\n" + "\n".join(errs[:15]) + "\nHãy trả lại TOÀN BỘ JSON đã sửa."
    print(f"📊 Claude Code ({out.get('num_turns', 1)} lượt, {out.get('duration_ms', 0) / 1000:.0f}s)", flush=True)
    return data
