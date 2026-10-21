#!/usr/bin/env python3
"""Mutation check for the Console setting: break each rule on purpose (schema, handler, capability table, wiring) and the test file must fail.
Restores every file afterwards. Run from enjoy_router/:  python3 mutate_console_setting.py"""
import subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parent
SCH = ROOT / "schemas" / "console_setting.schema.json"; HAN = HERE / "crud" / "console_settings_crud.py"
POL = HERE / "access" / "policy.py"; END = HERE / "crud_endpoint.py"
M = [
 ("minimum of 1 minute lowered to 0 (an off setting)", SCH, '"minimum": 1,\n      "maximum": 480', '"minimum": 0,\n      "maximum": 480'),
 ("maximum of 480 raised", SCH, '"maximum": 480', '"maximum": 100000'),
 ("minutes may be a fraction", SCH, '"type": "integer",\n      "minimum": 1', '"type": "number",\n      "minimum": 1'),
 ("minutes no longer required", SCH, '"required": [\n    "settings_key",\n    "session_timeout_minutes"\n  ]', '"required": [\n    "settings_key"\n  ]'),
 ("settings_key may be anything", SCH, '"const": "default"', '"type": "string"'),
 ("unknown fields allowed", SCH, '"additionalProperties": false', '"additionalProperties": true'),
 ("starting value is not 10", HAN, '"session_timeout_minutes": 10}', '"session_timeout_minutes": 60}'),
 ("a second record is allowed", HAN, 'if cur is None and live(store, H.COLLECTION):', 'if False:'),
 ("settings_key can change", HAN, 'immutable=("settings_key",)', 'immutable=()'),
 ("delete is allowed", HAN, 'def soft_delete(*_a, **_k):\n    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])', 'def soft_delete(*a, **k):\n    return H.soft_delete(*a, **k)'),
 ("list accepts filters", HAN, 'order="settings_key")', 'order="settings_key", filters=("settings_key",))'),
 ("reading needs a capability a viewer lacks", POL, '"console_settings": ("view_console",), ', '"console_settings": ("manage_access",), '),
 ("reading is super admin only", POL, '"console_settings": ("view_console",), ', '"console_settings": (SUPER_ONLY,), '),
 ("a viewer may change it", POL, '"console_settings": (SUPER_ONLY,),                    # only a super admin', '"console_settings": ("view_console",),                    # only a super admin'),
 ("the handler is not registered", END, ', "console_settings": console_settings_crud}', '}'),
]
survivors = []
try:
    for label, f, a, b in M:
        src = f.read_text(encoding="utf-8")
        if src.count(a) != 1: print("CANNOT APPLY:", label, src.count(a)); survivors.append(label + " (pattern)"); continue
        f.write_text(src.replace(a, b), encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, str(HERE / "run_console_setting_tests.py")], capture_output=True, text=True, timeout=120, cwd=HERE)
            caught = r.returncode != 0
        finally:
            f.write_text(src, encoding="utf-8")
        print(("caught   " if caught else "SURVIVED ") + label, flush=True)
        if not caught: survivors.append(label)
finally:
    pass
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)
