#!/usr/bin/env python3
"""Put the starting Discovery settings into the LIVE system through the admin door (safe to run again: it only adds what is missing).

    python3 seed_discovery.py            adds the settings record, models, the 50 states and DC, the four venue types and the venue prompt
    python3 seed_discovery.py regions    adds the starter Colorado regions (needs the ZIP table deployed first)

What it adds (everything is editable in the Console afterwards):
  settings  100 cents starting cap, 1000 cents maximum, 100 results a run, 10 a step
  models    Gemini 3.8 Flash and Gemini 3.5 Flash-Lite (on); Claude Haiku 5.5, Claude Sonnet 5.5 and OpenAI gpt-6-luna (OFF until their
            keys are set; the record names the key setting, never the key)
  areas     all 50 states and DC; ONLY Colorado is switched on
  types     independent coffee shops and cafes, public libraries, Panera Bread locations, community centers and senior centers
  prompt    the venue prompt, published as version 1
Prices are whole US cents per million tokens (searches: per 1,000), taken from the providers' price pages on 2026-10-17; the Gemini
3.x Flash prices are promotional through 2026-12-31, so check the Models list then. The key is read from .env.launch-ai-workshop and never printed."""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
          "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
          "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
          "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
          "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
          "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
          "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
          "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
MODELS = [
    dict(provider="gemini", model_name="gemini-3.8-flash", label="Gemini 3.8 Flash (Google search)", price_input_per_million_cents=75,
         price_output_per_million_cents=375, search_price_per_1000_cents=1400, max_output_tokens=8192, has_grounding=True, is_active=True,
         notes="Uses the Google project, no key. $0.75 in / $3.75 out per million tokens (promotional through 2026-12-31); Google Search grounding $14 per 1,000 after 5,000 free a month."),
    dict(provider="gemini", model_name="gemini-3.5-flash-lite", label="Gemini 3.5 Flash-Lite (cheapest)", price_input_per_million_cents=30,
         price_output_per_million_cents=250, search_price_per_1000_cents=1400, max_output_tokens=8192, has_grounding=True, is_active=True,
         notes="Uses the Google project, no key. $0.30 in / $2.50 out per million tokens; grounding $14 per 1,000 after 5,000 free a month."),
    dict(provider="claude", model_name="claude-haiku-5-5", label="Claude Haiku 5.5", price_input_per_million_cents=10, price_output_per_million_cents=50,
         search_price_per_1000_cents=1000, max_output_tokens=8192, has_grounding=True, key_name="ICDT_CLAUDE_KEY", is_active=False,
         notes="OFF until ICDT_CLAUDE_KEY is set. The published price is 'from $0.10 in / $0.50 out'; check the exact price. Web search $10 per 1,000."),
    dict(provider="claude", model_name="claude-sonnet-5-5", label="Claude Sonnet 5.5", price_input_per_million_cents=200, price_output_per_million_cents=1000,
         search_price_per_1000_cents=1000, max_output_tokens=8192, has_grounding=True, key_name="ICDT_CLAUDE_KEY", is_active=False,
         notes="OFF until ICDT_CLAUDE_KEY is set. $2 in / $10 out per million tokens. Web search $10 per 1,000."),
    dict(provider="openai", model_name="gpt-6-luna", label="OpenAI gpt-6-luna", price_input_per_million_cents=10, price_output_per_million_cents=50,
         search_price_per_1000_cents=1000, max_output_tokens=8192, has_grounding=True, key_name="ICDT_OPENAI_KEY", is_active=False,
         notes="OFF until ICDT_OPENAI_KEY is set. $0.10 in / $0.50 out per million tokens. Web search $10 per 1,000 calls."),
]
TYPES = [
    dict(key="coffee_shops", label="Independent coffee shops and cafes", sort_order=1, is_chain=False,
         search_hint="Independent (not chain) coffee shops, cafes and roasters with seating where a small group can sit and talk for an hour or two. Prefer ones with character: a back room, a quiet corner, a long table."),
    dict(key="libraries", label="Public libraries", sort_order=2, is_chain=False,
         search_hint="Public library branches that have a meeting room or a quiet table area a small group can use."),
    dict(key="panera", label="Panera Bread locations", sort_order=3, is_chain=True,
         search_hint="Panera Bread restaurants: they have reliable seating, wifi and a predictable layout. The operator is Panera Bread."),
    dict(key="community_centers", label="Community centers and senior centers", sort_order=4, is_chain=False,
         search_hint="Community centers, recreation centers and senior centers that have a lounge or a room a small group can use."),
]
REGIONS = [  # starter regions; ZIP lists are checked against the ZIP table. Edit them in the Console.
    dict(name="Boulder", zip_codes=["80301", "80302", "80303", "80304", "80305"]),
    dict(name="Louisville and Lafayette", zip_codes=["80027", "80026"]),
    dict(name="Longmont", zip_codes=["80501", "80503", "80504"]),
]


def _data(r): return (r[1] or {}).get("data") or {}
def _records(call, coll, **flt): 
    r = call(coll, "list", limit=200, **({"filters": flt} if flt else {}))
    return _data(r).get("records", []) if r[0] == 200 else None


def seed(call, say=print, regions=False):
    """Add what is missing. Returns {"added": {...}, "errors": [...]}."""
    added, errors = {}, []
    def add(coll, data, label):
        r = call(coll, "create", data=data, source="import")
        if r[0] == 200:
            added[coll] = added.get(coll, 0) + 1
            return _data(r)
        errors.append(f"{label}: {(r[1] or {}).get('error', {}).get('problems') or r[0]}")
        say(f"  REFUSED {label}")
        return None
    if regions:
        states = {a["state_code"] for a in (_records(call, "discovery_areas", kind="state") or [])}
        have = {(a["state_code"], a["name"].lower()) for a in (_records(call, "discovery_areas", kind="region") or [])}
        for rg in REGIONS:
            if ("CO", rg["name"].lower()) not in have:
                add("discovery_areas", {"kind": "region", "state_code": "CO", "is_active": True, **rg}, "region " + rg["name"])
        return {"added": added, "errors": errors}
    if _records(call, "discovery_settings") == []:
        add("discovery_settings", {}, "settings")
    have = {(m["provider"], m["model_name"]) for m in (_records(call, "discovery_models") or [])}
    for m in MODELS:
        if (m["provider"], m["model_name"]) not in have:
            add("discovery_models", m, "model " + m["model_name"])
    have = {a["state_code"] for a in (_records(call, "discovery_areas", kind="state") or [])}
    for code, name in STATES.items():
        if code not in have:
            add("discovery_areas", {"kind": "state", "state_code": code, "name": name, "is_active": code == "CO"}, "state " + code)
    have = {t["key"] for t in (_records(call, "discovery_types", finder_key="venue") or [])}
    for t in TYPES:
        if t["key"] not in have:
            add("discovery_types", {"finder_key": "venue", "is_active": True, **t}, "type " + t["key"])
    if not _records(call, "discovery_prompts", finder_key="venue"):
        text = json.loads((HERE.parent / "schemas" / "examples" / "discovery_prompt.examples.json").read_text())["valid"]["venue_seed_prompt"]
        made = add("discovery_prompts", {"finder_key": "venue", "name": "Venue search (starting wording)", "text": text["text"]}, "prompt")
        if made:
            r = call("discovery_prompts", "publish", id=made["id"])
            if r[0] != 200:
                errors.append("publish prompt")
    return {"added": added, "errors": errors}


def main(argv):
    from run_org_test_suite import make_call, read_key
    res = seed(make_call(read_key()), regions="regions" in argv[1:])
    print("Done. Added:", json.dumps(res["added"]) if res["added"] else "nothing (everything was already there)")
    for e in res["errors"]:
        print("  PROBLEM:", e)
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
