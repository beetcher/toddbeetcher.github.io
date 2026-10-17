"""LAUNCH's implementations of the core's ports over the Discovery collections (in-process handlers on a doc store).

StoreAreas   AreaDirectory: states take their ZIPs from the shared ZIP table, regions carry their own list.
StoreCatalog Catalog: models, active types, the standing published prompt, and the limits (starting values until settings exist).
StoreRuns    RunStore: run records through the runs handler; there is no delete.
Each raises only when the database itself fails; the core catches that and ends the call as internal_error.
"""
from __future__ import annotations

from discovery.contract import AreaEntry, Limits, ModelEntry, PromptEntry, TypeEntry
from crud import discovery_areas_crud as AR
from crud import discovery_models_crud as MO
from crud import discovery_prompts_crud as PR
from crud import discovery_runs_crud as RU
from crud import discovery_settings_crud as SE
from crud import discovery_types_crud as TY

from . import zip_table


class StoreAreas:
    def __init__(self, store):
        self.store = store

    def resolve(self, area_ids):
        out = []
        for aid in area_ids:
            got = AR.get(self.store, aid) if isinstance(aid, str) else None
            if not got or not got.ok:
                continue
            a = got.data
            state_active = a["is_active"]
            if a["kind"] == "region":
                states = [s for s in AR.list(self.store, {"kind": "state", "state_code": a["state_code"]}).data["records"]]
                state_active = bool(states and states[0]["is_active"])
                zips = tuple(a.get("zip_codes", ()))
            else:
                zips = tuple(zip_table.zips_in_state(a["state_code"]))
            out.append(AreaEntry(a["id"], a["name"], a["kind"], a["state_code"], a["is_active"], state_active, zips))
        return out


class StoreCatalog:
    def __init__(self, store):
        self.store = store

    def get_model(self, model_id):
        got = MO.get(self.store, model_id) if isinstance(model_id, str) else None
        if not got or not got.ok:
            return None
        m = got.data
        return ModelEntry(m["id"], m["provider"], m["model_name"], m["label"], m["price_input_per_million_cents"],
                          m["price_output_per_million_cents"], m.get("search_price_per_1000_cents"), m.get("max_output_tokens"),
                          m["has_grounding"], m.get("key_name"), m["is_active"])

    def list_types(self, finder_key):
        recs = TY.list(self.store, {"finder_key": finder_key}, "sort_order").data["records"]
        recs.sort(key=lambda d: (d.get("sort_order", 10**6), d["label"].lower()))
        return [TypeEntry(d["key"], d["label"], d.get("search_hint", ""), d["is_chain"], d["is_active"]) for d in recs]

    def published_prompt(self, finder_key):
        pubs = PR.list(self.store, {"finder_key": finder_key}).data["records"]
        pubs = [d for d in pubs if d.get("status") == "published"]
        if not pubs:
            return None
        stand = PR.standing(self.store, pubs[0])
        return PromptEntry(stand["id"], stand["version"], stand["text"]) if stand else None

    def get_prompt(self, prompt_id):
        got = PR.get(self.store, prompt_id) if isinstance(prompt_id, str) else None
        return PromptEntry(got.data["id"], got.data["version"], got.data["text"]) if got and got.ok else None

    def limits(self):
        recs = SE.list(self.store).data["records"]
        s = recs[0] if recs else SE.DEFAULTS
        return Limits(max_spend_cap_cents=s["max_spend_cap_cents"], max_results_per_run=s["max_results_per_run"],
                      results_per_step=s["results_per_step"], default_spend_cap_cents=s["default_spend_cap_cents"],
                      default_model_id=s.get("default_model_id"))


class StoreRuns:
    def __init__(self, store):
        self.store = store

    def create(self, run, by, now):
        got = RU.create(self.store, run, by, source="import", now=now)
        if not got.ok:
            raise RuntimeError("run not saved: " + ",".join(f"{p['field']}:{p['issue']}" for p in got.problems or []) or got.code)
        return got.data["id"]

    def update(self, run_id, changes, by, now):
        got = RU.update(self.store, run_id, changes, by, now=now)
        if not got.ok:
            raise RuntimeError("run not updated: " + ",".join(f"{p['field']}:{p['issue']}" for p in got.problems or []) or got.code)

    def get(self, run_id):
        got = RU.get(self.store, run_id) if isinstance(run_id, str) else None
        return got.data if got and got.ok else None
