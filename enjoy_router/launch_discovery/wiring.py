"""Puts the Discovery engine together for LAUNCH: the venue finder, the stores over the handlers, the venue sink, the three provider
adapters, and the run mode from the environment (ICDT_DISCOVERY_MODE: off, dry_run or live; unset or anything else is off).
Also the read-only status the Console shows (mode, which model keys are present, whether the ZIP table is loaded).
"""
from __future__ import annotations

import contextlib
import os

from crud import geocoder
from crud import discovery_models_crud as MO
from discovery.modes import resolve_mode
from discovery.pipeline import Discovery

from . import zip_table
from .providers.build import build_providers
from .stores import StoreAreas, StoreCatalog, StoreRuns
from .venue_finder import FINDER
from .venue_sink import VenueSink

MODE_VAR = "ICDT_DISCOVERY_MODE"
DEFAULT_PROJECT = "launch-ai-workshop"
PROVIDER_TIMEOUT_S = 90


def project_id(environ) -> str:
    return environ.get("ICDT_DISCOVERY_PROJECT") or environ.get("GCLOUD_PROJECT") or DEFAULT_PROJECT


def mode_of(environ) -> str:
    return resolve_mode(environ, MODE_VAR)


def build_engine(store, environ=None, providers=None, clock=None) -> Discovery:
    env = os.environ if environ is None else environ
    return Discovery([FINDER], providers if providers is not None else build_providers(project_id(env)),
                     StoreAreas(store), StoreCatalog(store), StoreRuns(store), VenueSink(store),
                     mode_fn=lambda: mode_of(env), clock=clock, provider_timeout_s=PROVIDER_TIMEOUT_S)


def status(store, environ=None) -> dict:
    """What the Console's Run tab needs to know that is not in the database. Never contains a key."""
    env = os.environ if environ is None else environ
    names = sorted({m["key_name"] for m in MO.list(store).data["records"] if m.get("key_name")})
    t = zip_table.table()
    return {"mode": mode_of(env), "keys": {n: bool(env.get(n)) for n in names}, "project": project_id(env),
            "zip_table": {"loaded": bool(t), "zip_count": len(t or {}), "states": zip_table.states_loaded()}}


@contextlib.contextmanager
def no_gps():
    """Discovery never looks up GPS while it saves (a person does that after activating a venue; it would also eat the call's time)."""
    saved = geocoder.lookup
    geocoder.lookup = None
    try:
        yield
    finally:
        geocoder.lookup = saved
