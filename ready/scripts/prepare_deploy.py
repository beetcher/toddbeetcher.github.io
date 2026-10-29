#!/usr/bin/env python3
"""Stage only READY as a self-contained Python Firebase function codebase.

No network or deployment. Staging avoids shipping unrelated website media and
keeps `ready` importable as a package in the Firebase runtime source root.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".firebase-build"


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    shutil.copytree(ROOT, STAGE / "ready", ignore=shutil.ignore_patterns(
        ".firebase-build", ".venv", "venv", "__pycache__", "*.pyc", ".env*", "tests", "scripts", ".git"))
    shutil.copy2(ROOT / "firebase_entry.py", STAGE / "main.py")
    shutil.copy2(ROOT / "runtime-requirements.txt", STAGE / "requirements.txt")
    print("READY function staged; no project selected or deployed.")


if __name__ == "__main__":
    main()
