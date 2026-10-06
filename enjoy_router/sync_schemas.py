#!/usr/bin/env python3
"""Copy the schema files this endpoint needs into enjoy_router/schemas/ before a deploy.

    python3 enjoy_router/sync_schemas.py

The deployed function cannot see the repo's schemas/ folder, so it carries a copy. The copy is
git-ignored; run this before `firebase deploy`. It copies registry.json and every schema file the registry names.
"""
import json
import pathlib
import shutil

here = pathlib.Path(__file__).resolve().parent
src = here.parent / "schemas"
dst = here / "schemas"
dst.mkdir(exist_ok=True)
registry = json.loads((src / "registry.json").read_text())
files = ["registry.json"] + [e["schema"] for e in registry["schemas"]]
for f in files:
    shutil.copy2(src / f, dst / f)
print(f"copied {len(files)} files to {dst}")
