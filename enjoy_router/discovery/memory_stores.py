"""In-memory ports for tests and for dry runs of the contract kit. Product-blind."""
from __future__ import annotations

import copy
import itertools
import uuid
from typing import Optional

from .contract import (AreaEntry, Candidate, Limits, ModelEntry, PromptEntry, ProviderRequest, ProviderResult, SinkContext,
                       SinkResult, TypeEntry, WithdrawResult)


class MemoryRunStore:
    def __init__(self):
        self.runs, self._n = {}, itertools.count(1)
        self.fail = False

    def create(self, run, by, now):
        if self.fail:
            raise RuntimeError("store down")
        rid = f"run-{next(self._n)}"
        self.runs[rid] = {**copy.deepcopy(run), "id": rid, "created_by": by}
        return rid

    def update(self, run_id, changes, by, now):
        if self.fail:
            raise RuntimeError("store down")
        self.runs[run_id].update(copy.deepcopy(changes))
        self.runs[run_id]["updated_by"] = by

    def get(self, run_id) -> Optional[dict]:
        return copy.deepcopy(self.runs.get(run_id))


class MemoryAreas:
    def __init__(self, entries=()):
        self.entries = {e.id: e for e in entries}

    def resolve(self, area_ids):
        return [self.entries[i] for i in area_ids if i in self.entries]


class MemoryCatalog:
    def __init__(self, models=(), types=(), prompts=(), limits=None, published=None):
        self.models = {m.id: m for m in models}
        self.types = {}
        for finder_key, t in types:
            self.types.setdefault(finder_key, []).append(t)
        self.prompts = {p.id: p for p in prompts}
        self.published = dict(published or {})
        self._limits = limits or Limits(max_spend_cap_cents=1000, max_results_per_run=100, results_per_step=10,
                                        default_spend_cap_cents=100)

    def get_model(self, model_id): return self.models.get(model_id)
    def list_types(self, finder_key): return list(self.types.get(finder_key, []))
    def published_prompt(self, finder_key):
        pid = self.published.get(finder_key)
        return self.prompts.get(pid) if pid else None
    def get_prompt(self, prompt_id): return self.prompts.get(prompt_id)
    def limits(self): return self._limits


class FakeProvider:
    """A provider that answers from a script. reply(request) -> ProviderResult, or a list of results used in turn.
    It honours max_output_tokens the way every real adapter must (the contract kit checks that)."""
    def __init__(self, name="fake", replies=None):
        self.name, self.calls, self.replies = name, [], replies

    def generate(self, request: ProviderRequest) -> ProviderResult:
        self.calls.append(request)
        r = self.replies
        if callable(r):
            res = r(request)
        elif r:
            res = r[min(len(self.calls), len(r)) - 1]
        else:
            res = ProviderResult("ok", text='{"results": []}', input_tokens=100, output_tokens=20)
        if res.output_tokens > request.max_output_tokens:
            res = ProviderResult(res.outcome, res.text[:0], res.input_tokens, request.max_output_tokens, res.searches, res.error_code)
        return res


class MemorySink:
    """Saves candidates as inactive records in a dict. dedupe on the finder's own key is the sink's job (D-7): this memory sink
    uses the key passed in `keyer`."""
    def __init__(self, keyer, kind="item"):
        self.keyer, self.kind = keyer, kind
        self.records, self.touched, self._n = {}, set(), itertools.count(1)
        self.record_status = "inactive"
        self.extra_attention = ()

    def save(self, candidate: Candidate, ctx: SinkContext) -> SinkResult:
        key = self.keyer(candidate.values())
        if key is not None and any(r["key"] == key and not r.get("withdrawn") for r in self.records.values()):
            return SinkResult("duplicate", reason="same_record")
        rid = str(uuid.uuid4())
        self.records[rid] = {"key": key, "values": candidate.values(), "status": self.record_status, "block": candidate.block,
                             "run_id": ctx.run_id}
        return SinkResult("saved", record_status=self.record_status, ids={self.kind: [rid]},
                          attention_reasons=tuple(self.extra_attention))

    def withdraw(self, run, by, now) -> WithdrawResult:
        removed, kept = 0, []
        for rid in run.get(f"created_{self.kind}_ids", []):
            rec = self.records.get(rid)
            if not rec or rec.get("withdrawn"):
                continue
            if rec["status"] != "inactive" or rid in self.touched:
                kept.append(rid)
            else:
                rec["withdrawn"] = True
                removed += 1
        return WithdrawResult({self.kind: removed}, kept)
