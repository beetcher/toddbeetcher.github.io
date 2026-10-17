#!/usr/bin/env python3
"""Tests for the AI-company adapters (launch_discovery/providers/): request shape, reply reading, error mapping, no key or provider text
ever returned, and the core's provider contract kit. A fake transport stands in for the network; nothing is called.
Run from enjoy_router/:  python3 run_discovery_providers_tests.py   (-v lists every check)."""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from discovery import contract_kit  # noqa: E402
from discovery.contract import ProviderRequest  # noqa: E402
from launch_discovery import http_transport  # noqa: E402
from launch_discovery.providers import CODES  # noqa: E402
from launch_discovery.providers.build import build_providers  # noqa: E402
from launch_discovery.providers.claude import ClaudeProvider  # noqa: E402
from launch_discovery.providers.gemini import GeminiProvider  # noqa: E402
from launch_discovery.providers.openai import OpenAIProvider  # noqa: E402

fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

SECRET = "sk-THIS-IS-A-SECRET-KEY-1234567890"
class Net:
    """A fake network: records calls, answers with a scripted (status, json)."""
    def __init__(self, status=200, data=None, boom=None): self.calls, self.status, self.data, self.boom = [], status, data, boom
    def __call__(self, url, headers, body, timeout_s):
        self.calls.append((url, headers, body, timeout_s))
        if self.boom: raise self.boom
        return self.status, self.data
def req(provider="x", key_name="MY_KEY", ground=True, searches=3, **kw):
    return ProviderRequest(provider=provider, model_name="the-model", key_name=key_name, prompt="PROMPT TEXT", max_output_tokens=900,
                           max_searches=searches, use_grounding=ground, timeout_s=33, **kw)
GEM = {"candidates": [{"content": {"parts": [{"text": '{"venues": []}'}]}, "groundingMetadata": {"webSearchQueries": ["a", "b"]}}],
       "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 40, "thoughtsTokenCount": 15}}
CLA = {"content": [{"type": "text", "text": "ok "}, {"type": "web_search_tool_result"}, {"type": "text", "text": "done"}],
       "usage": {"input_tokens": 200, "output_tokens": 60, "server_tool_use": {"web_search_requests": 2}}}
OAI = {"output": [{"type": "web_search_call"}, {"type": "web_search_call"}, {"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
       "usage": {"input_tokens": 300, "output_tokens": 70}}

# ---------------------------------------------------------------- Gemini
n = Net(data=GEM); g = GeminiProvider(n, lambda: "TOKEN123", "my-project")
r = g.generate(req())
url, headers, body, to = n.calls[0]
check("gemini: calls the Vertex generateContent URL for the project and model", url == "https://aiplatform.googleapis.com/v1/projects/my-project/locations/global/publishers/google/models/the-model:generateContent", url)
check("gemini: signs in with the token, not a key", headers == {"Authorization": "Bearer TOKEN123"})
check("gemini: body has the prompt, the output limit and the search tool", body["contents"][0]["parts"][0]["text"] == "PROMPT TEXT"
      and body["generationConfig"]["maxOutputTokens"] == 900 and body["tools"] == [{"googleSearch": {}}] and to == 33)
check("gemini: reads text, tokens (answer + thinking) and searches", (r.outcome, r.text, r.input_tokens, r.output_tokens, r.searches) == ("ok", '{"venues": []}', 120, 55, 2))
n = Net(data=GEM); GeminiProvider(n, lambda: "T", "p").generate(req(ground=False))
check("gemini: no search tool when grounding is off", "tools" not in n.calls[0][2])
check("gemini: no token = rejected auth_failed, no call", (lambda n: (GeminiProvider(n, lambda: None, "p").generate(req()).error_code, len(n.calls)))(Net()) == ("auth_failed", 0))
check("gemini: no project = rejected, no call", (lambda n: (GeminiProvider(n, lambda: "t", "").generate(req()).outcome, len(n.calls)))(Net()) == ("rejected", 0))
check("gemini: a token function that raises is a no_answer", GeminiProvider(Net(), lambda: 1 / 0, "p").generate(req()).outcome == "no_answer")
check("gemini: empty candidate is no_answer unreadable_reply, usage kept", (lambda r: (r.outcome, r.error_code, r.input_tokens))(GeminiProvider(Net(data={"candidates": [{}], "usageMetadata": {"promptTokenCount": 9}}), lambda: "t", "p").generate(req())) == ("no_answer", "unreadable_reply", 9))

# ---------------------------------------------------------------- Claude
n = Net(data=CLA); c = ClaudeProvider(n, lambda name: SECRET if name == "MY_KEY" else None)
r = c.generate(req())
url, headers, body, to = n.calls[0]
check("claude: Messages URL, key header and version header", url == "https://api.anthropic.com/v1/messages" and headers["x-api-key"] == SECRET and headers["anthropic-version"] == "2023-06-01")
check("claude: body has model, max_tokens, prompt and the search tool with max_uses", body["model"] == "the-model" and body["max_tokens"] == 900
      and body["messages"] == [{"role": "user", "content": "PROMPT TEXT"}] and body["tools"][0]["name"] == "web_search" and body["tools"][0]["max_uses"] == 3)
check("claude: joins the text blocks and reads usage and searches", (r.outcome, r.text, r.input_tokens, r.output_tokens, r.searches) == ("ok", "ok done", 200, 60, 2))
n = Net(data=CLA); ClaudeProvider(n, lambda k: SECRET).generate(req(searches=0))
check("claude: no search tool with zero searches allowed", "tools" not in n.calls[0][2])
n = Net(); r = ClaudeProvider(n, lambda k: None).generate(req())
check("claude: key not found by that NAME = rejected key_missing and NO call", (r.outcome, r.error_code, len(n.calls)) == ("rejected", "key_missing", 0))
check("claude: a model with no key_name is key_missing", ClaudeProvider(Net(), lambda k: SECRET).generate(req(key_name=None)).error_code == "key_missing")

# ---------------------------------------------------------------- OpenAI
n = Net(data=OAI); o = OpenAIProvider(n, lambda name: SECRET)
r = o.generate(req())
url, headers, body, to = n.calls[0]
check("openai: Responses URL and bearer key", url == "https://api.openai.com/v1/responses" and headers == {"Authorization": f"Bearer {SECRET}"})
check("openai: body has input, output limit, web_search tool and the tool-call limit", body["input"] == "PROMPT TEXT" and body["max_output_tokens"] == 900
      and body["tools"] == [{"type": "web_search"}] and body["max_tool_calls"] == 3)
check("openai: reads message text, usage and counts search calls", (r.outcome, r.text, r.input_tokens, r.output_tokens, r.searches) == ("ok", "hi", 300, 70, 2))

# ---------------------------------------------------------------- errors, for every adapter
mk = {"gemini": lambda net: GeminiProvider(net, lambda: "t", "p"), "claude": lambda net: ClaudeProvider(net, lambda k: SECRET),
      "openai": lambda net: OpenAIProvider(net, lambda k: SECRET)}
body_with_secret = {"error": {"message": f"bad key {SECRET} and a very long provider explanation"}}
for name, build in mk.items():
    for status, outcome, code in ((401, "rejected", "auth_failed"), (403, "rejected", "auth_failed"), (400, "rejected", "bad_request"),
                                  (404, "rejected", "bad_request"), (429, "no_answer", "rate_limited"), (500, "no_answer", "provider_unavailable"),
                                  (503, "no_answer", "provider_unavailable"), (0, "no_answer", "provider_unavailable")):
        r = build(Net(status=status, data=body_with_secret)).generate(req())
        check(f"{name}: HTTP {status} -> {outcome}/{code}", (r.outcome, r.error_code) == (outcome, code), (r.outcome, r.error_code))
    r = build(Net(boom=TimeoutError(f"slow {SECRET}"))).generate(req())
    check(f"{name}: a transport that raises is a no_answer with a fixed code, nothing leaked",
          r.outcome == "no_answer" and r.error_code in CODES and SECRET not in repr(r))
    r = build(Net(status=200, data={"surprise": True})).generate(req())
    check(f"{name}: a reply of the wrong shape is no_answer unreadable_reply", (r.outcome, r.error_code) == ("no_answer", "unreadable_reply"))
    r = build(Net(status=200, data=None)).generate(req())
    check(f"{name}: a reply that is not JSON is a no_answer, not a crash", r.outcome == "no_answer")
    r = build(Net(status=401, data=body_with_secret)).generate(req())
    check(f"{name}: provider error text and the key never come back", SECRET not in repr(r) and "explanation" not in repr(r))
check("error codes are all in the closed list", all(code in CODES for code in ("key_missing", "auth_failed", "bad_request", "rate_limited", "provider_unavailable", "unreadable_reply")))

# ---------------------------------------------------------------- the core's provider contract kit
good = {"gemini": GEM, "claude": CLA, "openai": OAI}
for name, build in mk.items():
    check(f"kit: {name} keeps the provider contract", contract_kit.provider_failures(build(Net(data=good[name])), key_name="MY_KEY") == [])
    check(f"kit: {name} keeps it when the network fails", contract_kit.provider_failures(build(Net(boom=OSError("x"))), key_name="MY_KEY") == [])

# ---------------------------------------------------------------- build and the real transport
table = build_providers("proj", transport=Net(data=GEM), secret_fn=lambda k: SECRET, token_fn=lambda: "t")
check("build: one adapter per company", sorted(table) == ["claude", "gemini", "openai"] and all(table[k].name == k for k in table))
check("transport: refuses anything but https and never raises", http_transport.post_json("http://example.com", {}, {}, 1) == (0, None)
      and http_transport.post_json("https://127.0.0.1:1/x", {}, {}, 1)[0] == 0)

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
