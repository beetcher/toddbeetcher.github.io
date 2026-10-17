"""OpenAI through the Responses API. The key comes from the server's settings by the NAME on the model record.

Web search uses the web_search tool; `max_tool_calls` limits searches. Each search is billed, so the count comes from the web_search_call
items in the reply. UNVERIFIED AGAINST THE LIVE SERVICE until a live check; field names follow OpenAI's documentation.
"""
from __future__ import annotations

from discovery.contract import ProviderRequest, ProviderResult

from . import from_status, whole

URL = "https://api.openai.com/v1/responses"


class OpenAIProvider:
    name = "openai"

    def __init__(self, transport, secret_fn):
        self.transport, self.secret_fn = transport, secret_fn

    def generate(self, request: ProviderRequest) -> ProviderResult:
        try:
            key = self.secret_fn(request.key_name) if request.key_name else None
            if not key:
                return ProviderResult("rejected", error_code="key_missing")
            body = {"model": request.model_name, "input": request.prompt, "max_output_tokens": request.max_output_tokens}
            if request.use_grounding and request.max_searches > 0:
                body["tools"] = [{"type": "web_search"}]
                body["max_tool_calls"] = request.max_searches
            status, data = self.transport(URL, {"Authorization": f"Bearer {key}"}, body, request.timeout_s)
            failed = from_status(status)
            if failed:
                return failed
            out = data.get("output") or []
            text = "".join(c.get("text", "") for item in out if isinstance(item, dict) and item.get("type") == "message"
                           for c in item.get("content", []) if isinstance(c, dict) and c.get("type") == "output_text")
            searches = sum(1 for item in out if isinstance(item, dict) and item.get("type") == "web_search_call")
            use = data.get("usage") or {}
            if not text:
                return ProviderResult("no_answer", error_code="unreadable_reply", input_tokens=whole(use.get("input_tokens")),
                                      output_tokens=whole(use.get("output_tokens")), searches=searches)
            return ProviderResult("ok", text=text, input_tokens=whole(use.get("input_tokens")), output_tokens=whole(use.get("output_tokens")),
                                  searches=searches)
        except Exception:
            return ProviderResult("no_answer", error_code="provider_unavailable")
