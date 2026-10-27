"""An in-memory document store for testing handler files. Same interface the Firestore one will have.

    get(base, id)                                  -> dict or None
    create(base, id, doc, tx=None)                 raises DocExists
    update(base, id, set_fields, delete_fields=(), expected_updated_at=None, tx=None)
                                                   raises DocMissing, StaleUpdate
    query(base, filters=(), order_by=None, descending=False, limit=100)   filters: (field, "==" or "array_contains", value); a field may be a dotted path
    transaction()                                  context manager; writes apply together or not at all

`base` is the collection name from the registry. An optional prefix (for example "test_") is added
here, so a test endpoint can never touch a real collection. `reads` logs every read, so a test can
prove an update did not read.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Optional

from .nested_arrays import decode as _decode, encode as _encode, has_nested_array as _has_nested
from .store_errors import DocExists, DocMissing, StaleUpdate  # noqa: F401  (re-exported)


def _get_path(doc, path):
    """Value at a dotted path (like Firestore field paths), or None."""
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_path(doc, path, value):
    """Set a dotted path, creating the nested objects (like Firestore update with a field path)."""
    parts = path.split(".")
    cur = doc
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _matches(doc, field, op, value):
    got = _get_path(doc, field)
    if op == "array_contains":
        return isinstance(got, list) and value in got
    if op in ("<", ">"):   # what Firestore does for a number field: a missing field never matches
        return isinstance(got, (int, float)) and not isinstance(got, bool) and (got < value if op == "<" else got > value)
    return got == value


class _Tx:
    def __init__(self):
        self.pending: list = []


class MemoryDocStore:
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self.data: dict = {}
        self.reads: list = []

    def _c(self, base: str) -> dict:
        return self.data.setdefault(self.prefix + base, {})

    def get(self, base: str, id: str) -> Optional[dict]:
        self.reads.append(("get", base, id))
        doc = self._c(base).get(id)
        return _decode(copy.deepcopy(doc)) if doc is not None else None

    def create(self, base: str, id: str, doc: dict, tx: Optional[_Tx] = None) -> None:
        def apply():
            if id in self._c(base):
                raise DocExists()
            stored = _encode(copy.deepcopy(doc))   # the same wrapping the Firestore store does (nested arrays are refused there)
            if _has_nested(stored):
                raise ValueError("nested array")
            self._c(base)[id] = stored
        (tx.pending.append(apply) if tx is not None else apply())

    def update(self, base: str, id: str, set_fields: dict, delete_fields=(), expected_updated_at: Optional[str] = None,
               tx: Optional[_Tx] = None, timeout: Optional[float] = None) -> None:
        def apply():
            cur = self._c(base).get(id)
            if cur is None:
                raise DocMissing()
            if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
                raise StaleUpdate()
            for k, v in _encode(copy.deepcopy(set_fields)).items():
                _set_path(cur, k, v)
            for f in delete_fields:
                cur.pop(f, None)
        (tx.pending.append(apply) if tx is not None else apply())

    def query(self, base: str, filters=(), order_by: Optional[str] = None, descending: bool = False,
              limit: int = 100) -> list:
        self.reads.append(("query", base))
        docs = [d for d in self._c(base).values() if all(_matches(d, f, op, v) for f, op, v in filters)]
        if order_by:
            # equal values come back in a fixed order, by id in the same direction (what Firestore does), so tests see the same order every run (DT-24)
            docs.sort(key=lambda d: (d.get(order_by) is None, d.get(order_by), str(d.get("id", ""))), reverse=descending)
        return [_decode(copy.deepcopy(d)) for d in docs[:limit]]

    @contextmanager
    def transaction(self):
        tx = _Tx()
        yield tx
        snapshot = copy.deepcopy(self.data)
        try:
            for apply in tx.pending:
                apply()
        except Exception:
            self.data = snapshot
            raise
