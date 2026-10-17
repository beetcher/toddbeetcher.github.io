"""The Discovery engine (plan sections 8 and 14). Product-blind (D-1).

Calls: plan (check the request, build the run record and the estimate), step (do ONE chunk: one AI call for one type in one area),
stop, withdraw. Every call returns a Reply and NEVER raises into the caller. The run record is the log: one record per Go, never
deleted (D-12), holding the exact prompt text of every step (D-18).
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cost, marks, parse, prompt as prompt_mod
from .contract import (MAX_IDS, MAX_REJECTIONS, MAX_STEPS, MAX_STORED_PROMPT, ProviderRequest, Reply, RunRequest, SinkContext)

REASONS = ("ok", "mode_off", "unknown_finder", "unknown_model", "model_inactive", "unknown_area", "area_inactive",
           "unknown_type", "type_inactive", "no_prompt", "bad_prompt", "over_cap", "over_results", "bad_request",
           "too_many_steps", "run_not_found", "run_not_active", "nothing_to_withdraw", "internal_error")
MAX_NO_ANSWERS_IN_A_ROW = 3


def _iso(now) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Discovery:
    def __init__(self, finders, providers, areas, catalog, runs, sink, mode_fn, clock=None):
        self.finders = {f.key: f for f in finders}
        self.providers, self.areas, self.catalog = providers, areas, catalog
        self.runs, self.sinks, self.mode_fn = runs, sink, mode_fn
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # ---------------------------------------------------------------- public calls
    def plan(self, request: RunRequest, by: str) -> Reply:
        try:
            return self._plan(request, by)
        except Exception:
            return Reply(False, "internal_error", "Discovery could not plan this run.")

    def step(self, run_id: str, by: str) -> Reply:
        try:
            return self._step(run_id, by)
        except Exception:
            self._try_fail(run_id, by)
            return Reply(False, "internal_error", "Discovery could not finish this step.")

    def stop(self, run_id: str, by: str) -> Reply:
        try:
            run = self.runs.get(run_id)
            if not run:
                return Reply(False, "run_not_found", "No such run.")
            if run["status"] not in ("planned", "running"):
                return Reply(False, "run_not_active", "This run is not active.")
            self._update(run_id, {"status": "stopped", "stop_reason": "operator", "finished_at": _iso(self.clock())}, by)
            return Reply(True, data={"run_id": run_id})
        except Exception:
            return Reply(False, "internal_error", "Discovery could not stop this run.")

    def withdraw(self, run_id: str, by: str) -> Reply:
        try:
            run = self.runs.get(run_id)
            if not run:
                return Reply(False, "run_not_found", "No such run.")
            if run["status"] not in ("finished", "stopped", "failed") or run["run_mode"] != "live":
                return Reply(False, "nothing_to_withdraw", "This run has nothing to take back.")
            res = self.sinks.withdraw(run, by, self.clock())
            now = _iso(self.clock())
            self._update(run_id, {"status": "withdrawn", "withdrawn_at": now, "withdrawn_by": by,
                                  "notes": f"Withdrawn. Removed: {res.removed}. Kept: {len(res.kept)}."[:2000]}, by)
            return Reply(True, data={"removed": res.removed, "kept": list(res.kept)})
        except Exception:
            return Reply(False, "internal_error", "Discovery could not withdraw this run.")

    # ---------------------------------------------------------------- plan
    def _refuse(self, code, message):
        return Reply(False, code, message)

    def _plan(self, rq: RunRequest, by: str) -> Reply:
        if self.mode_fn() == "off":
            return self._refuse("mode_off", "Discovery is switched off.")
        finder = self.finders.get(rq.finder_key)
        if not finder:
            return self._refuse("unknown_finder", "No such finder.")
        if (not rq.area_ids or not rq.type_keys or len(set(rq.area_ids)) != len(rq.area_ids)
                or len(set(rq.type_keys)) != len(rq.type_keys) or rq.max_results < 1 or rq.spend_cap_cents < 0):
            return self._refuse("bad_request", "The request is not complete.")
        limits = self.catalog.limits()
        if rq.max_results > limits.max_results_per_run:                     # D-16
            return self._refuse("over_results", "More results than the settings allow.")
        if rq.spend_cap_cents > limits.max_spend_cap_cents:                 # D-16
            return self._refuse("over_cap", "A spending cap above what the settings allow.")
        model = self.catalog.get_model(rq.model_id)
        if not model:
            return self._refuse("unknown_model", "No such model.")
        if not model.is_active or model.provider not in self.providers:     # D-9
            return self._refuse("model_inactive", "This model is not switched on.")
        areas = {a.id: a for a in self.areas.resolve(rq.area_ids)}
        for aid in rq.area_ids:
            a = areas.get(aid)
            if not a:
                return self._refuse("unknown_area", "No such area.")
            if not (a.is_active and a.state_is_active):                       # D-9
                return self._refuse("area_inactive", "An area or its state is not switched on.")
        types = {t.key: t for t in self.catalog.list_types(rq.finder_key)}
        for key in rq.type_keys:
            t = types.get(key)
            if not t:
                return self._refuse("unknown_type", "No such type.")
            if not t.is_active:                                                # D-9
                return self._refuse("type_inactive", "A type is not switched on.")
        pr = self.catalog.published_prompt(rq.finder_key)
        if not pr:
            return self._refuse("no_prompt", "There is no published prompt.")
        if prompt_mod.check_text(pr.text, finder.placeholders):
            return self._refuse("bad_prompt", "The published prompt has a problem.")
        steps = len(rq.area_ids) * len(rq.type_keys)
        if steps > MAX_STEPS:
            return self._refuse("too_many_steps", f"A run is at most {MAX_STEPS} steps.")
        per_step = min(limits.results_per_step, rq.max_results)
        chars = [len(prompt_mod.build(pr.text, finder, areas[a], types[t], per_step)) for a in rq.area_ids for t in rq.type_keys]
        low, high = cost.estimate(model, chars, [per_step] * steps)
        mode = self.mode_fn()
        run = {"finder_key": rq.finder_key, "status": "planned", "run_mode": "live" if mode == "live" else "dry_run",
               "model_id": model.id, "model_name": model.model_name,
               "model_price_input_per_million_cents": model.price_input_per_million_cents,
               "model_price_output_per_million_cents": model.price_output_per_million_cents,
               "area_ids": list(rq.area_ids), "area_labels": [areas[a].label for a in rq.area_ids],
               "type_keys": list(rq.type_keys), "prompt_id": pr.id, "prompt_version": pr.version,
               "max_results": rq.max_results, "spend_cap_cents": rq.spend_cap_cents,
               "estimated_cost_low_cents": low, "estimated_cost_high_cents": high, "actual_cost_cents": 0,
               "input_tokens": 0, "output_tokens": 0, "search_count": 0, "steps_planned": steps, "steps_done": 0, "steps": [],
               "found_count": 0, "created_count": 0, "duplicate_count": 0, "rejected_count": 0, "attention_count": 0,
               "rejections": [], "started_at": _iso(self.clock())}
        if model.price_search_per_1000_cents is not None:
            run["model_price_search_per_1000_cents"] = model.price_search_per_1000_cents
        rid = self.runs.create(run, by, self.clock())
        return Reply(True, data={"run_id": rid, "run_mode": run["run_mode"], "steps_planned": steps,
                                 "estimated_cost_low_cents": low, "estimated_cost_high_cents": high})

    # ---------------------------------------------------------------- step
    def _update(self, run_id, changes, by):
        self.runs.update(run_id, changes, by, self.clock())

    def _try_fail(self, run_id, by):
        try:
            run = self.runs.get(run_id)
            if run and run["status"] in ("planned", "running"):
                self._update(run_id, {"status": "failed", "finished_at": _iso(self.clock())}, by)
        except Exception:
            pass

    def _stop(self, run_id, reason, by, status="stopped"):
        self._update(run_id, {"status": status, "stop_reason": reason, "finished_at": _iso(self.clock())}, by)
        return Reply(True, data={"run_id": run_id, "status": status, "stop_reason": reason, "done": True})

    def _step(self, run_id, by) -> Reply:
        run = self.runs.get(run_id)
        if not run:
            return Reply(False, "run_not_found", "No such run.")
        if run["status"] not in ("planned", "running"):
            return Reply(False, "run_not_active", "This run is not active.")
        mode = self.mode_fn()
        if mode == "off":                                                        # D-5
            return self._stop(run_id, "mode_off", by)
        finder = self.finders[run["finder_key"]]
        n = run["steps_done"]
        if n >= run["steps_planned"]:
            return self._finish(run_id, by)
        remaining_results = run["max_results"] - run["created_count"]
        if remaining_results <= 0:                                               # D-14
            return self._stop(run_id, "results_limit", by)
        tail = [s["status"] for s in run["steps"][-MAX_NO_ANSWERS_IN_A_ROW:]]
        if len(tail) == MAX_NO_ANSWERS_IN_A_ROW and all(s == "no_answer" for s in tail):
            return self._stop(run_id, "too_many_no_answers", by)
        type_key = run["type_keys"][n % len(run["type_keys"])]
        area_id = run["area_ids"][n // len(run["type_keys"])]
        model = self.catalog.get_model(run["model_id"])
        pr = self.catalog.get_prompt(run["prompt_id"])
        types = {t.key: t for t in self.catalog.list_types(run["finder_key"])}
        areas = {a.id: a for a in self.areas.resolve([area_id])}
        limits = self.catalog.limits()
        if not (model and pr and type_key in types and area_id in areas):
            return self._fail_step(run_id, run, n, type_key, area_id, "setting_missing", by)
        # Anything switched off after the plan stops the run (D-9).
        if not (model.is_active and types[type_key].is_active and areas[area_id].is_active and areas[area_id].state_is_active):
            return self._stop(run_id, "operator", by)
        per_step = min(limits.results_per_step, remaining_results)
        text = prompt_mod.build(pr.text, finder, areas[area_id], types[type_key], per_step)
        stored = text[:MAX_STORED_PROMPT]
        live = run["run_mode"] == "live" and mode == "live"
        if not live:                                                              # dry_run: no provider call (D-5)
            step = {"step_number": n + 1, "type_key": type_key, "area_id": area_id, "status": "skipped", "result_count": 0,
                    "input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "prompt_text": stored}
            return self._record(run_id, run, step, {}, by)
        remaining_cents = run["spend_cap_cents"] - run["actual_cost_cents"]
        lim = cost.step_limits(model, len(text), remaining_cents)                 # D-4
        if lim is None:
            return self._stop(run_id, "cap_reached", by)
        max_out, max_search = lim
        if run["status"] == "planned":
            self._update(run_id, {"status": "running"}, by)
        result = self._call(model, text, max_out, max_search)
        in_t, out_t = max(0, int(result.input_tokens)), max(0, int(result.output_tokens))
        searches = max(0, int(result.searches))
        step_cost = cost.cost_cents(model, in_t, out_t, searches)
        step = {"step_number": n + 1, "type_key": type_key, "area_id": area_id, "result_count": 0, "input_tokens": in_t,
                "output_tokens": out_t, "cost_cents": step_cost, "prompt_text": stored}
        counts = {"input_tokens": in_t, "output_tokens": out_t, "search_count": searches, "cost": step_cost}
        if result.outcome != "ok":
            step["status"] = "rejected" if result.outcome == "rejected" else "no_answer"
            step["error_code"] = (result.error_code or "provider_error")[:60]
            return self._record(run_id, run, step, counts, by)
        items = parse.parse_items(result.text, finder.result_key)
        if items is None:
            step["status"], step["error_code"] = "no_answer", "unreadable_answer"
            return self._record(run_id, run, step, counts, by)
        step["status"] = "ok"
        found = len(items)
        counts.update(self._save_items(run_id, run, finder, items[:per_step], by))
        counts["found"] = found
        step["result_count"] = counts.get("created", 0)
        return self._record(run_id, run, step, counts, by)

    def _call(self, model, text, max_out, max_search):
        provider = self.providers[model.provider]
        req = ProviderRequest(provider=model.provider, model_name=model.model_name, key_name=model.key_name, prompt=text,
                              max_output_tokens=max_out, max_searches=max_search,
                              use_grounding=bool(model.has_grounding and max_search))
        try:
            res = provider.generate(req)
            if res.outcome not in ("ok", "rejected", "no_answer"):
                raise ValueError
            return res
        except Exception:                                                         # D-2
            from .contract import ProviderResult
            return ProviderResult("no_answer", error_code="provider_failed")

    def _save_items(self, run_id, run, finder, items, by) -> dict:
        seen, out = set(), {"created": 0, "duplicate": 0, "rejected": 0, "attention": 0, "rejections": [], "ids": {}}
        ctx = SinkContext(run_id, finder.key, run["model_name"], run["prompt_version"], by, self.clock())
        found_at = _iso(self.clock())
        for raw in items:
            cand, rej = marks.check_item(raw, finder)
            if rej:                                                               # D-8, D-10
                out["rejected"] += 1
                out["rejections"].append(rej)
                continue
            key = finder.dedupe_key(cand.values())
            if key is not None and key in seen:                                   # D-7 inside one run
                out["duplicate"] += 1
                continue
            cand.block = marks.build_block(cand, run_id, run["model_name"], run["prompt_version"], found_at)
            res = self.sinks.save(cand, ctx)
            for kind, ids in (res.ids or {}).items():
                out["ids"].setdefault(kind, []).extend(ids)
            if res.status == "duplicate":
                out["duplicate"] += 1
                if key is not None:
                    seen.add(key)
                continue
            if res.status != "saved" or res.record_status != "inactive":          # D-6
                out["rejected"] += 1
                out["rejections"].append({"name": cand.label[:200], "fields": [],
                                          "reason": "not_saved_inactive" if res.status == "saved" else (res.reason or "sink_rejected")})
                continue
            if key is not None:
                seen.add(key)
            out["created"] += 1
            if cand.attention_reasons or res.attention_reasons:
                out["attention"] += 1
        return out

    def _fail_step(self, run_id, run, n, type_key, area_id, code, by):
        step = {"step_number": n + 1, "type_key": type_key, "area_id": area_id, "status": "no_answer", "result_count": 0,
                "input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "error_code": code}
        return self._record(run_id, run, step, {}, by)

    def _record(self, run_id, run, step, c, by):
        changes = {"steps": run["steps"] + [step], "steps_done": run["steps_done"] + 1,
                   "input_tokens": run["input_tokens"] + c.get("input_tokens", 0),
                   "output_tokens": run["output_tokens"] + c.get("output_tokens", 0),
                   "search_count": run["search_count"] + c.get("search_count", 0),
                   "actual_cost_cents": run["actual_cost_cents"] + c.get("cost", 0),
                   "found_count": run["found_count"] + c.get("found", 0),
                   "created_count": run["created_count"] + c.get("created", 0),
                   "duplicate_count": run["duplicate_count"] + c.get("duplicate", 0),
                   "rejected_count": run["rejected_count"] + c.get("rejected", 0),
                   "attention_count": run["attention_count"] + c.get("attention", 0),
                   "rejections": (run["rejections"] + c.get("rejections", []))[:MAX_REJECTIONS]}
        for kind, ids in c.get("ids", {}).items():
            key = f"created_{kind}_ids"
            changes[key] = (run.get(key, []) + ids)[:MAX_IDS]
        if run["status"] == "planned":
            changes["status"] = "running"
        self._update(run_id, changes, by)
        done = changes["steps_done"] >= run["steps_planned"]
        if changes["actual_cost_cents"] > run["spend_cap_cents"]:
            return self._stop(run_id, "cap_reached", by)
        if done:
            return self._finish(run_id, by)
        return Reply(True, data={"run_id": run_id, "status": "running", "done": False, "steps_done": changes["steps_done"],
                                 "step_status": step["status"]})

    def _finish(self, run_id, by):
        self._update(run_id, {"status": "finished", "finished_at": _iso(self.clock())}, by)
        return Reply(True, data={"run_id": run_id, "status": "finished", "done": True})
