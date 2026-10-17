"""Gemini through the Google Cloud project (Vertex AI generateContent). No API key: the server's own service account signs in.

`token_fn()` returns a Google access token string (the real one uses google-auth application default credentials with the
cloud-platform scope; see build.py); `project` is the Google project id. Grounding with Google Search is switched on with the
`googleSearch` tool when the model has it. Reported output tokens = answer tokens + thinking tokens, because both are billed.
UNVERIFIED AGAINST THE LIVE SERVICE until step 5 (live check on Todd's Mac): endpoint shape and field names follow Google's REST reference.
"""
from __future__ import annotations

from discovery.contract import ProviderRequest, ProviderResult

from . import from_status, whole

HOST = "https://aiplatform.googleapis.com"


class GeminiProvider:
    name = "gemini"

    def __init__(self, transport, token_fn, project: str, location: str = "global"):
        self.transport, self.token_fn, self.project, self.location = transport, token_fn, project, location

    def generate(self, request: ProviderRequest) -> ProviderResult:
        try:
            if not self.project:
                return ProviderResult("rejected", error_code="key_missing")
            token = self.token_fn()
            if not token:
                return ProviderResult("rejected", error_code="auth_failed")
            url = (f"{HOST}/v1/projects/{self.project}/locations/{self.location}/publishers/google/models/"
                   f"{request.model_name}:generateContent")
            body = {"contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
                    "generationConfig": {"maxOutputTokens": request.max_output_tokens, "temperature": 0.2}}
            if request.use_grounding:
                body["tools"] = [{"googleSearch": {}}]
            status, data = self.transport(url, {"Authorization": f"Bearer {token}"}, body, request.timeout_s)
            failed = from_status(status)
            if failed:
                return failed
            cand = (data.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if isinstance(p, dict))
            use = data.get("usageMetadata") or {}
            searches = len((cand.get("groundingMetadata") or {}).get("webSearchQueries") or [])
            if not text:
                return ProviderResult("no_answer", error_code="unreadable_reply", input_tokens=whole(use.get("promptTokenCount")),
                                      output_tokens=whole(use.get("candidatesTokenCount")) + whole(use.get("thoughtsTokenCount")),
                                      searches=searches)
            return ProviderResult("ok", text=text, input_tokens=whole(use.get("promptTokenCount")),
                                  output_tokens=whole(use.get("candidatesTokenCount")) + whole(use.get("thoughtsTokenCount")),
                                  searches=searches)
        except Exception:
            return ProviderResult("no_answer", error_code="provider_unavailable")
