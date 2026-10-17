"""The real HTTPS transport the provider adapters use: transport(url, headers, body, timeout_s) -> (status, parsed_json_or_None).

Standard library only. Never raises: any network problem is (0, None). Redirects are not followed. The body and answer are never logged.
Adapters call fixed provider URLs only; nothing a person typed becomes a URL.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def post_json(url: str, headers: dict, body: dict, timeout_s: int):
    if not url.startswith("https://"):
        return 0, None
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout_s) as resp:
            raw = resp.read(5_000_000)
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read(200_000)
        except Exception:
            raw = b""
    except Exception:
        return 0, None
    try:
        return status, json.loads(raw.decode("utf-8"))
    except Exception:
        return status, None
