#!/usr/bin/env python3
"""In-memory tests for place_zones (the fix_place_zones op): Colorado places get Denver, everything else is listed, a dry run writes nothing."""
import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone  # noqa: E402
from crud import locations_crud as LOC  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
import place_zones  # noqa: E402

fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

A = "user:admin"
s = MemoryDocStore("")
def mk(name, region=None, zip_=None, tz=None):
    addr = {"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "country": "US"}
    if region: addr["region"] = region
    if zip_: addr["postal_code"] = zip_
    d = {"name": name, "addresses": [addr]}
    if tz: d["time_zone"] = tz
    r = LOC.create(s, d, A); assert r.ok, r.problems; return r.data["id"]
co = mk("Boulder Library", "CO", "80301"); az = mk("Phoenix Hall", "AZ", "85001"); inn = mk("Indy Hall", "IN", "46201"); has = mk("Already", "NY", "10001", "America/New_York"); co2 = mk("Zip only", None, "80027")
dry = place_zones.run(s, A, apply=False)
check("dry run: finds the places with no zone, writes nothing", dry["without_zone"] == 4 and dry["filled"] == 0 and all(not s.get("locations", i).get("time_zone") for i in (co, az, inn)), dry)
check("dry run lists the non-Colorado places for a person", sorted(x["name"] for x in dry["needs_a_person"]) == ["Indy Hall", "Phoenix Hall"] and dry["colorado"] == 2, dry)
done = place_zones.run(s, A, apply=True)
check("apply fills the Colorado ones with America/Denver", done["filled"] == 2 and s.get("locations", co)["time_zone"] == "America/Denver", done)
check("apply never guesses Arizona, Indiana or a place that already has a zone", not s.get("locations", az).get("time_zone") and not s.get("locations", inn).get("time_zone") and s.get("locations", has)["time_zone"] == "America/New_York")
check("a second run finds only the ones a person must fix", place_zones.run(s, A)["without_zone"] == 2)
K = "k" * 16 + "Z" * 16 + "-browser-test-key"
def door(body): return handle_admin("POST", "Bearer " + K, body, K, "v", s, make_failure_limiter(), datetime.now(timezone.utc))
r = door(b'{"collection":"locations","op":"fix_place_zones","args":{"apply":false}}')
check("through the admin door (the key is a super admin): a dry run answers with the list", r.status == 200 and r.body["data"]["without_zone"] == 2 and r.body["data"]["applied"] is False, (r.status, r.body))
check("a bad argument is refused", door(b'{"collection":"locations","op":"fix_place_zones","args":{"apply":"yes"}}').status == 400 and door(b'{"collection":"locations","op":"fix_place_zones","args":{"x":1}}').status == 400)
check("without the key: 401", handle_admin("POST", "Bearer wrong", b'{"collection":"locations","op":"fix_place_zones","args":{}}', K, "v", s, make_failure_limiter(), datetime.now(timezone.utc)).status == 401)
print("\nFAILED: %d" % len(fails) if fails else "\nOK: all place-zone tests pass"); sys.exit(1 if fails else 0)
