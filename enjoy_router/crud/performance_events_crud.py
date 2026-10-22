"""Handler for `performance_events`: timing measurements of the Console (see PERFORMANCE_EVENT_GUIDE.md). Records are created only by
crud/performance_service.py (the record_timing op); through the Console door they can be read (list, get) and nothing else. Who may read
is decided in access/policy.py (view_performance), not here."""
from __future__ import annotations

from .discovery_kit import make
from .schema_kit import failure

H = make("performance_event", order="created_at")
COLLECTION, get, list = H.COLLECTION, H.get, H.list
save = H.create          # the ONLY way in: crud/performance_service.py (the record_timing op). `create` below is what a door would call, and it refuses.


def create(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


def update(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


def soft_delete(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])
