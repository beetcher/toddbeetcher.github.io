#!/usr/bin/env python3
"""Break-it check for the timing log, ONLY the rules about who may write and read (demo level: the fast server test is run once per break).
Run from enjoy_router/:  python3 mutate_performance.py"""
import os, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
E, P, S = HERE / "crud_endpoint.py", HERE / "access" / "policy.py", HERE / "crud" / "performance_service.py"
C = HERE / "crud" / "performance_events_crud.py"
M = [
 ("the Inspector may record a timing (a write)", E, "        if access.inspector:\n            return _door.forbidden(tag)\n        args = body.get", "        args = body.get"),
 ("the role is taken from the sender, not the server", S, 'data["role_key"] = access.role_key or "unknown"', 'data.setdefault("role_key", access.role_key or "unknown")'),
 ("the person is taken from the sender (no stamp)", E, "performance_service.record(store, access, args, who, now=now)", 'performance_service.record(store, access, args, args.get("created_by", who), now=now)'),
 ("anyone can read the log (no capability needed)", P, '"performance_events": ("view_performance",),', '"performance_events": ("view_console",),'),
 ("the log can be created through the Console CRUD", C, "def create(*_a, **_k):", "def _x(*_a, **_k):"),
 ("the log can be edited through the Console CRUD", C, "def update(*_a, **_k):", "def _y(*_a, **_k):"),
 ("the one-per-10-seconds limit is gone", S, "if t - _last.get(actor, -1e9) < MIN_GAP_SECONDS:", "if False:"),
 ("the log is written into the activity log", HERE / "crud" / "activity_log.py", ', "performance_events"})', '})'),
]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); survivors = []
for label, f, a, b in M:
    src = f.read_text(encoding="utf-8")
    if src.count(a) != 1: print("CANNOT APPLY:", label); survivors.append(label); continue
    f.write_text(src.replace(a, b), encoding="utf-8")
    try: caught = subprocess.run([sys.executable, "-B", str(HERE / "run_performance_tests.py")], capture_output=True, text=True, timeout=120, cwd=HERE, env=env).returncode != 0
    finally: f.write_text(src, encoding="utf-8")
    print(("caught   " if caught else "SURVIVED ") + label, flush=True)
    if not caught: survivors.append(label)
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
sys.exit(1 if survivors else 0)
