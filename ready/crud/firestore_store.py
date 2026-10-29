"""Native Firestore persistence for READY, with buffered real transactions.

D003: SDK writes are queued until all callback reads finish, so service/handler
composition never violates Firestore's read-before-write rule. A retry reruns the
whole callback; no HTTP/email/AI side effects occur in it. No extra collection.
The SDK is imported only when this adapter is selected, not for offline tests.
"""
from copy import deepcopy
from datetime import datetime, timezone


def encode(value, field=""):
    if isinstance(value, dict):
        return {key: encode(child, key) for key, child in value.items()}
    if isinstance(value, list):
        return [encode(child) for child in value]
    if isinstance(value, str) and (field.endswith("_at") or field == "at"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def decode(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: decode(child) for key, child in value.items()}
    if isinstance(value, list):
        return [decode(child) for child in value]
    return value


class _Rejected(Exception):
    def __init__(self, result):
        self.result = result


class FirestoreStore:
    def __init__(self, project):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
        self.sdk = firestore
        self.filter = FieldFilter
        self.db = firestore.Client(project=project)

    def get(self, collection, record_id):
        snap = self.db.collection(collection).document(record_id).get()
        return decode(snap.to_dict()) if snap.exists else None

    def query(self, collection, filters=(), limit=100):
        query = self.db.collection(collection)
        for key, value in filters:
            query = query.where(filter=self.filter(key, "==", encode(value, key)))
        query = query.order_by("created_at").limit(limit)
        return [decode(snap.to_dict()) for snap in query.stream()]

    def create(self, collection, record_id, data):
        self.db.collection(collection).document(record_id).create(encode(data))

    def replace_metadata(self, collection, record_id, data):
        # Existing record updates must be transactional to preserve version guards.
        raise RuntimeError("metadata_update_requires_transaction")

    def transact(self, callback):
        @self.sdk.transactional
        def run(transaction):
            view = _View(self, transaction)
            result = callback(view)
            if hasattr(result, "ok") and not result.ok:
                raise _Rejected(result)
            view.flush()
            return result
        try:
            return run(self.db.transaction(max_attempts=5))
        except _Rejected as reject:
            return reject.result


class _View:
    def __init__(self, store, transaction):
        self.store, self.transaction = store, transaction
        self.pending = {}
        self.reads = {}

    def get(self, collection, record_id):
        key = (collection, record_id)
        if key in self.pending:
            return deepcopy(self.pending[key][1])
        if key not in self.reads:
            snap = self.store.db.collection(collection).document(record_id).get(transaction=self.transaction)
            self.reads[key] = decode(snap.to_dict()) if snap.exists else None
        return deepcopy(self.reads[key])

    def query(self, collection, filters=(), limit=100):
        query = self.store.db.collection(collection)
        for key, value in filters:
            query = query.where(filter=self.store.filter(key, "==", encode(value, key)))
        rows = {snap.id: decode(snap.to_dict()) for snap in query.order_by("created_at").limit(limit).stream(transaction=self.transaction)}
        for (base, record_id), (_, value) in self.pending.items():
            if base == collection:
                rows[record_id] = deepcopy(value)
        values = [row for row in rows.values() if all(row.get(key) == value for key, value in filters)]
        values.sort(key=lambda row: (row["created_at"], row["id"]))
        return values[:limit]

    def create(self, collection, record_id, data):
        if self.get(collection, record_id) is not None:
            raise ValueError("record_exists")
        self.pending[(collection, record_id)] = ("create", deepcopy(data))

    def replace_metadata(self, collection, record_id, data):
        if self.get(collection, record_id) is None:
            raise KeyError("not_found")
        kind = self.pending.get((collection, record_id), ("update",))[0]
        self.pending[(collection, record_id)] = (kind, deepcopy(data))

    def transact(self, callback):
        before = deepcopy(self.pending)
        try:
            result = callback(self)
            if hasattr(result, "ok") and not result.ok:
                self.pending = before
            return result
        except Exception:
            self.pending = before
            raise

    def flush(self):
        if len(self.pending) > 400:
            raise ValueError("transaction_write_limit")
        for (collection, record_id), (kind, data) in self.pending.items():
            reference = self.store.db.collection(collection).document(record_id)
            getattr(self.transaction, kind)(reference, encode(data))
