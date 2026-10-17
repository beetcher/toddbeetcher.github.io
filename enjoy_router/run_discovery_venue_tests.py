#!/usr/bin/env python3
"""Tests for the venue finder and the venue sink (launch_discovery/venue_finder.py, venue_sink.py) over the REAL venue, place and
organization handlers in memory. Also the whole Discovery engine end to end with a fake AI.
Run from enjoy_router/:  python3 run_discovery_venue_tests.py   (-v lists every check). Nothing touches the network or Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import (discovery_areas_crud as AR, discovery_models_crud as MO, discovery_prompts_crud as PR, discovery_types_crud as TY,  # noqa: E402
                  location_links_crud as LK, locations_crud as LOC, organization_links_crud as OLC, organizations_crud as ORG,
                  venues_crud as VC, venues_service as VS)
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from discovery import contract_kit, marks  # noqa: E402
from discovery.contract import Candidate, ProviderResult, RunRequest, SinkContext  # noqa: E402
from discovery.memory_stores import FakeProvider  # noqa: E402
from discovery.pipeline import Discovery  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from launch_discovery.stores import StoreAreas, StoreCatalog, StoreRuns  # noqa: E402
from launch_discovery.venue_finder import FINDER, dedupe_key, norm  # noqa: E402
from launch_discovery.venue_sink import ACTOR, VenueSink  # noqa: E402

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
RUN = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 1
    return NOW + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

def cand(name="The Beanery", op="Beanery Inc.", city="Boulder", street="1200 Pearl St", post="80302", **extra):
    f = {"name": name, "operator": op, "city": city, "state": "CO", "is_public_venue": True}
    if street: f["street"] = street
    if post: f["postal_code"] = post
    f.update(extra)
    c = Candidate("", name, {k: {"value": v, "mark": "verify"} for k, v in f.items()})
    c.attention_reasons = [] if street else ["no_street_address"]
    c.block = marks.build_block(c, RUN, "fake-1", 3, "2026-10-17T12:00:00Z")
    return c
CTX = lambda: SinkContext(RUN, "venue", "fake-1", 3, "user:admin", tick())
def fresh(): return MemoryDocStore("test_"), None
def count(store, coll): return len([d for d in store.query(coll, [], limit=999) if "deleted_at" not in d])

# ---------------------------------------------------------------- finder
check("finder: one definition of fields and limits shared with the venue schema", FINDER.ask_fields[0].schema == VC.VENUES.properties["name"]
      and [f.key for f in FINDER.ask_fields if f.tier == "needed"] == ["name", "operator", "city", "state", "is_public_venue"])
check("finder: names compare without punctuation, case or a leading 'the'", norm("The Beanery, Inc.") == norm("beanery inc") == "beanery inc")
check("finder: dedupe key = name + operator + street (else city)", dedupe_key({"name": "A", "operator": "B", "city": "C", "state": "CO", "street": "1 Main"})
      != dedupe_key({"name": "A", "operator": "B", "city": "C", "state": "CO"}) and dedupe_key({"name": "A", "operator": "B", "city": "C", "state": "CO"}) == dedupe_key({"name": "a.", "operator": "b", "city": "c", "state": "co"}))

# ---------------------------------------------------------------- saving
store = MemoryDocStore("test_"); sink = VenueSink(store)
r = sink.save(cand(), CTX())
check("save: a new venue is saved, inactive", r.status == "saved" and r.record_status == "inactive", r.reason)
vid = r.ids["venue"][0]
v = VC.get(store, vid).data
check("save: venue fields, slug, public, inactive, made by the Discovery actor", (v["name"], v["status"], v["is_public_venue"], v["slug"], v["created_by"]) == ("The Beanery", "inactive", True, "the_beanery_boulder", ACTOR), v)
check("save: the AI block is on the venue with the run, marks and no attention", v["discovery"]["run_id"] == RUN and v["discovery"]["marks"]["name"] == "verify")
check("save: ids filed for every record created", sorted(r.ids) == ["location", "location_link", "organization", "organization_link", "venue"])
loc = LOC.get(store, r.ids["location"][0]).data["addresses"][0]
check("save: the place holds a civic address split into number and street", (loc["street_number"], loc["street"], loc["locality"], loc["region"], loc["postal_code"]) == ("1200", "Pearl St", "Boulder", "CO", "80302"))
org = ORG.get(store, r.ids["organization"][0]).data
check("save: the operator organization is created, noted, and the venue is flagged operator_unconfirmed", org["name"] == "Beanery Inc." and RUN in org["notes"]
      and v["discovery"]["attention_reasons"] == ["operator_unconfirmed"] and r.attention_reasons == ("operator_unconfirmed",))
check("save: venue operated_by the organization", OLC.get(store, r.ids["organization_link"][0]).data["relationship"] == "operated_by")
check("save: nothing is active and no GPS lookup was made", VS.has_place(store, vid) and v["status"] == "inactive" and "parking_latitude" not in v)

# duplicates
d = sink.save(cand(name="the beanery", op="BEANERY, INC"), CTX())
check("D-7 same place + same name + same operator (different spelling) is a duplicate, nothing created", d.status == "duplicate" and not d.ids
      and count(store, "venues") == 1 and count(store, "organizations") == 1)
check("D-7 the saved venue is untouched by the duplicate", VC.get(store, vid).data["updated_at"] == v["updated_at"])
s = sink.save(cand(name="The Beanery", op="Someone Else LLC"), CTX())
check("D-7 same place + name, DIFFERENT operator: a new venue that shares the place", s.status == "saved" and "location" not in s.ids
      and count(store, "venues") == 2 and count(store, "locations") == 1)
sink.save(cand(name="Walnut Spot", op="Someone Else LLC", street="900 Walnut St", post="80302"), CTX())
s2 = sink.save(cand(name="Walnut Spot", op="Beanery Inc.", street="900 Walnut St", post="80302"), CTX())
check("D-7 both operators already exist: same place + name + a different (known) operator is still a new venue", s2.status == "saved" and "organization" not in s2.ids)
s = sink.save(cand(street="900 Walnut St"), CTX())
check("D-7 same name + operator at another address: a new venue, existing organization reused, not flagged", s.status == "saved" and "organization" not in s.ids
      and VC.get(store, s.ids["venue"][0]).data["slug"] == "the_beanery_boulder_3" and "needs_attention" not in VC.get(store, s.ids["venue"][0]).data["discovery"])

# no street address
n1 = sink.save(cand(name="Corner Cafe", op="Corner LLC", street=None, post=None), CTX())
nv = VC.get(store, n1.ids["venue"][0]).data
check("D-17 no street address: kept, city-only place, flagged", n1.status == "saved" and nv["discovery"]["needs_attention"] is True
      and "no_street_address" in nv["discovery"]["attention_reasons"] and "location" in n1.ids)
na = LOC.get(store, n1.ids["location"][0]).data["addresses"][0]
check("D-17 the city-only place says it is unverified", (na["locality"], na["region"], na.get("verification")) == ("Boulder", "CO", "none") and "street" not in na and na["lines"] == ["Boulder, CO"])
check("D-7 no street: same name + operator + city is a duplicate", sink.save(cand(name="Corner Cafe", op="Corner LLC", street=None, post=None), CTX()).status == "duplicate")
check("D-7 no street: a different city is not", sink.save(cand(name="Corner Cafe", op="Corner LLC", city="Longmont", street=None, post=None), CTX()).status == "saved")

# refusals
long_name = "N" * 250
rj = sink.save(cand(name=long_name, op="Brand New Operator Co"), CTX())
check("a refused venue is rejected with a code, and any organization it created is still reported", rj.status == "rejected" and rj.reason == "venue_refused" and len(rj.ids.get("organization", [])) == 1)
check("a crash inside the sink is a rejection, not an exception", (lambda s: s.save(cand(), CTX()).status)(type("S", (VenueSink,), {"_address": lambda self, v: 1 / 0})(MemoryDocStore("test_"))) == "rejected")

# kit
n = [0]
def factory(i):
    return cand(name=f"Kit Place {i}", op="Kit Org", street=f"{i} Kit Rd", post="80302")
check("kit: VenueSink keeps the sink contract", contract_kit.sink_failures(VenueSink(MemoryDocStore("test_")), factory) == [])

# ---------------------------------------------------------------- withdraw
store = MemoryDocStore("test_"); sink = VenueSink(store)
res = [sink.save(cand(name=f"Place {i}", op="Shared Org" if i < 3 else "Solo Org", street=f"{i} Main St"), CTX()) for i in range(1, 5)]
run = {}
for r in res:
    for k, ids in r.ids.items():
        run.setdefault(f"created_{k}_ids", []).extend(ids)
v_activate, v_edit, v_other = res[0].ids["venue"][0], res[1].ids["venue"][0], res[2].ids["venue"][0]
check("withdraw setup: venue with a place can be activated by a person", VS.update(store, v_activate, {"status": "active"}, "user:admin", now=tick()).ok)
VS.update(store, v_edit, {"description": "A person edited this."}, "user:admin", now=tick())
w = sink.withdraw(run, "user:admin", tick())
live = lambda coll: {d["id"] for d in store.query(coll, [], limit=999) if "deleted_at" not in d}
check("D-13 an activated venue and an edited venue are kept; untouched ones are taken back", live("venues") == {v_activate, v_edit} and w.removed["venue"] == 2)
check("D-13 a kept venue keeps its place and its links", len(live("locations")) == 2 and len(live("location_links")) == 2 and len(live("organization_links")) == 2)
check("D-13 an organization still used by a kept venue is kept; an unused one goes", len(live("organizations")) == 1 and w.removed.get("organization") == 1)
check("D-13 withdraw reports what it kept", set(w.kept) >= {v_activate, v_edit})
w2 = sink.withdraw(run, "user:admin", tick())
check("D-13 withdraw twice changes nothing more", w2.removed == {} and live("venues") == {v_activate, v_edit})

# ---------------------------------------------------------------- the whole engine, end to end
zip_table.set_table({z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80027")})
s = MemoryDocStore("test_")
A = "user:admin"
mid = MO.create(s, {"provider": "gemini", "model_name": "gemini-3.8-flash", "label": "Gemini", "price_input_per_million_cents": 75,
                    "price_output_per_million_cents": 375, "search_price_per_1000_cents": 1400, "has_grounding": True, "max_output_tokens": 4000}, A, now=tick()).data["id"]
AR.create(s, {"kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}, A, now=tick())
reg = AR.create(s, {"kind": "region", "name": "Boulder", "state_code": "CO", "zip_codes": ["80301", "80302"], "is_active": True}, A, now=tick()).data["id"]
TY.create(s, {"finder_key": "venue", "key": "coffee_shops", "label": "Independent coffee shops and cafes"}, A, now=tick())
seed = json.loads((HERE.parent / "schemas" / "examples" / "discovery_prompt.examples.json").read_text())["valid"]["venue_seed_prompt"]
pid = PR.create(s, {"finder_key": "venue", "name": seed["name"], "text": seed["text"]}, A, now=tick()).data["id"]
PR.publish(s, pid, A, now=tick())
def item(**kw):
    f = {k: {"value": v, "mark": "sure", "source_url": "https://example.org/x"} for k, v in kw.items()}
    return f
answer = json.dumps({"venues": [
    item(name="Ozo Coffee", operator="Ozo Coffee Co", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St", postal_code="80302", website_url="https://ozocoffee.com"),
    item(name="Ozo Coffee", operator="Ozo Coffee Co", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St"),
    item(name="Someone's Apartment", operator="Sam", city="Boulder", state="CO", is_public_venue=False, street="5 Elm St"),
    item(name="Mystery Cafe", operator="Mystery LLC", city="Boulder", state="CO", is_public_venue=True)]})
prov = FakeProvider("gemini", lambda r: ProviderResult("ok", text=answer, input_tokens=900, output_tokens=500, searches=2))
sink = VenueSink(s)
d = Discovery([FINDER], {"gemini": prov}, StoreAreas(s), StoreCatalog(s), StoreRuns(s), sink, lambda: "live", clock=tick, provider_timeout_s=90)
q = d.quote(RunRequest("venue", mid, (reg,), ("coffee_shops",), 20, 100))
check("e2e: the quote shows the cost range and the exact prompt, saving nothing", q.ok and q.data["estimated_cost_high_cents"] >= q.data["estimated_cost_low_cents"] > 0
      and "Boulder (ZIP codes: 80301, 80302)" in q.data["prompts"][0]["prompt_text"] and count(s, "discovery_runs") == 0)
rid = d.plan(RunRequest("venue", mid, (reg,), ("coffee_shops",), 20, 100), A).data["run_id"]
last = d.step(rid, A)
run = StoreRuns(s).get(rid)
check("e2e: one step: 2 saved, 1 duplicate, 1 private home rejected", last.ok and (run["created_count"], run["duplicate_count"], run["rejected_count"]) == (2, 1, 1), run)
check("e2e: the private home was rejected by name and reason, never saved", run["rejections"][0]["reason"] == "private_home" and not any(
    x["name"] == "Someone's Apartment" for x in s.query("venues", [], limit=99)))
check("e2e: the run holds the ids, the cost and the exact prompt", len(run["created_venue_ids"]) == 2 and run["actual_cost_cents"] > 0 and "independent" in run["steps"][0]["prompt_text"].lower())
check("e2e: attention counted (no street, new operators)", run["attention_count"] == 2)
check("e2e: both venues inactive with their marks", all(VC.get(s, i).data["status"] == "inactive" and VC.get(s, i).data["discovery"]["marks"]["name"] == "sure" for i in run["created_venue_ids"]))
check("e2e: a second identical run creates nothing", (lambda rid2: (d.step(rid2, A), StoreRuns(s).get(rid2))[1])(d.plan(RunRequest("venue", mid, (reg,), ("coffee_shops",), 20, 100), A).data["run_id"])["created_count"] == 0)
check("e2e: the provider was given the 90 second limit and the grounding tool", prov.calls[0].timeout_s == 90 and prov.calls[0].use_grounding)
wd = d.withdraw(rid, A)
check("e2e: withdraw takes the run's venues back and marks the run withdrawn", wd.ok and count(s, "venues") == 0 and StoreRuns(s).get(rid)["status"] == "withdrawn"
      and count(s, "organizations") == 0 and count(s, "locations") == 0)

hstore = MemoryDocStore("test_"); hsink = VenueSink(hstore)
v0 = VC.get(hstore, hsink.save(cand(name="Plain Cafe", op="Plain Cafe LLC", street="2 Plain St"), CTX()).ids["venue"][0]).data
hr = hsink.save(cand(name="Hours Cafe", op="Hours Cafe LLC", street="9 Hours St", public_hours="Mon-Fri 7am-5pm, Sat 8am-3pm"), CTX())
hv = VC.get(hstore, hr.ids["venue"][0]).data
check("hours: the public hours are saved as readable text in the availability notes, labelled as web hours to check",
      hv.get("availability_notes") == "Public hours per the web (check before relying on them): Mon-Fri 7am-5pm, Sat 8am-3pm", hv.get("availability_notes"))
check("hours: they never become structured open days (a person sets the real class window)", not hv.get("availability_hours"), hv.get("availability_hours"))
check("hours: a place with no hours gets no availability notes", "availability_notes" not in v0, v0.get("availability_notes"))
check("hours: the hours fact keeps its mark and is asked for as an optional fact",
      "public_hours" in hv["discovery"]["marks"] and [f.tier for f in FINDER.ask_fields if f.key == "public_hours"] == ["optional"])
long_ = hsink.save(cand(name="Long Hours", op="Long Hours Co", street="1 Long St", public_hours="x" * 300), CTX())
check("hours: the longest allowed hours fit in the venue record", long_.status == "saved" and len(VC.get(hstore, long_.ids["venue"][0]).data["availability_notes"]) <= 1000)

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
