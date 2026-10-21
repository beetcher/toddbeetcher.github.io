"""The ActivityStore: a document store that writes an activity entry with every document write (P-46).

It wraps the real store (Firestore, or the in-memory one in tests) and has the same interface, so every handler and service that writes
through it is covered without changing a line: the Console door, the Discovery door and engine, the comms service and the sign-in check all
share the Console's store. For each create and update of a logged collection it builds the entry (activity_log.py) and writes it in the SAME
all-or-nothing step as the change, so a change cannot happen without its entry and an entry cannot outlive a change that failed.

    store = ActivityStore(FirestoreDocStore(client, ""))

Not covered, on purpose (ACTIVITY_EVENT_GUIDE.md section 3): the log's own collection and the other logs (EXCLUDED_COLLECTIONS), names the
registry does not know, and an update made with a bounded `timeout` (the comms status write after a send). A fault while building an entry
is NOT swallowed: the write fails, because a change with no proof is the thing this log exists to prevent.
"""
from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from . import activity_log as AL
from .activity_log import EXCLUDED_COLLECTIONS, QUIET_FIELDS  # noqa: F401  (re-exported for tests and the guide)


class ActivityStore:
    def __init__(self, inner, clock: Optional[Callable[[], datetime]] = None):
        self.inner = inner
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._last_ms = 0
        self._lock = threading.Lock()

    def __getattr__(self, name):   # prefix, reads, data and anything else the real store has
        return getattr(self.inner, name)

    def _sequence_ms(self) -> int:
        """Strictly increasing within this process, so two changes in the same second keep their order."""
        with self._lock:
            ms = int(self._clock().timestamp() * 1000)
            if ms <= self._last_ms:
                ms = self._last_ms + 1
            self._last_ms = ms
            return ms

    # -- reads pass straight through
    def get(self, base, id):  # noqa: A002
        return self.inner.get(base, id)

    def query(self, base, filters=(), order_by=None, descending=False, limit=100):
        return self.inner.query(base, filters, order_by, descending, limit)

    def transaction(self):
        return self.inner.transaction()

    # -- writes
    def _together(self, write, tx):
        """Run `write(tx)` in the caller's transaction, or in one of our own so the record and its entry still land together."""
        if tx is not None:
            write(tx)
            return
        with self.inner.transaction() as own:
            write(own)

    @staticmethod
    def _pending(tx) -> dict:
        """What this transaction has already queued for each record (the real store cannot see it until the transaction ends), so a record created
        and then changed in one transaction, or changed twice, still gets an entry per write with the right before and after."""
        if tx is None:
            return {}
        if not hasattr(tx, "_activity_docs"):
            tx._activity_docs = {}
        return tx._activity_docs

    def create(self, base, id, doc, tx=None):  # noqa: A002
        info = AL.collection_info(base)
        if info is None:
            return self.inner.create(base, id, doc, tx=tx)
        entry = AL.entry_for_create(info, id, doc, self._sequence_ms(), self._clock())
        if tx is not None:
            self._pending(tx)[(base, id)] = copy.deepcopy(doc)

        def write(t):
            self.inner.create(base, id, doc, tx=t)
            self.inner.create(AL.COLLECTION, entry["id"], entry, tx=t)
        self._together(write, tx)

    def update(self, base, id, set_fields, delete_fields=(), expected_updated_at=None, tx=None, timeout=None):  # noqa: A002
        info = AL.collection_info(base)
        if info is None or timeout is not None:
            return self.inner.update(base, id, set_fields, delete_fields, expected_updated_at, tx=tx, timeout=timeout)
        pend = self._pending(tx)
        before = pend[(base, id)] if (base, id) in pend else self.inner.get(base, id)
        entry = None if before is None else AL.entry_for_update(info, id, before, set_fields, delete_fields, self._sequence_ms(), self._clock())
        if tx is not None and before is not None:
            pend[(base, id)] = AL.apply_changes(before, set_fields, delete_fields)
        if entry is None:   # a missing record (the real store raises as it always did), or nothing worth an entry
            return self.inner.update(base, id, set_fields, delete_fields, expected_updated_at, tx=tx)

        def write(t):
            self.inner.update(base, id, set_fields, delete_fields, expected_updated_at, tx=t)
            self.inner.create(AL.COLLECTION, entry["id"], entry, tx=t)
        self._together(write, tx)
