"""An in-memory Store for the test runner. Same interface the Firestore store will have."""
from __future__ import annotations

from typing import Optional

from core import DuplicateIdempotencyKey


class MemoryStore:
    def __init__(self, classes: list):
        self.classes = {c["id"]: c for c in classes}
        self.requests: list = []  # stored documents, oldest first

    def get_class(self, class_id: str) -> Optional[dict]:
        return self.classes.get(class_id)

    def find_by_idempotency_key(self, key: str) -> Optional[dict]:
        return next((d for d in self.requests if d.get("idempotency_key") == key), None)

    def find_latest_by_email_and_type(self, email: str, registration_type: str) -> Optional[dict]:
        matches = [d for d in self.requests
                   if d["email"] == email and d["registration_type"] == registration_type and not d.get("deleted_at")]
        return matches[-1] if matches else None

    def confirmation_number_exists(self, number: str) -> bool:
        return any(d.get("confirmation_number") == number for d in self.requests)

    def put_request(self, doc: dict) -> None:
        if self.find_by_idempotency_key(doc["idempotency_key"]) is not None:
            raise DuplicateIdempotencyKey()
        self.requests.append(dict(doc))

    def list_requests(self, limit: int, since: Optional[str] = None) -> list:
        """Newest first by created_at (ties broken by id). since keeps created_at >= since."""
        docs = [d for d in self.requests if since is None or d["created_at"] >= since]
        docs.sort(key=lambda d: (d["created_at"], d["id"]), reverse=True)
        return [dict(d) for d in docs[:limit]]
