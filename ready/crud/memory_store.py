"""Offline transactional adapter for READY handler tests (D001).

No Firebase or network. Whole callbacks run under a reentrant lock and roll back
on exceptions or failed Results. Production Firestore must provide equivalent
read/modify/write semantics; passing these tests does not establish that proof.
"""
from copy import deepcopy
from threading import RLock


class MemoryStore:
    def __init__(self):
        self._data = {}
        self._lock = RLock()

    def transact(self, callback):
        """Commit callback atomically; failed Results and exceptions change nothing."""
        with self._lock:
            before = deepcopy(self._data)
            try:
                result = callback(self)
                if hasattr(result, "ok") and not result.ok:
                    self._data = before
                return result
            except Exception:
                self._data = before
                raise

    def get(self, collection, record_id):
        with self._lock:
            return deepcopy(self._data.get(collection, {}).get(record_id))

    def create(self, collection, record_id, data):
        with self._lock:
            bucket = self._data.setdefault(collection, {})
            if record_id in bucket:
                raise ValueError("record_exists")
            bucket[record_id] = deepcopy(data)

    def replace_metadata(self, collection, record_id, data):
        """Private persistence primitive; handlers restrict changes to lifecycle metadata."""
        with self._lock:
            if record_id not in self._data.get(collection, {}):
                raise KeyError("not_found")
            self._data[collection][record_id] = deepcopy(data)

    def query(self, collection, filters=(), limit=100):
        """Equality-only bounded foundation queries; no arbitrary public scan API."""
        with self._lock:
            rows = self._data.get(collection, {}).values()
            out = [deepcopy(row) for row in rows if all(row.get(key) == value for key, value in filters)]
            out.sort(key=lambda row: (row["created_at"], row["id"]))
            return out[:limit]
