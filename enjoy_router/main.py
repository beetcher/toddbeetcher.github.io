"""Firebase entry point for the registration endpoint (Cloud Functions for Firebase, Python).

    POST  .../enjoy_registration_request   body: a registration_request as JSON

All the rules are in core.py; the HTTP handling is in handler.py. This file only connects
them to Firebase: the request in, the Firestore store, CORS, and the settings.

Settings (environment variables, none required):
  ICDT_ALLOWED_ORIGINS   comma-separated browser origins allowed to call this (default: the site and local dev)
  ICDT_VISITOR_SALT      salt for hashing visitor addresses in the rate limiter
  ICDT_RATE_RULES        override the rate limit, as window_seconds:max pairs, for example "600:1000,86400:5000".
                         For a test deployment only (a live test run sends 30 requests from one address).
                         A warning is logged at startup whenever it is set. Leave it unset for real use.
  ICDT_ADMIN_KEY         the one key that locks the Console and the CRUD test endpoint (32+ characters)
Emulator only (honored only when FUNCTIONS_EMULATOR is "true", or ICDT_STORE=memory for local tests):
  ICDT_FIXED_NOW         a fixed UTC clock, so date rules are repeatable in tests (set on the emulator's command line, see README)
  ICDT_STORE=memory      use the in-memory store seeded from the test records, no Firestore needed
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from datetime import datetime, timezone

from firebase_functions import https_fn, options

from core import Schemas
from console import handle_console, make_failure_limiter
from crud_endpoint import handle_crud_test
from handler import handle_http
from ratelimit import DEFAULT_RULES, RateLimiter, parse_rules, visitor_key

logging.basicConfig(level=logging.INFO)

DEFAULT_ORIGINS = (
    "https://beetcher.com",
    "https://www.beetcher.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8788",
)
ORIGINS = [o.strip() for o in os.environ.get("ICDT_ALLOWED_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(",") if o.strip()]
SALT = os.environ.get("ICDT_VISITOR_SALT", "icdt-enjoy")
ADMIN_KEY = os.environ.get("ICDT_ADMIN_KEY", "")  # the Console lock; never logged
LOCAL_TESTING = os.environ.get("FUNCTIONS_EMULATOR") == "true" or os.environ.get("ICDT_STORE") == "memory"

_schemas = Schemas.load()
_rate_rules = os.environ.get("ICDT_RATE_RULES")
if _rate_rules:
    logging.getLogger("enjoy_router").warning("ICDT_RATE_RULES is set (%s): the public rate limit is overridden", _rate_rules)
_limiter = RateLimiter(rules=parse_rules(_rate_rules) if _rate_rules else DEFAULT_RULES)
_console_limiter = make_failure_limiter()
_crud_limiter = make_failure_limiter()
_store = None
_doc_store = None
CRUD_TEST_PREFIX = "test_"  # fixed in code on purpose: the test endpoint can never reach a real collection


def _get_store():
    """Built on first use, so importing this file needs no network and no credentials."""
    global _store
    if _store is None:
        if os.environ.get("ICDT_STORE") == "memory":
            from memory_store import MemoryStore
            records = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "examples" / "registration_request.test_records.json"
            _store = MemoryStore(json.loads(records.read_text())["setup"]["scheduled_classes"])
        else:
            import firebase_admin
            from firebase_admin import firestore
            from firestore_store import FirestoreStore
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            _store = FirestoreStore(firestore.client(), _schemas)
    return _store


def _get_doc_store():
    """The handler-file store for the CRUD test endpoint. Collection names get the test prefix."""
    global _doc_store
    if _doc_store is None:
        if os.environ.get("ICDT_STORE") == "memory":
            from crud.memory_doc_store import MemoryDocStore
            _doc_store = MemoryDocStore(CRUD_TEST_PREFIX)
        else:
            import firebase_admin
            from firebase_admin import firestore
            from crud.firestore_doc_store import FirestoreDocStore
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            _doc_store = FirestoreDocStore(firestore.client(), CRUD_TEST_PREFIX)
    return _doc_store


def _now() -> datetime:
    fixed = os.environ.get("ICDT_FIXED_NOW")
    if fixed and LOCAL_TESTING:
        return datetime.fromisoformat(fixed.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _client_address(req) -> str:
    """The visitor's address. Google's front end appends the real client address to X-Forwarded-For,
    so the LAST entry is the one to trust; an earlier entry can be forged by the visitor."""
    forwarded = [p.strip() for p in req.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    return forwarded[-1] if forwarded else (req.remote_addr or "unknown")


@https_fn.on_request(
    invoker="public",
    cors=options.CorsOptions(cors_origins=ORIGINS, cors_methods=["POST", "OPTIONS"]),
    max_instances=5,
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
)
def enjoy_registration_request(req: https_fn.Request) -> https_fn.Response:
    result = handle_http(
        method=req.method,
        raw_body=req.get_data(),
        visitor=visitor_key(_client_address(req), SALT),
        store=_get_store(),
        schemas=_schemas,
        limiter=_limiter,
        now=_now(),
    )
    return https_fn.Response(json.dumps(result.body), status=result.status,
                             headers={"Content-Type": "application/json", **result.headers})


@https_fn.on_request(
    invoker="public",
    cors=options.CorsOptions(cors_origins=ORIGINS, cors_methods=["GET", "OPTIONS"]),
    max_instances=5,
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
)
def enjoy_console_records(req: https_fn.Request) -> https_fn.Response:
    result = handle_console(
        method=req.method,
        authorization=req.headers.get("Authorization", ""),
        params=req.args.to_dict(),
        admin_key=ADMIN_KEY,
        visitor=visitor_key(_client_address(req), SALT),
        store=_get_store(),
        limiter=_console_limiter,
        now=_now(),
    )
    return https_fn.Response(json.dumps(result.body), status=result.status,
                             headers={"Content-Type": "application/json", **result.headers})


@https_fn.on_request(
    invoker="public",
    max_instances=2,
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
)
def enjoy_crud_test(req: https_fn.Request) -> https_fn.Response:
    """Exercise the CRUD handler files with curl. Locked by the admin key; works only on test_-prefixed collections."""
    result = handle_crud_test(
        method=req.method,
        authorization=req.headers.get("Authorization", ""),
        raw_body=req.get_data(),
        admin_key=ADMIN_KEY,
        visitor=visitor_key(_client_address(req), SALT),
        store=_get_doc_store(),
        limiter=_crud_limiter,
        now=_now(),
    )
    return https_fn.Response(json.dumps(result.body), status=result.status,
                             headers={"Content-Type": "application/json", **result.headers})
