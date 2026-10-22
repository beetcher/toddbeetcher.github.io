#!/usr/bin/env python3
"""Email check: the shared format check and the notice directory. Run: python3 -B run_email_check_tests.py
(The registration form's refusal is covered by test records t20, t64 to t66 in run_tests.py.)"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsonschema import FormatChecker
from email_check import is_valid_email
from launch_comms.directory import IndividualDirectory

n = bad = 0
def check(label, ok):
    global n, bad
    n += 1
    if not ok:
        bad += 1
    print(("ok   " if ok else "FAIL ") + label)

for a in ("name@gmail.com", "name+test23@gmail.com", "Name.Last@Gmail.COM", "a.b@c-d.org", "x@sub.domain.co"):
    check("accepts " + a, is_valid_email(a) and FormatChecker().conforms(a, "email"))
for a in ("name@gmail.com+tag", "name@@gmail.com", "name@gmail", "name@", "@gmail.com", "na me@gmail.com", " name@gmail.com", "name@gmail.com.", "", "name@x.test"):
    check("refuses " + repr(a), not is_valid_email(a) and not FormatChecker().conforms(a, "email"))
check("a non-text value is left to the type rule", is_valid_email(None) and is_valid_email(5))

d = IndividualDirectory(None)
check("directory: good address is used", d.lookup({"type": "adhoc", "email": "a+t@gmail.com"}).preferred_channel == "email")
check("directory: bad address alone means no contact", d.lookup({"type": "adhoc", "email": "a@gmail.com+t"}) is None)
c = d.lookup({"type": "adhoc", "email": "a@gmail.com+t", "phone": "3035550100"})
check("directory: bad address with a phone falls back to text", c is not None and c.email is None and c.preferred_channel == "text")
print("\n%d/%d checks passed" % (n - bad, n))
sys.exit(1 if bad else 0)
