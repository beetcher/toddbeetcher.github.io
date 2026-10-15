#!/usr/bin/env python3
"""Tests for the CMS core (comms/): one test group per rule in CMS_GUIDE.md section 10 (R-1 to R-26), the golden masters, and the
port contract kit. Nothing is sent: a fake channel and memory stores stand in. Run from enjoy_router/:  python3 run_comms_core_tests.py  (-v lists every check)."""
import ast, json, pathlib, sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
from comms import contract_kit  # noqa: E402
from comms.calendar_event import event_from_facts, make_ics  # noqa: E402
from comms.channels.email import EmailChannel  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from comms.contract import CONTRACT_VERSION, STATUS_OF, Contact  # noqa: E402
from comms.kinds import KindRegistry  # noqa: E402
from comms.memory_stores import MemoryDirectory, MemoryLogStore, MemorySettings, MemoryTemplateStore  # noqa: E402
from comms.settings import Settings, resolve_mode  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

KINDS = KindRegistry().load(SCHEMAS)
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
GOLD = json.loads((SCHEMAS / "message_kinds" / "golden_masters.json").read_text())
IND = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"
PERSON = Contact(name="Gladys", email="gladys@example.com", phone="+13035550100", preferred_channel="email", individual_id=IND)
A = "user:admin"

def seeded_templates(extra=()):
    ts = MemoryTemplateStore()
    for t in SEED:
        ts.add({**t})
    for t in extra:
        ts.add(t)
    return ts

def make(mode="live", contacts=None, templates=None, settings=None, channels=None, log=None, **kw):
    ch = channels if channels is not None else [FakeChannel()]
    log = log or MemoryLogStore()
    c = comms.Comms(kinds=KINDS, directory=MemoryDirectory(contacts if contacts is not None else {IND: PERSON}),
                    templates=templates or seeded_templates(), log=log, settings=MemorySettings(settings), channels=ch, mode=mode,
                    clock=lambda: NOW, **kw)
    return c, log, ch[0] if ch else None

PL = GOLD["cases"]["placement_full"]
RC = GOLD["cases"]["receipt_with_link"]
def place(c, **kw):
    args = dict(kind="placement_confirmation", recipient={"type": "individual", "individual_id": IND}, context=PL["facts"], by=A,
                trigger="automatic", refs={"attendance_id": PL["facts"]["uid"]}, audience="student")
    args.update(kw)
    return c.notify(**args)

# ---------------------------------------------------------------- golden masters through the whole pipeline (R-6, R-11, R-25)
for name, case in GOLD["cases"].items():
    c, log, ch = make()
    if case["kind"] == "request_received":
        r = c.notify("request_received", {"type": "adhoc", "name": case["inputs"]["name"], "email": case["inputs"]["email"]}, case["facts"],
                     A, "automatic", {"request_id": "6c5e1f4b-0d7a-4b82-8e9d-4f5a6b7c8d9e"}, "requester")
    else:
        r = c.notify("placement_confirmation", {"type": "individual", "individual_id": IND}, case["facts"], A, "automatic",
                     {"attendance_id": case["facts"]["uid"]}, "student")
    sent = ch.sent[0]["content"] if ch.sent else {}
    check(f"golden {name}: sent", r.status == "sent" and r.reason == "ok", str(r))
    check(f"golden {name}: subject, text, HTML match the pre-refactor bytes",
          (sent.get("subject"), sent.get("text"), sent.get("html")) == (case["expect"]["subject"], case["expect"]["text"], case["expect"]["html"]))
    if "ics" in case["expect"]:
        att = sent["attachments"]
        check(f"golden {name}: calendar file matches byte for byte (R-25)",
              len(att) == 1 and att[0][0] == "workshop.ics" and att[0][1] == "text/calendar" and att[0][2].decode("utf-8") == case["expect"]["ics"])
    else:
        check(f"golden {name}: no calendar file for a receipt", sent.get("attachments") == [])

# ---------------------------------------------------------------- R-1 the core imports nothing from LAUNCH
std = set(sys.stdlib_module_names)
bad = []
for f in (HERE / "comms").rglob("*.py"):
    for n in ast.walk(ast.parse(f.read_text())):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) and n.level == 0 else []
        for m in mods:
            top = m.split(".")[0]
            if top and top not in std and top not in ("jsonschema",):
                bad.append(f"{f.name}: {m}")
check("R-1 comms/ imports only the standard library and jsonschema", not bad, str(bad))

# ---------------------------------------------------------------- R-2 sending code lives only behind the door
LEGACY = {"cms_service.py", "placement_email.py", "registration_service.py"}   # removed in step 3; this list then becomes empty
ALLOWED = {"smtp_transport.py", "main.py", "capture_comms_golden.py"} | LEGACY
offenders = []
for f in HERE.rglob("*.py"):
    rel = f.relative_to(HERE)
    if "venv" in rel.parts or rel.parts[0] in ("comms", "launch_comms", "schemas") or f.name.startswith("run_") or f.name in ALLOWED:
        continue
    src = f.read_text()
    if "import smtplib" in src or "import smtp_transport" in src or "from smtp_transport" in src:
        offenders.append(str(rel))
check("R-2 no sending code outside the CMS, the transport, the wiring and the two legacy senders", not offenders, str(offenders))

# ---------------------------------------------------------------- R-3 notify never raises, and a log failure is survived
class Boom:
    def lookup(self, r): raise RuntimeError("directory down")
c, log, ch = make(); c.directory = Boom()
try:
    r = place(c); ok = True
except Exception:
    ok = False
check("R-3 a directory failure does not raise", ok)
check("R-3 …and is reported as internal_error, logged", r.status == "not_sent" and r.reason == "internal_error" and log.entries[-1]["reason"] == "internal_error")
class BoomCh(FakeChannel):
    def send(self, *a, **k): raise RuntimeError("provider down")
c, log, _ = make(channels=[BoomCh()])
r = place(c)
check("R-3 a channel that raises does not raise through notify", r.reason == "internal_error")
c, log, ch = make(log=MemoryLogStore(fail=True))
r = place(c)
check("R-3/R-7 a log write failure does not raise; the message still goes; log_id is None", r.status == "sent" and r.log_id is None and len(ch.sent) == 1)

# ---------------------------------------------------------------- R-5 context validation
c, log, ch = make()
bad_ctx = [("missing required fact", {k: v for k, v in PL["facts"].items() if k != "title"}), ("unknown fact", {**PL["facts"], "surprise": "x"}),
           ("bad format", {**PL["facts"], "start_utc": "tomorrow"}), ("not a dict", ["x"]), ("not plain JSON", {**PL["facts"], "title": {1, 2}})]
for label, ctx in bad_ctx:
    r = place(c, context=ctx)
    check(f"R-5 {label}: not_sent / invalid_context, nothing sent", r.reason == "invalid_context" and r.status == "not_sent" and not ch.sent)
check("R-5 unknown kind", place(c, kind="nope").reason == "unknown_kind")
check("R-5 audience not offered by the kind", place(c, audience="martian").reason == "invalid_context")
check("R-5 bad recipient", place(c, recipient={"type": "alien"}).reason == "invalid_context")
check("R-5 bad trigger", place(c, trigger="whenever").reason == "invalid_context")

# ---------------------------------------------------------------- R-6 fixed order: the earlier step wins when several fail at once
c, log, ch = make(mode="off", contacts={})
check("R-6 invalid beats mode off", place(c, context={}).reason == "invalid_context")
check("R-6 mode off beats everything after validation", place(c).reason == "cms_off")
c, log, ch = make(contacts={})
log.entries.append({"dedupe_key": f"placement_confirmation:{IND}:attendance_id={PL['facts']['uid']}", "status": "sent"})
check("R-6 duplicate beats no_contact", place(c).reason == "duplicate")
c, log, ch = make(contacts={})
check("R-6 no_contact beats exclusion", place(c, suppress=[IND]).reason == "no_contact")
c, log, ch = make(contacts={IND: replace(PERSON, preferred_channel="text")})
check("R-6 exclusion beats channel_unavailable", place(c, suppress=[IND]).reason == "excluded")
check("R-6 channel_unavailable beats no_template", c.notify(**{**dict(kind="placement_confirmation", recipient={"type": "individual", "individual_id": IND}, context=PL["facts"], by=A, trigger="automatic", audience="student")}).reason == "channel_unavailable")
c, log, ch = make(templates=MemoryTemplateStore())
check("R-6 no_template beats incomplete/log_only", place(c).reason == "no_template")
unguarded = {"kind": "placement_confirmation", "channel": "email", "audience": "student", "name": "x", "subject": "S {where}", "is_active": True,
             "blocks": [{"type": "paragraph", "text": "Hi"}]}
facts_no_where = {k: v for k, v in PL["facts"].items() if k != "where"}
c, log, ch = make(mode="log_only", templates=seeded_templates()); c.templates = MemoryTemplateStore(); c.templates.add(unguarded)
check("R-6 incomplete beats log_only", place(c, context=facts_no_where).reason == "incomplete")

# ---------------------------------------------------------------- R-7 one log entry per call, whatever happens; R-17 no body; R-23 contract version; R-14 map
c, log, ch = make()
results = [place(c), place(c, context={}), place(c, kind="nope"), place(c, trigger="manual"), place(c, suppress=[IND])]
check("R-7 exactly one log entry per call", len(log.entries) == len(results) == 5)
check("R-7 every result carries its log id", all(r.log_id for r in results))
SCH = json.loads((SCHEMAS / "communication_log.schema.json").read_text())
props = set(SCH["properties"])
check("R-17 log entries carry only schema fields and never message text", all(set(e) - {"id", "created_at", "created_by"} <= props for e in log.entries)
      and not any(k in e for e in log.entries for k in ("text", "html", "body")))
check("R-23 contract_version recorded on every entry", all(e["contract_version"] == CONTRACT_VERSION for e in log.entries))
check("R-14 every result's status is the one its reason maps to", all(STATUS_OF[e["reason"]] == e["status"] for e in log.entries))
schema_map = {}
for blk in SCH["allOf"]:
    for r_ in blk["if"]["properties"]["reason"]["enum"]:
        schema_map[r_] = blk["then"]["properties"]["status"]["const"]
check("R-14 the code's reason-to-status map equals the schema's", schema_map == STATUS_OF, str(set(schema_map.items()) ^ set(STATUS_OF.items())))
check("R-7 required log fields are always present", all({"kind", "channel", "status", "reason", "trigger", "contract_version"} <= set(e) for e in log.entries))

# ---------------------------------------------------------------- R-8 one channel per person
both = Contact(name="G", email="g@example.com", phone="+13035550100", preferred_channel="email", individual_id=IND)
em, tx = FakeChannel("email"), FakeChannel("text")
c, log, _ = make(contacts={IND: both}, channels=[em, tx], settings=Settings(is_text_on=True))
place(c)
check("R-8 a person with both gets only their preferred channel", len(em.sent) == 1 and len(tx.sent) == 0)
em, tx = FakeChannel("email"), FakeChannel("text")
c, log, _ = make(contacts={IND: replace(both, preferred_channel="text")}, channels=[em], settings=Settings())
r = place(c)
check("R-8 a text-preferring person with no text channel gets NO email: not_sent / channel_unavailable", r.reason == "channel_unavailable" and not em.sent)
check("R-20 …and the entry waits in the hand-contact queue (not_sent)", log.entries[-1]["status"] == "not_sent")
c, log, _ = make(settings=Settings(is_email_on=False)); r = place(c)
check("R-19 the email switch off makes email unavailable", r.reason == "channel_unavailable")

# ---------------------------------------------------------------- R-9 duplicates
c, log, ch = make()
a, b = place(c), place(c)
check("R-9 the same event twice: second is skipped / duplicate", (a.status, b.status, b.reason) == ("sent", "skipped", "duplicate") and len(ch.sent) == 1)
m = place(c, trigger="manual")
check("R-9 a manual send bypasses the duplicate check", m.status == "sent" and len(ch.sent) == 2)
check("R-9 a different explicit dedupe_key is a different event", place(c, dedupe_key="class-changed-2").status == "sent")
ch2 = FakeChannel(outcome="rejected", error_code="recipient_rejected"); c, log, _ = make(channels=[ch2])
place(c); ch2.outcome = "accepted"
check("R-9 a failed attempt does not block the retry", place(c).status == "sent")
ch3 = FakeChannel(outcome="no_answer"); c, log, _ = make(channels=[ch3])
place(c)
check("R-9 an unknown attempt blocks an automatic repeat (it may have gone)", place(c).reason == "duplicate")

# ---------------------------------------------------------------- R-10 suppression and mute
c, log, ch = make()
check("R-10 suppress by individual id", place(c, suppress=[IND]).reason == "excluded")
check("R-10 suppress by address, case-insensitive", place(c, suppress=["GLADYS@example.com"], dedupe_key="b").reason == "excluded")
check("R-10 someone else in the list changes nothing", place(c, suppress=["other@example.com"], dedupe_key="c").status == "sent")
c, log, ch = make(contacts={IND: replace(PERSON, muted=True)})
check("R-10 a muted person is skipped / muted", place(c).reason == "muted" and not ch.sent)

# ---------------------------------------------------------------- R-11 / R-21 template resolution
draft = {**SEED[1], "status": "draft", "version": 2, "subject": "DRAFT {when_short}"}
c, log, ch = make(templates=seeded_templates([draft]))
place(c)
check("R-11 a draft is never sent", ch.sent[0]["content"]["subject"].startswith("Launch — you're scheduled"))
off = {**SEED[1], "is_active": False}
ts = MemoryTemplateStore(); ts.add({**SEED[1], "is_active": False})
c, log, ch = make(templates=ts)
check("R-11 an inactive template: not_sent / no_template", place(c).reason == "no_template")
old = MemoryTemplateStore(); first = old.add({**SEED[1]}); old.add({**SEED[1], "version": 2, "previous_id": first["id"], "subject": "NEW {when_short}"})
c, log, ch = make(templates=old); place(c)
check("R-11 the standing (newest published) version is used and its number logged", ch.sent[0]["content"]["subject"].startswith("NEW") and log.entries[-1]["template_version"] == 2)
check("R-11 a channel/audience with no template: not_sent / no_template", make(templates=seeded_templates())[0].notify(
    "request_received", {"type": "individual", "individual_id": IND}, RC["facts"], A, "automatic", audience="requester").status == "sent")

# ---------------------------------------------------------------- R-12 placeholders
check("R-12 a template using a fact the kind lacks is refused", KINDS.check_template({**SEED[1], "subject": "{nonsense}"}) != [])
check("R-12 an optional fact used outside its own show_if is refused", KINDS.check_template(unguarded | {"subject": "S {where}"}) != [])
check("R-12 the seed templates pass", all(KINDS.check_template(t) == [] for t in SEED))
check("R-12 a stray brace is refused", KINDS.check_template({**SEED[0], "subject": "Hi {name"}) != [])

# ---------------------------------------------------------------- R-13 modes, redirect, settings
c, log, ch = make(mode="log_only"); r = place(c)
check("R-13 log_only renders and logs but never sends", r.reason == "log_only" and not ch.sent and log.entries[-1].get("subject") and log.entries[-1]["channel"] == "email")
c, log, ch = make(mode="off"); r = place(c)
check("R-13 off sends nothing and renders nothing (no subject logged)", r.reason == "cms_off" and not ch.sent and "subject" not in log.entries[-1])
c, log, ch = make(mode="bogus"); check("R-13 an unknown mode fails closed to off", c.mode == "off" and place(c).reason == "cms_off")
c, log, ch = make(settings=Settings(test_redirect_address="todd+test@example.com")); place(c)
check("R-13 the test redirect replaces the address and is logged", ch.sent[0]["to"] == "todd+test@example.com" and log.entries[-1]["is_redirected"] and log.entries[-1]["to"] == "todd+test@example.com")
check("R-19 mode comes from the environment: COMMS_MODE wins", resolve_mode({"ICDT_COMMS_MODE": "log_only", "ICDT_CMS_ENABLED": "true"}) == "log_only")
check("R-19 …the old switch maps true to live", resolve_mode({"ICDT_CMS_ENABLED": "true"}) == "live")
check("R-19 …false or missing means off; junk means off", resolve_mode({}) == "off" and resolve_mode({"ICDT_COMMS_MODE": "party"}) == "off")
c, log, ch = make(settings=Settings(sender_name="Launch Team", from_address="hi@example.com", reply_to="todd@example.com", footer="Footer line & more."))
place(c)
st = ch.sent[0]["settings"]
check("R-19 sender name, from and reply-to come from the settings record", (st.sender_name, st.from_address, st.reply_to) == ("Launch Team", "hi@example.com", "todd@example.com"))
check("R-19 the footer is added after the last block, escaped in HTML", ch.sent[0]["content"]["text"].endswith("Launch\n\nFooter line & more.\n")
      and ch.sent[0]["content"]["html"].endswith("<p>Launch</p><p>Footer line &amp; more.</p></body></html>"))

# ---------------------------------------------------------------- R-15 the core only appends and reads
class Spy(MemoryLogStore):
    def __init__(self): super().__init__(); self.calls = []
    def append(self, *a, **k): self.calls.append("append"); return super().append(*a, **k)
    def find_by_dedupe_key(self, k): self.calls.append("find"); return super().find_by_dedupe_key(k)
spy = Spy(); c, _, _ = make(log=spy); place(c); place(c)
check("R-15 the core only appends and looks up; it never updates or deletes", set(spy.calls) <= {"append", "find"})
check("R-15 the log schema is append-only", SCH["x_history"] == "append_only")

# ---------------------------------------------------------------- R-22 time budget
t = [0.0]
class Slow(FakeChannel):
    def send(self, *a, **k):
        t[0] += 1.0
        return super().send(*a, **k)
slow = Slow(); c, log, _ = make(channels=[slow], monotonic=lambda: t[0])
items = [dict(kind="placement_confirmation", recipient={"type": "individual", "individual_id": IND}, context=PL["facts"], by=A,
              trigger="automatic", refs={"attendance_id": PL["facts"]["uid"]}, audience="student", dedupe_key=f"k{i}") for i in range(5)]
res = c.notify_many(items, 2.5)
check("R-22 notify_many returns one result per item, in order", len(res) == 5)
check("R-22 items inside the budget are sent", [r.status for r in res[:3]] == ["sent"] * 3)
check("R-22 items beyond the budget are logged not_sent / time_budget (nobody dropped silently)",
      [r.reason for r in res[3:]] == ["time_budget"] * 2 and len(log.entries) == 5 and all(e["reason"] == "time_budget" for e in log.entries[3:]))

# ---------------------------------------------------------------- R-26 message_ref
c, log, ch = make(); place(c)
check("R-26 the message_ref is recorded on a sent message", log.entries[-1]["message_ref"] == ch.sent[0]["message_ref"] and log.entries[-1]["message_ref"])
ch4 = FakeChannel(outcome="no_answer"); c, log, _ = make(channels=[ch4]); place(c)
check("R-26 …and on an unknown one, so a later report can still be matched", log.entries[-1].get("message_ref") and log.entries[-1]["status"] == "unknown")

# ---------------------------------------------------------------- the module door
comms.configure(None)
check("R-2 unconfigured, the door answers skipped / cms_off and sends nothing", comms.notify("x", {}, {}, A, "automatic").reason == "cms_off")
c, log, ch = make(); comms.configure(c)
check("R-2 configured, the door is the pipeline", comms.notify(**dict(kind="placement_confirmation", recipient={"type": "individual", "individual_id": IND}, context=PL["facts"], by=A, trigger="automatic", audience="student")).status == "sent")
comms.configure(None)

# ---------------------------------------------------------------- R-18 the contract kit, on the fakes and the email channel
class Res:
    def __init__(self, ok, code): self.ok, self.code = ok, code
sent_args = []
def sender(key, to, subject, text, html, attachments, headers):
    sent_args.append((key, to, subject, text, html, attachments, headers)); return Res(True, "accepted")
for label, mk in (("FakeChannel", lambda: FakeChannel()), ("EmailChannel", lambda: EmailChannel(sender, lambda: "key"))):
    fl = contract_kit.channel_contract(mk)
    check(f"R-18 {label} passes the channel contract", not fl, str(fl))
fl = contract_kit.log_store_contract(MemoryLogStore); check("R-18 MemoryLogStore passes the log store contract", not fl, str(fl))
fl = contract_kit.template_store_contract(MemoryTemplateStore, lambda s, r: s.add(r)); check("R-18 MemoryTemplateStore passes the template store contract", not fl, str(fl))
fl = contract_kit.directory_contract(lambda: MemoryDirectory({IND: PERSON}), IND); check("R-18 MemoryDirectory passes the directory contract", not fl, str(fl))
em = EmailChannel(sender, lambda: "key")
check("R-18 the email channel passes headers and attachments through", em.send("a@example.com", {"subject": "S", "text": "T", "html": "H", "attachments": [("f.ics", "text/calendar", b"x")]},
      Settings(sender_name="Launch", reply_to="r@example.com"), "<id@x>").outcome == "accepted"
      and sent_args[-1][6] == {"from_name": "Launch", "message_id": "<id@x>", "reply_to": "r@example.com"} and sent_args[-1][5] == [("f.ics", "text/calendar", b"x")])
for label, res_, want in (("unknown", Res(False, "unknown"), ("no_answer", "unknown")), ("refused", Res(False, "recipient_rejected"), ("rejected", "recipient_rejected")),
                          ("junk code", Res(False, "Bad Code!"), ("rejected", "smtp_failed")), ("ok but not accepted", Res(True, "weird"), ("rejected", "smtp_failed"))):
    e2 = EmailChannel(lambda *a, r=res_: r, lambda: "k"); r = e2.send("a@example.com", dict(contract_kit.CONTENT), Settings(), None)
    check(f"R-18 email channel maps a {label} provider answer", (r.outcome, r.error_code) == want, str(r))
def raiser(*a): raise TimeoutError("slow")
r = EmailChannel(raiser, lambda: "k").send("a@example.com", dict(contract_kit.CONTENT), Settings(), None)
check("R-18 email channel turns a raised provider error into no_answer and never leaks text", (r.outcome, r.error_code) == ("no_answer", "unknown"))

# ---------------------------------------------------------------- R-25 the calendar helper on its own
ev = event_from_facts(PL["facts"], {"uid": "uid", "title": "title", "start": "start_utc", "end": "end_utc", "venue": "venue", "room": "room",
                                    "address": "address", "lead": "lead", "confirmation": "confirmation_number", "notes": "notes"})
check("R-25 the calendar helper reproduces the golden file", make_ics(ev, NOW).decode("utf-8") == PL["expect"]["ics"])
check("R-25 …and a cancel method is supported for later", b"METHOD:CANCEL" in make_ics(ev, NOW, method="CANCEL"))

print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "\nFAILED:\n - " + "\n - ".join(fails)))
sys.exit(1 if fails else 0)
