"""The Firestore document store for CRUD handler files. Same interface as MemoryDocStore.

    get(base, id), create(base, id, doc, tx), update(base, id, set_fields, delete_fields, expected_updated_at, tx),
    query(base, filters, order_by, descending, limit), transaction()

`base` is the collection name from the registry. The optional prefix (for example "test_") is added here, so a
test endpoint built on a prefixed store can never touch a real collection.

Without `tx`, each write happens at once. With `tx` (from `with store.transaction() as tx:`), writes are collected
and committed together as one atomic batch when the block ends; an error inside the block commits nothing.
expected_updated_at: without `tx` the compare and the write are one Firestore transaction. Inside a `tx` batch the
compare is a read made just before the batch is queued (best effort; a handler's whole-record path already
compares at its own read).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import firestore
from google.cloud.firestore_v1 import Query
from google.cloud.firestore_v1.base_query import FieldFilter

from .store_errors import DocExists, DocMissing, StaleUpdate


class _Tx:
    def __init__(self, db):
        self.batch = db.batch()
        self.count = 0


class FirestoreDocStore:
    def __init__(self, client, prefix: str = ""):
        self.db = client
        self.prefix = prefix

    def _col(self, base: str):
        return self.db.collection(self.prefix + base)

    def get(self, base: str, id: str) -> Optional[dict]:
        snap = self._col(base).document(id).get()
        return snap.to_dict() if snap.exists else None

    def create(self, base: str, id: str, doc: dict, tx: Optional[_Tx] = None) -> None:
        ref = self._col(base).document(id)
        if tx is not None:
            tx.batch.create(ref, doc)
            tx.count += 1
            return
        try:
            ref.create(doc)
        except AlreadyExists:
            raise DocExists()

    def update(self, base: str, id: str, set_fields: dict, delete_fields=(), expected_updated_at: Optional[str] = None,
               tx: Optional[_Tx] = None) -> None:
        ref = self._col(base).document(id)
        changes = dict(set_fields)
        for f in delete_fields:
            changes[f] = firestore.DELETE_FIELD
        if tx is not None:
            if expected_updated_at is not None:
                snap = ref.get()
                if not snap.exists:
                    raise DocMissing()
                if snap.to_dict().get("updated_at") != expected_updated_at:
                    raise StaleUpdate()
            tx.batch.update(ref, changes)
            tx.count += 1
            return
        if expected_updated_at is None:
            try:
                ref.update(changes)
            except NotFound:
                raise DocMissing()
            return

        @firestore.transactional
        def run(transaction):
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                raise DocMissing()
            if snap.to_dict().get("updated_at") != expected_updated_at:
                raise StaleUpdate()
            transaction.update(ref, changes)

        run(self.db.transaction())

    def query(self, base: str, filters=(), order_by: Optional[str] = None, descending: bool = False,
              limit: int = 100) -> list:
        q = self._col(base)
        for field, op, value in filters:
            q = q.where(filter=FieldFilter(field, op, value))
        if order_by:
            q = q.order_by(order_by, direction=Query.DESCENDING if descending else Query.ASCENDING)
        return [d.to_dict() for d in q.limit(limit).stream()]

    @contextmanager
    def transaction(self):
        tx = _Tx(self.db)
        yield tx
        if tx.count:
            try:
                tx.batch.commit()
            except AlreadyExists:
                raise DocExists()
            except NotFound:
                raise DocMissing()
