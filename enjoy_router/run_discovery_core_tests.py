#!/usr/bin/env python3
"""Tests for the Discovery core (discovery/): one group per rule D-1..D-18 of claude/discovery-module-plan.md, the two-finder
portability test (a venue-shaped finder and a toy high-school-track finder through the SAME engine) and the port contract kit.
Nothing is called or saved outside memory. Run from enjoy_router/:  python3 run_discovery_core_tests.py  (-v lists every check)."""
import ast, json, pathlib, sys
from datetime import datetime, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import discovery  # noqa: E402
from discovery import contract_kit, cost, marks, parse, prompt as P  # noqa: E402
from discovery.contract import (AreaEntry, Candidate, FieldSpec, Finder, Limits, ModelEntry, PromptEntry, ProviderResult,
                                RunRequest, TypeEntry)  # noqa: E402
from discovery.memory_stores import FakeProvider, MemoryAreas, MemoryCatalog, MemoryRunStore, MemorySink  # noqa: E402
from discovery.modes import resolve_mode  # noqa: E402
from discovery.pipeline import Discovery, REASONS  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

# ---------------------------------------------------------------- two finders, defined as data
VENUE = json.loads((SCHEMAS / "venue.schema.json").read_text())["properties"]
S_TEXT = {"type": "string", "minLength": 1, "maxLength": 200}
def norm(s): return " ".join(str(s).lower().split())
def venue_key(v): return f"{norm(v['name'])}|{norm(v['operator'])}|{norm(v.get('street') or v['city'])}"
VENUE_FINDER = Finder(
    key="venue", name="Meeting places", result_key="venues",
    ask_fields=(FieldSpec("name", "the place's name", "needed", VENUE["name"]),
                FieldSpec("operator", "who runs it", "needed", S_TEXT),
                FieldSpec("city", "city", "needed", S_TEXT), FieldSpec("state", "state code", "needed", {"type": "string", "pattern": "^[A-Z]{2}$"}),
                FieldSpec("street", "street address", "optional", S_TEXT),
                FieldSpec("website_url", "web page", "optional", VENUE["website_url"]),
                FieldSpec("is_public_venue", "open to the public, not a private home", "needed", {"type": "boolean"})),
    dedupe_key=venue_key, must_be_true={"is_public_venue": "private_home"}, attention_if_missing={"street": "no_street_address"})
def track_key(v): return f"{norm(v['school_name'])}|{norm(v['district'])}"
TRACK_FINDER = Finder(
    key="high_school_track", name="High school tracks", result_key="tracks",
    ask_fields=(FieldSpec("school_name", "school", "needed", S_TEXT), FieldSpec("district", "school district", "needed", S_TEXT),
                FieldSpec("town", "town", "needed", S_TEXT),
                FieldSpec("lane_count", "lanes", "optional", {"type": "integer", "minimum": 4, "maximum": 12})),
    dedupe_key=track_key)

MODEL = ModelEntry("m1", "fake", "fake-1", "Fake one", price_input_per_million_cents=1000, price_output_per_million_cents=4000,
                   price_search_per_1000_cents=500, max_output_tokens=2000, has_grounding=True)
AREAS = [AreaEntry("a1", "Boulder County", "region", "CO", True, True, ("80301", "80302")),
         AreaEntry("a2", "Larimer County", "region", "CO", True, True, ()),
         AreaEntry("a3", "Texas county", "region", "TX", True, False, ("75001",)),
         AreaEntry("a4", "Off region", "region", "CO", False, True, ()),
         AreaEntry("a5", "Mesa", "region", "CO", True, True, ())]
PROMPT = "Find {types} in {territory}. Up to {max_results}.\n{fields}"
def types_for(key): return [(key, TypeEntry("cafe", "Cafes", "independent cafes")), (key, TypeEntry("lib", "Libraries")),
                            (key, TypeEntry("old", "Old type", is_active=False))]
def catalog(key="venue", **kw):
    return MemoryCatalog(models=[MODEL, ModelEntry("m2", "fake", "x", "Off", 1, 1, is_active=False)], types=types_for(key),
                         prompts=[PromptEntry("p1", 3, PROMPT)], published={key: "p1"}, **kw)

def v(name, op="Library District", city="Boulder", street="1 Main St", public=True, mark="sure", src="https://e.org/a", **extra):
    def f(val, m=mark): return {"value": val, "mark": m, **({"source_url": src} if src else {})}
    item = {"name": f(name), "operator": f(op), "city": f(city), "state": f("CO"), "is_public_venue": f(public)}
    if street: item["street"] = f(street)
    item.update(extra)
    return item
def reply(*items, key="venues", out=300, inp=200):
    return ProviderResult("ok", text="```json\n" + json.dumps({key: list(items)}) + "\n```", input_tokens=inp, output_tokens=out)

class Env:
    def __init__(self, finder=VENUE_FINDER, replies=None, mode="live", cat=None, areas=None, sink=None, provider=None):
        self.mode = mode
        self.provider = provider or FakeProvider("fake", replies)
        self.runs = MemoryRunStore()
        self.sink = sink or MemorySink(finder.dedupe_key, "item")
        self.cat = cat or catalog(finder.key)
        self.d = Discovery([finder], {"fake": self.provider}, MemoryAreas(areas or AREAS), self.cat, self.runs, self.sink,
                           mode_fn=lambda: self.mode, clock=lambda: NOW)
    def plan(self, areas=("a1",), types=("cafe",), n=20, cap=500, model="m1", key="venue"):
        return self.d.plan(RunRequest(key, model, tuple(areas), tuple(types), n, cap), "user:todd")
    def go(self, rid, limit=60):
        last = None
        for _ in range(limit):
            last = self.d.step(rid, "user:todd")
            if not last.ok or last.data.get("done"): break
        return last
    def run(self, rid): return self.runs.get(rid)

# ================================================================ D-1 core is product-blind, stdlib + jsonschema only; D-15 no way out
core = sorted((HERE / "discovery").glob("*.py"))
allowed = set(sys.stdlib_module_names) | {"jsonschema"}
forbidden = {"socket", "http", "urllib", "smtplib", "ssl", "requests", "ftplib", "subprocess", "os"}
bad_imports, net, words = [], [], []
for f in core:
    tree = ast.parse(f.read_text())
    for n in ast.walk(tree):
        mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else \
               [(n.module or "").split(".")[0]] if isinstance(n, ast.ImportFrom) and n.level == 0 else []
        for m in mods:
            if m and m not in allowed: bad_imports.append((f.name, m))
            if m in forbidden: net.append((f.name, m))
    low = f.read_text().lower()
    words += [(f.name, w) for w in ("venue", "public library", "cafe", "colorado", "launch", "firestore", "firebase") if w in low]
check("D-1 core imports only the standard library and jsonschema", not bad_imports, bad_imports)
check("D-1 core never mentions what a finder finds", not words, words)
check("D-15 core imports nothing that can reach the network, a shell or the environment", not net, net)

# ================================================================ D-5 mode
check("D-5 mode: three modes", all(resolve_mode({"DISCOVERY_MODE": m}) == m for m in ("off", "dry_run", "live")))
check("D-5 mode: unset, junk and odd case fail closed to off", resolve_mode({}) == "off" and resolve_mode({"DISCOVERY_MODE": "go"}) == "off"
      and resolve_mode({"DISCOVERY_MODE": ""}) == "off" and resolve_mode({"DISCOVERY_MODE": " LIVE "}) == "live")
e = Env(mode="off"); r = e.plan()
check("D-5 mode off refuses to plan", not r.ok and r.code == "mode_off")
check("D-5 unconfigured module refuses", not discovery.is_configured() and discovery.plan(None, "x").code == "mode_off")
e = Env(mode="dry_run"); rid = e.plan().data["run_id"]; last = e.go(rid)
run = e.run(rid)
check("D-5 dry_run makes no provider call and spends nothing", not e.provider.calls and run["actual_cost_cents"] == 0
      and run["steps"][0]["status"] == "skipped" and run["run_mode"] == "dry_run" and last.data["status"] == "finished")
check("D-5 dry_run still builds and stores the exact prompt (D-18)", "Cafes" in run["steps"][0]["prompt_text"])
e = Env(replies=lambda r: reply(v("A")), mode="live"); rid = e.plan(types=("cafe", "lib")).data["run_id"]
e.d.step(rid, "u"); e.mode = "off"; last = e.d.step(rid, "u")
check("D-5 mode switched to off mid-run stops the run (mode_off)", e.run(rid)["stop_reason"] == "mode_off" and len(e.provider.calls) == 1)
e = Env(replies=lambda r: reply(v("A")), mode="live"); rid = e.plan().data["run_id"]; e.mode = "dry_run"; e.go(rid)
check("D-5 a live run never calls the AI when the mode is no longer live", not e.provider.calls)
e = Env(mode="dry_run"); rid = e.plan().data["run_id"]; e.mode = "live"; e.go(rid)
check("D-5 a dry run never becomes live", not e.provider.calls)

# ================================================================ D-9 inactive things cannot run, D-16 settings maximums
cases = [("area off", dict(areas=("a4",)), "area_inactive"), ("state off", dict(areas=("a3",)), "area_inactive"),
         ("unknown area", dict(areas=("zz",)), "unknown_area"), ("type off", dict(types=("old",)), "type_inactive"),
         ("unknown type", dict(types=("nope",)), "unknown_type"), ("model off", dict(model="m2"), "model_inactive"),
         ("unknown model", dict(model="zz"), "unknown_model"), ("unknown finder", dict(key="zz"), "unknown_finder"),
         ("over cap (D-16)", dict(cap=1001), "over_cap"), ("over results (D-16)", dict(n=101), "over_results"),
         ("no areas", dict(areas=()), "bad_request"), ("duplicate type", dict(types=("cafe", "cafe")), "bad_request"),
         ("zero results", dict(n=0), "bad_request")]
for label, kw, code in cases:
    r = Env().plan(**kw)
    check(f"D-9/D-16 {label} refused as {code}", not r.ok and r.code == code, r.code)
check("D-9/D-16 every refusal code is in the closed list", all(Env().plan(**kw).code in REASONS for _, kw, _ in cases))
e = Env(); rid = e.plan(types=("cafe", "lib")).data["run_id"]; e.d.step(rid, "u")
e.cat.models["m1"] = ModelEntry("m1", "fake", "fake-1", "Fake", 1, 1, is_active=False); e.d.step(rid, "u")
check("D-9 a model switched off after the plan stops the run", e.run(rid)["status"] == "stopped")
no_prompt = Env(cat=MemoryCatalog(models=[MODEL], types=types_for("venue"), published={})).plan()
check("no published prompt is refused", no_prompt.code == "no_prompt")
bad = Env(cat=MemoryCatalog(models=[MODEL], types=types_for("venue"), prompts=[PromptEntry("p1", 1, "Find {oops}")], published={"venue": "p1"}))
check("a prompt with an unknown placeholder is refused", bad.plan().code == "bad_prompt")
check("too many steps (more than 40) refused", Env(cat=catalog(), areas=[AreaEntry(f"x{i}", f"X{i}", "region", "CO", True, True) for i in range(21)])
      .plan(areas=[f"x{i}" for i in range(21)], types=("cafe", "lib")).code == "too_many_steps")

# ================================================================ D-18 the prompt: stored per step, placeholders, editable
e = Env(replies=lambda r: reply(v("A", street=None)), mode="live"); rid = e.plan(areas=("a1", "a2"), types=("cafe", "lib")).data["run_id"]
last = e.go(rid); run = e.run(rid)
check("D-18 one prompt per type x area is stored on the run", len(run["steps"]) == 4 and run["steps_planned"] == 4
      and all(s["prompt_text"] for s in run["steps"]))
check("D-18 the stored prompt is exactly what the provider received", [s["prompt_text"] for s in run["steps"]] == [c.prompt for c in e.provider.calls])
check("D-18 placeholders filled: area, ZIPs, type, count, fields", "Boulder County (ZIP codes: 80301, 80302)" in e.provider.calls[0].prompt
      and "Cafes: independent cafes" in e.provider.calls[0].prompt and "Up to 10." in e.provider.calls[0].prompt
      and "operator (needed)" in e.provider.calls[0].prompt and "Larimer County" in e.provider.calls[2].prompt)
check("D-18 the run remembers which prompt version it used", run["prompt_id"] == "p1" and run["prompt_version"] == 3)
e.cat.prompts["p1"] = PromptEntry("p1", 4, "NEW WORDING {types} {territory} {max_results} {fields}")
e2 = Env(cat=e.cat, replies=lambda r: reply(v("A")), mode="live"); rid2 = e2.plan().data["run_id"]; e2.go(rid2)
check("D-18 editing the prompt changes the next run's text", e2.provider.calls[0].prompt.startswith("NEW WORDING"))
check("D-18 prompt text checker", P.check_text("a {types} {x}", ("types",)) == [{"issue": "unknown_placeholder", "name": "x"}]
      and P.check_text("a { b", ("types",)) == [{"issue": "stray_brace"}] and P.check_text("{types} ok", ("types",)) == [])
check("D-18 inserted text is never scanned for placeholders", P.render("{a} {b}", {"a": "{b}", "b": "x"}) == "{b} x")
e3 = Env(cat=MemoryCatalog(models=[MODEL], types=types_for("venue"), prompts=[PromptEntry("p1", 1, "x" * 20000 + "{types}{territory}{max_results}{fields}")],
                            published={"venue": "p1"}), mode="dry_run")
rid3 = e3.plan().data["run_id"]; e3.go(rid3)
check("D-18 a long stored prompt is cut to the record limit", len(e3.run(rid3)["steps"][0]["prompt_text"]) == 8000)

# ================================================================ finding and saving
e = Env(replies=lambda r: reply(v("Louisville Library", street=None), v("Boulder Cafe", op="Beans Inc", mark="sure", src=None)), mode="live")
rid = e.plan().data["run_id"]; e.go(rid); run = e.run(rid)
recs = list(e.sink.records.values())
check("candidates are created", run["created_count"] == 2 and len(recs) == 2 and run["found_count"] == 2)
check("D-6 every candidate is saved inactive", all(r["status"] == "inactive" for r in recs))
cafe = next(r for r in recs if r["values"]["name"] == "Boulder Cafe")
check("D-3 'sure' without a source is stored as verify", cafe["block"]["marks"]["name"] == "verify" and cafe["block"]["marks"]["city"] == "verify")
lib = next(r for r in recs if r["values"]["name"] == "Louisville Library")
check("D-3 'sure' with a source stays sure and the source is kept", lib["block"]["marks"]["name"] == "sure" and lib["block"]["source_urls"] == ["https://e.org/a"])
check("D-17 no street address: kept, flagged, reason recorded", lib["block"]["needs_attention"] is True
      and lib["block"]["attention_reasons"] == ["no_street_address"] and "street" not in lib["block"]["marks"] and run["attention_count"] == 1)
check("block carries run, model, prompt version and time", lib["block"]["run_id"] == rid and lib["block"]["model_name"] == "fake-1"
      and lib["block"]["prompt_version"] == 3 and lib["block"]["found_at"] == "2026-10-17T12:00:00Z")
check("D-12 created ids are filed on the run", run["created_item_ids"] == list(e.sink.records) and run["status"] == "finished")

# D-6: a sink that saves something not inactive is not counted
e = Env(replies=lambda r: reply(v("A")), mode="live"); e.sink.record_status = "active"; rid = e.plan().data["run_id"]; e.go(rid)
run = e.run(rid)
check("D-6 a record the sink saved as active is not counted as created and its id is still filed for withdrawal",
      run["created_count"] == 0 and run["rejected_count"] == 1 and run["rejections"][0]["reason"] == "not_saved_inactive" and run["created_item_ids"])

# D-7 duplicates
e = Env(replies=lambda r: reply(v("Same Place"), v("same  place "), v("Same Place", op="Other Org")), mode="live")
rid = e.plan().data["run_id"]; e.go(rid); run = e.run(rid)
check("D-7 same name + same operator + same place twice in one answer: one record, one duplicate", run["created_count"] == 2 and run["duplicate_count"] == 1)
check("D-7 a different operator is a different venue", len({r["key"] for r in e.sink.records.values()}) == 2)
rid = e.plan().data["run_id"]; e.go(rid); run = e.run(rid)
check("D-7 a second run does not duplicate; the duplicate is skipped and the existing record untouched",
      run["created_count"] == 0 and run["duplicate_count"] == 3 and len(e.sink.records) == 2)
e = Env(replies=lambda r: reply(v("Twin"), v("twin")), mode="live", sink=MemorySink(lambda _v: None, "item")); rid = e.plan().data["run_id"]; e.go(rid)
check("D-7 the core itself drops a repeat inside one run, even if the sink would not", e.run(rid)["created_count"] == 1 and e.run(rid)["duplicate_count"] == 1)

e = Env(replies=lambda r: reply(v("X", street=None), v("X", street=None, city="Boulder")), mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
check("D-7 no street address: matched on name + operator + city", e.run(rid)["created_count"] == 1)

# D-8 distrust of the answer, D-10 no private homes
junk = v("Fine Place"); junk["secret_field"] = {"value": "x", "mark": "sure"}
bad1 = v("No City"); del bad1["city"]
bad2 = v("Bad State"); bad2["state"] = {"value": "Colorado", "mark": "sure"}
home = v("Smith House", public=False)
bad3 = v("Odd Url", website_url={"value": "https://e.org/" + "x" * 400, "mark": "sure", "source_url": "https://e.org"})
e = Env(replies=lambda r: reply(junk, bad1, bad2, home, bad3, "not an object"), mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
run = e.run(rid); saved = {r["values"]["name"]: r for r in e.sink.records.values()}
check("D-8 unknown fields are dropped", "secret_field" not in saved["Fine Place"]["values"] and "secret_field" not in saved["Fine Place"]["block"]["marks"])
check("D-8 a bad optional value is dropped, the record kept", "Odd Url" in saved and "website_url" not in saved["Odd Url"]["values"])
by_reason = {x.get("name", ""): x for x in run["rejections"]}
check("D-8 missing/invalid needed field: rejected, naming the fields only",
      by_reason["No City"]["fields"] == ["city"] and by_reason["Bad State"]["fields"] == ["state"] and "Colorado" not in json.dumps(run["rejections"]))
check("D-10 a private home is rejected", by_reason["Smith House"]["reason"] == "private_home" and "Smith House" not in saved)
check("D-8 a non-object item is rejected", any(x["reason"] == "not_an_object" for x in run["rejections"]) and run["rejected_count"] == 4)
e = Env(replies=[ProviderResult("ok", text="I could not find anything, sorry.", input_tokens=10, output_tokens=5)], mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
check("D-8 an unreadable answer is a no_answer step, not a crash", e.run(rid)["steps"][0]["status"] == "no_answer" and e.run(rid)["steps"][0]["error_code"] == "unreadable_answer")
check("parse reads fenced and bare JSON", parse.parse_items('x ```json\n{"a": [1]}\n``` y', "a") == [1] and parse.parse_items('{"a": [2]}', "a") == [2]
      and parse.parse_items('{"b": []}', "a") is None and parse.parse_items(None, "a") is None and parse.parse_items("{bad", "a") is None)

# D-2 provider never breaks the engine; D-11 keys
class Boom:
    name = "fake"
    def generate(self, request): raise RuntimeError("SECRET-sk-123 provider says no")
e = Env(provider=Boom(), mode="live"); rid = e.plan().data["run_id"]; last = e.go(rid); run = e.run(rid)
check("D-2 a provider that raises becomes a no_answer step with a fixed code", run["steps"][0]["status"] == "no_answer"
      and run["steps"][0]["error_code"] == "provider_failed" and last.ok)
check("D-2 nothing the provider said is stored", "SECRET" not in json.dumps(run) and "SECRET" not in json.dumps(vars(last)))
e = Env(replies=[ProviderResult("weird")], mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
check("D-2 a provider answering outside the contract is a no_answer", e.run(rid)["steps"][0]["status"] == "no_answer")
e = Env(replies=[ProviderResult("rejected", error_code="refused")], mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
check("a refused call is recorded as a rejected step with its code", e.run(rid)["steps"][0]["status"] == "rejected" and e.run(rid)["steps"][0]["error_code"] == "refused")
e = Env(replies=lambda r: ProviderResult("no_answer", error_code="timeout"), mode="live"); rid = e.plan(areas=("a1", "a2", "a5"), types=("cafe", "lib")).data["run_id"]; e.go(rid)
check("three no_answers in a row stop the run", e.run(rid)["stop_reason"] == "too_many_no_answers" and len(e.provider.calls) == 3)
e = Env(replies=lambda r: reply(v("A")), mode="live"); e.cat.models["m1"] = ModelEntry("m1", "fake", "fake-1", "F", 1, 1, key_name="MY_KEY_NAME", is_active=True)
rid = e.plan().data["run_id"]; e.go(rid)
check("D-11 the provider is given the key NAME only; no key is stored on the run", e.provider.calls[0].key_name == "MY_KEY_NAME"
      and not hasattr(e.provider.calls[0], "api_key") and "MY_KEY_NAME" not in json.dumps(e.run(rid)))

# D-4 cost and the cap
check("D-4 cost rounds up to whole cents", cost.cost_cents(MODEL, 1, 1, 0) == 1 and cost.cost_cents(MODEL, 0, 0, 0) == 0
      and cost.cost_cents(MODEL, 1_000_000, 0, 0) == 1000 and cost.cost_cents(MODEL, 0, 0, 1) == 1)
check("D-4 estimate is a range, low <= high", (lambda lh: 0 < lh[0] <= lh[1])(cost.estimate(MODEL, [600] * 4, [10] * 4)))
check("D-4 step limits fit the remaining money in the worst case", all(
    (lambda lim: lim is None or cost.cost_cents(MODEL, cost.tokens_from_chars(800), lim[0], lim[1]) <= rem)(cost.step_limits(MODEL, 800, rem)) for rem in range(0, 600, 7)))
check("D-4 not enough money for a useful answer means no call", cost.step_limits(MODEL, 800, 1) is None)
worst = lambda r: ProviderResult("ok", text=json.dumps({"venues": []}), input_tokens=cost.tokens_from_chars(len(r.prompt)),
                                 output_tokens=r.max_output_tokens, searches=r.max_searches)
ok = True
for cap in (0, 3, 10, 25, 60, 120):
    e = Env(replies=worst, mode="live"); rid = e.plan(areas=("a1", "a2", "a5"), types=("cafe", "lib"), cap=cap).data["run_id"]; e.go(rid); run = e.run(rid)
    ok &= run["actual_cost_cents"] <= cap and (cap > 0 or not e.provider.calls)
    ok &= all(c.max_output_tokens <= 2000 for c in e.provider.calls)
check("D-4 spend never exceeds the cap, even when every call uses its whole allowance", ok)
e = Env(replies=worst, mode="live"); rid = e.plan(areas=("a1", "a2", "a5"), types=("cafe", "lib"), cap=25).data["run_id"]; e.go(rid)
check("D-4 a run that runs out of money stops as cap_reached", e.run(rid)["stop_reason"] == "cap_reached" and e.run(rid)["status"] == "stopped")
e = Env(replies=lambda r: reply(v("A")), mode="live"); rid = e.plan().data["run_id"]; e.go(rid); run = e.run(rid)
check("actual cost and tokens are added up on the run", run["actual_cost_cents"] == cost.cost_cents(MODEL, 200, 300, 0) and run["input_tokens"] == 200 and run["output_tokens"] == 300)

# D-14 results limit
many = lambda r: reply(*[v(f"Place {i}") for i in range(30)])
e = Env(replies=many, mode="live"); rid = e.plan(areas=("a1", "a2"), types=("cafe", "lib"), n=7).data["run_id"]; e.go(rid); run = e.run(rid)
check("D-14 never more candidates than the run's limit", run["created_count"] == 7 == len(e.sink.records) and run["stop_reason"] in ("results_limit", None)
      and all(f"Up to {min(10, 7)}." in c.prompt or "Up to" in c.prompt for c in e.provider.calls))
check("D-14 the AI is asked for no more than is still allowed", e.provider.calls[0].prompt.count("Up to 7.") == 1)

# D-12, D-13 history and withdraw
e = Env(replies=lambda r: reply(v("Keep Me"), v("Take Back"), v("Edited")), mode="live"); rid = e.plan().data["run_id"]; e.go(rid)
ids = e.run(rid)["created_item_ids"]; e.sink.records[ids[0]]["status"] = "active"; e.sink.touched.add(ids[2])
r = e.d.withdraw(rid, "user:todd"); run = e.run(rid)
check("D-13 withdraw removes untouched candidates and keeps activated or edited ones", r.ok and r.data["removed"] == {"item": 1}
      and sorted(r.data["kept"]) == sorted([ids[0], ids[2]]) and e.sink.records[ids[1]].get("withdrawn"))
check("D-12 the run record stays, marked withdrawn, with who and when", run["status"] == "withdrawn" and run["withdrawn_by"] == "user:todd" and run["withdrawn_at"])
check("D-13 a withdrawn run cannot be withdrawn twice", e.d.withdraw(rid, "u").code == "nothing_to_withdraw")
e = Env(mode="dry_run"); rid = e.plan().data["run_id"]; e.go(rid)
check("D-13 a dry run has nothing to withdraw", e.d.withdraw(rid, "u").code == "nothing_to_withdraw")
e = Env(replies=lambda r: reply(v("A")), mode="live"); rid = e.plan(types=("cafe", "lib")).data["run_id"]; e.d.step(rid, "u")
check("stop: operator stop ends the run and later steps are refused", e.d.stop(rid, "u").ok and e.run(rid)["stop_reason"] == "operator"
      and e.d.step(rid, "u").code == "run_not_active" and e.d.stop(rid, "u").code == "run_not_active")
check("unknown run ids", e.d.step("zz", "u").code == "run_not_found" and e.d.stop("zz", "u").code == "run_not_found" and e.d.withdraw("zz", "u").code == "run_not_found")
check("D-12 the run store offers no delete", not any(hasattr(MemoryRunStore, n) for n in ("delete", "remove", "clear")))

# never raises
e = Env(replies=lambda r: reply(v("A")), mode="live"); rid = e.plan().data["run_id"]; e.runs.fail = True
res = [e.d.step(rid, "u"), e.d.plan(RunRequest("venue", "m1", ("a1",), ("cafe",), 5, 5), "u"), e.d.stop(rid, "u"), e.d.withdraw(rid, "u")]
check("a failing store never raises into the caller", all(isinstance(r.ok, bool) for r in res) and all(r.code == "internal_error" for r in res[:2]))
class Evil(MemorySink):
    def save(self, *a, **k): raise RuntimeError("db down")
e = Env(replies=lambda r: reply(v("A")), mode="live", sink=Evil(venue_key)); rid = e.plan().data["run_id"]; last = e.go(rid)
check("a failing sink fails the run, never raises", last.code == "internal_error" and e.run(rid)["status"] == "failed")

# ================================================================ portability: a second finder through the same engine
def track(name, district="Boulder Valley SD", **kw):
    f = lambda x: {"value": x, "mark": "sure", "source_url": "https://school.example/t"}
    d = {"school_name": f(name), "district": f(district), "town": f("Boulder")}
    d.update(kw); return d
e = Env(finder=TRACK_FINDER, replies=lambda r: reply(track("Fairview HS", lane_count={"value": 8, "mark": "sure", "source_url": "https://a.org"}),
        track("fairview hs"), track("Boulder HS", lane_count={"value": 99, "mark": "verify"}), key="tracks"), mode="live")
rid = e.plan(key="high_school_track").data["run_id"]; e.go(rid); run = e.run(rid)
recs = {r["values"]["school_name"]: r for r in e.sink.records.values()}
check("PORT a toy 'high school track' finder runs through the unchanged engine", run["finder_key"] == "high_school_track"
      and run["created_count"] == 2 and run["duplicate_count"] == 1 and set(recs) == {"Fairview HS", "Boulder HS"})
check("PORT its own schema limits apply (lane_count 99 dropped, record kept)", "lane_count" not in recs["Boulder HS"]["values"] and recs["Fairview HS"]["values"]["lane_count"] == 8)
check("PORT its own dedupe rule applies (school + district)", len(e.sink.records) == 2)
check("PORT the prompt asks for ITS fields", "school_name (needed)" in e.provider.calls[0].prompt and "operator" not in e.provider.calls[0].prompt)
two = Discovery([VENUE_FINDER, TRACK_FINDER], {"fake": FakeProvider("fake", lambda r: reply(track("A HS"), key="tracks"))}, MemoryAreas(AREAS),
                MemoryCatalog(models=[MODEL], types=types_for("venue") + types_for("high_school_track"),
                              prompts=[PromptEntry("p1", 1, PROMPT)], published={"venue": "p1", "high_school_track": "p1"}),
                MemoryRunStore(), MemorySink(track_key), lambda: "live", clock=lambda: NOW)
rp = two.plan(RunRequest("high_school_track", "m1", ("a1",), ("cafe",), 5, 50), "u")
check("PORT one engine can carry several finders", rp.ok and two.step(rp.data["run_id"], "u").ok)

# ================================================================ quote: the same checks and the exact prompts, nothing saved
e = Env(replies=lambda r: reply(), mode="live")
q = e.d.quote(RunRequest("venue", "m1", ("a1", "a2"), ("cafe", "lib"), 20, 500))
check("quote: estimate range, step count, model and every step's exact prompt, and NOTHING is saved", q.ok and not e.runs.runs
      and q.data["steps_planned"] == 4 and len(q.data["prompts"]) == 4 and 0 < q.data["estimated_cost_low_cents"] <= q.data["estimated_cost_high_cents"]
      and "Larimer County" in q.data["prompts"][2]["prompt_text"] and q.data["model_name"] == "fake-1")
rid = e.d.plan(RunRequest("venue", "m1", ("a1", "a2"), ("cafe", "lib"), 20, 500), "u").data["run_id"]; e.go(rid)
check("quote: the prompts it showed are the ones the run then sent", [p["prompt_text"] for p in q.data["prompts"]] == [c.prompt for c in e.provider.calls])
check("quote: refuses exactly what plan refuses", all(Env().d.quote(RunRequest("venue", kw.get("model", "m1"), tuple(kw.get("areas", ("a1",))), tuple(kw.get("types", ("cafe",))), kw.get("n", 20), kw.get("cap", 500))).code == code
      for _, kw, code in cases if "key" not in kw))
check("quote: off mode refuses", Env(mode="off").d.quote(RunRequest("venue", "m1", ("a1",), ("cafe",), 5, 5)).code == "mode_off")
e = Env(replies=lambda r: reply(v("A")), mode="live"); e.d.provider_timeout_s = 77; rid = e.plan().data["run_id"]; e.go(rid)
check("the provider is given the engine's time limit", e.provider.calls[0].timeout_s == 77)

# ================================================================ marks and contract kit
raw = v("Kit")
c, rej = marks.check_item(raw, VENUE_FINDER)
check("marks: check_item returns a Candidate with checked values", rej is None and c.values()["name"] == "Kit" and c.label == "Kit")
check("marks: an unknown mark word becomes verify", marks.check_item({**raw, "name": {"value": "Q", "mark": "maybe", "source_url": "https://x.org"}}, VENUE_FINDER)[0].fields["name"]["mark"] == "verify")
check("marks: a non-http source is not a source", marks.check_item({**raw, "name": {"value": "Q", "mark": "sure", "source_url": "ftp://x"}}, VENUE_FINDER)[0].fields["name"]["mark"] == "verify")
check("marks: empty and whitespace values count as missing", marks.check_item({**raw, "operator": {"value": "  ", "mark": "sure"}}, VENUE_FINDER)[1]["fields"] == ["operator"])
check("kit: FakeProvider keeps the provider contract", contract_kit.provider_failures(FakeProvider("fake")) == [])
class Bad:
    name = "bad"
    def generate(self, r): return ProviderResult("ok", output_tokens=r.max_output_tokens + 1, error_code="has space")
check("kit: provider contract catches an over-limit, unclean provider", len(contract_kit.provider_failures(Bad())) == 2)
check("kit: provider contract catches a raising provider", contract_kit.provider_failures(type("R", (), {"name": "r", "generate": lambda s, r: 1 / 0})()))
base = {"finder_key": "kit", "status": "planned"}
check("kit: MemoryRunStore keeps the run store contract", contract_kit.run_store_failures(MemoryRunStore(), lambda: dict(base)) == [])
class WithDelete(MemoryRunStore):
    def delete(self, i): pass
check("kit: run store with delete is caught (D-12)", contract_kit.run_store_failures(WithDelete(), lambda: dict(base)))
mk = lambda n: Candidate("", f"Item {n}", {"name": {"value": f"Item {n}", "mark": "verify"}, "operator": {"value": "Org", "mark": "verify"},
                                         "city": {"value": "Boulder", "mark": "verify"}})
check("kit: MemorySink keeps the sink contract", contract_kit.sink_failures(MemorySink(venue_key, "item"), mk) == [])
active = MemorySink(venue_key, "item"); active.record_status = "active"
check("kit: a sink that saves active records is caught (D-6)", contract_kit.sink_failures(active, mk))
check("kit: MemoryAreas keeps the area contract", contract_kit.area_failures(MemoryAreas(AREAS), "a1", "zz") == [])

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
