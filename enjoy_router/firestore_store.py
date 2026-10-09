"""The Firestore Store: what core.py needs, backed by Cloud Firestore (or its emulator).

Collection names come from schemas/registry.json, not from this file. One extra internal
collection, idempotency_keys, holds one tiny marker per submission key. The request and its
marker are written in one atomic batch, and the marker is created with create(), so two copies
of one submission arriving together cannot both be stored.
"""
from __future__ import annotations

from typing import Optional

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1 import Query
from google.cloud.firestore_v1.base_query import FieldFilter

from core import DuplicateIdempotencyKey, Schemas

KEYS_COLLECTION = "idempotency_keys"


class FirestoreStore:
    def __init__(self, client, schemas: Schemas):
        self.db = client
        self.requests = client.collection(schemas.collection)
        self.classes = client.collection(schemas.class_collection)
        self.keys = client.collection(KEYS_COLLECTION)

    def get_class(self, class_id: str) -> Optional[dict]:
        snap = self.classes.document(class_id).get()
        return snap.to_dict() if snap.exists else None

    def find_by_idempotency_key(self, key: str) -> Optional[dict]:
        marker = self.keys.document(key).get()
        if not marker.exists:
            return None
        snap = self.requests.document(marker.to_dict()["registration_request_id"]).get()
        return snap.to_dict() if snap.exists else None

    def find_latest_by_email_and_type(self, email: str, registration_type: str) -> Optional[dict]:
        # Two equality filters need no composite index. The latest is picked here.
        q = (self.requests.where(filter=FieldFilter("email", "==", email))
             .where(filter=FieldFilter("registration_type", "==", registration_type)))
        docs = [d.to_dict() for d in q.stream()]
        docs = [d for d in docs if not d.get("deleted_at")]
        return max(docs, key=lambda d: d["created_at"]) if docs else None

    def confirmation_number_exists(self, number: str) -> bool:
        return any(True for _ in self.requests.where(filter=FieldFilter("confirmation_number", "==", number)).limit(1).stream())

    def put_request(self, doc: dict) -> None:
        batch = self.db.batch()
        batch.create(self.keys.document(doc["idempotency_key"]),
                     {"registration_request_id": doc["id"], "created_at": doc["created_at"]})
        batch.create(self.requests.document(doc["id"]), doc)
        try:
            batch.commit()
        except AlreadyExists:
            raise DuplicateIdempotencyKey()

    def list_requests(self, limit: int, since: Optional[str] = None) -> list:
        """Newest first by created_at. since keeps created_at >= since (one field, so no composite index)."""
        q = self.requests
        if since is not None:
            q = q.where(filter=FieldFilter("created_at", ">=", since))
        q = q.order_by("created_at", direction=Query.DESCENDING).limit(limit)
        return [d.to_dict() for d in q.stream()]
