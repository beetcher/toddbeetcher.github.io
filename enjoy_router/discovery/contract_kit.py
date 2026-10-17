"""Tests every implementation of a port must pass (like comms/contract_kit.py). Each function returns a list of failure messages;
an empty list means the implementation keeps the contract. Product-blind."""
from __future__ import annotations

from .contract import Candidate, ProviderRequest, SinkContext

PORT_OUTCOMES = ("ok", "rejected", "no_answer")


def provider_failures(provider, key_name=None) -> list:
    """A provider answers with a ProviderResult, never raises, never exceeds the output limit it was given, and never puts a key or
    provider text in error_code (D-2, D-11)."""
    out = []
    req = ProviderRequest(provider=getattr(provider, "name", "?"), model_name="test-model", key_name=key_name,
                          prompt="Reply with the JSON object {\"results\": []}.", max_output_tokens=500, max_searches=0,
                          use_grounding=False, timeout_s=5)
    try:
        res = provider.generate(req)
    except Exception as exc:
        return [f"generate raised {type(exc).__name__}"]
    if res.outcome not in PORT_OUTCOMES:
        out.append(f"outcome {res.outcome!r} is not one of {PORT_OUTCOMES}")
    if res.output_tokens > req.max_output_tokens:
        out.append("reported more output tokens than the limit it was given")
    if res.error_code is not None and (len(res.error_code) > 60 or " " in res.error_code):
        out.append("error_code is not a short code")
    if key_name and key_name in (res.error_code or ""):
        out.append("error_code contains the key name")
    return out


def run_store_failures(store, run_factory) -> list:
    out = []
    if hasattr(store, "delete") or hasattr(store, "remove"):
        out.append("a run store must not offer delete (D-12)")
    try:
        rid = store.create(run_factory(), "system:kit", None)
        got = store.get(rid)
        if not got or got.get("finder_key") != run_factory()["finder_key"]:
            out.append("get does not return what create stored")
        store.update(rid, {"status": "running"}, "system:kit", None)
        if store.get(rid)["status"] != "running":
            out.append("update did not change the run")
        got["status"] = "tampered"
        if store.get(rid)["status"] == "tampered":
            out.append("get returns the stored object itself, not a copy")
        if store.get("no-such-run") is not None:
            out.append("get of an unknown run must be None")
    except Exception as exc:
        out.append(f"run store raised {type(exc).__name__}")
    return out


def sink_failures(sink, candidate_factory) -> list:
    """candidate_factory(n) -> a Candidate whose n-th variants are different records. Save makes an inactive record; the same one
    again is a duplicate and creates nothing new; withdraw takes back what the save created (D-6, D-7, D-13)."""
    out = []
    ctx = SinkContext("run-kit", "kit", "m", 1, "system:kit", None)
    try:
        first = sink.save(candidate_factory(1), ctx)
        if first.status != "saved" or first.record_status != "inactive":
            out.append("first save must be saved as inactive")
        again = sink.save(candidate_factory(1), ctx)
        if again.status != "duplicate" or again.ids:
            out.append("the same candidate again must be a duplicate that creates nothing")
        other = sink.save(candidate_factory(2), ctx)
        if other.status != "saved":
            out.append("a different candidate must be saved")
        run = {f"created_{k}_ids": list(v) for k, v in first.ids.items()}
        res = sink.withdraw(run, "system:kit", None)
        if not any(res.removed.values()):
            out.append("withdraw removed nothing that the run created")
        if sink.save(candidate_factory(1), ctx).status != "saved":
            out.append("after withdraw the same candidate must be saveable again")
    except Exception as exc:
        out.append(f"sink raised {type(exc).__name__}")
    return out


def area_failures(areas, known_id, unknown_id) -> list:
    out = []
    got = areas.resolve((known_id, unknown_id))
    if [a.id for a in got] != [known_id]:
        out.append("resolve must return only the areas that exist")
    return out
