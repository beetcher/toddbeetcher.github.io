"""Claude through Anthropic's Messages API. The key comes from the server's settings by the NAME on the model record.

`secret_fn(name)` returns the key or None. Web search uses Anthropic's web_search tool with max_uses set to the step's search limit.
UNVERIFIED AGAINST THE LIVE SERVICE until step 7 (model swap); request and usage field names follow Anthropic's documentation.
"""
from __future__ import annotations

from discovery.contract import ProviderRequest, ProviderResult

from . import from_status, whole

URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"
SEARCH_TOOL = "web_search_20250305"


class ClaudeProvider:
    name = "claude"

    def __init__(self, transport, secret_fn):
        self.transport, self.secret_fn = transport, secret_fn

    def generate(self, request: ProviderRequest) -> ProviderResult:
        try:
            key = self.secret_fn(request.key_name) if request.key_name else None
            if not key:
                return ProviderResult("rejected", error_code="key_missing")
            body = {"model": request.model_name, "max_tokens": request.max_output_tokens,
                    "messages": [{"role": "user", "content": request.prompt}]}
            if request.use_grounding and request.max_searches > 0:
                body["tools"] = [{"type": SEARCH_TOOL, "name": "web_search", "max_uses": request.max_searches}]
            status, data = self.transport(URL, {"x-api-key": key, "anthropic-version": VERSION}, body, request.timeout_s)
            failed = from_status(status)
            if failed:
                return failed
            text = "".join(b.get("text", "") for b in data.get("content", []) if isinstance(b, dict) and b.get("type") == "text")
            use = data.get("usage") or {}
            searches = whole((use.get("server_tool_use") or {}).get("web_search_requests"))
            if not text:
                return ProviderResult("no_answer", error_code="unreadable_reply", input_tokens=whole(use.get("input_tokens")),
                                      output_tokens=whole(use.get("output_tokens")), searches=searches)
            return ProviderResult("ok", text=text, input_tokens=whole(use.get("input_tokens")), output_tokens=whole(use.get("output_tokens")),
                                  searches=searches)
        except Exception:
            return ProviderResult("no_answer", error_code="provider_unavailable")
