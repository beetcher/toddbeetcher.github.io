"""An in-memory document store for testing handler files. Same interface the Firestore one will have.

    get(base, id)                                  -> dict or None
    create(base, id, doc, tx=None)                 raises DocExists
    update(base, id, set_fields, delete_fields=(), expected_updated_at=None, tx=None)
                                                   raises DocMissing, StaleUpdate
    query(base, filters=(), order_by=None, descending=False, limit=100)
    transaction()                                  context manager; writes apply together or not at all

`base` is the collection name from the registry. An optional prefix (for example "test_") is added
here, so a test endpoint can never touch a real collection. `reads` logs every read, so a test can
prove an update did not read.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Optional

from .store_errors import DocExists, DocMissing, StaleUpdate  # noqa: F401  (re-exported)


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
        return copy.deepcopy(doc) if doc is not None else None

    def create(self, base: str, id: str, doc: dict, tx: Optional[_Tx] = None) -> None:
        def apply():
            if id in self._c(base):
                raise DocExists()
            self._c(base)[id] = copy.deepcopy(doc)
        (tx.pending.append(apply) if tx is not None else apply())

    def update(self, base: str, id: str, set_fields: dict, delete_fields=(), expected_updated_at: Optional[str] = None,
               tx: Optional[_Tx] = None) -> None:
        def apply():
            cur = self._c(base).get(id)
            if cur is None:
                raise DocMissing()
            if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
                raise StaleUpdate()
            cur.update(copy.deepcopy(set_fields))
            for f in delete_fields:
                cur.pop(f, None)
        (tx.pending.append(apply) if tx is not None else apply())

    def query(self, base: str, filters=(), order_by: Optional[str] = None, descending: bool = False,
              limit: int = 100) -> list:
        self.reads.append(("query", base))
        docs = [d for d in self._c(base).values() if all(d.get(f) == v for f, op, v in filters)]
        if order_by:
            docs.sort(key=lambda d: (d.get(order_by) is None, d.get(order_by)), reverse=descending)
        return [copy.deepcopy(d) for d in docs[:limit]]

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
