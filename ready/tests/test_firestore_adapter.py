"""Adapter serialization/buffering tests; not a substitute for emulator tests."""
from copy import deepcopy
from datetime import datetime
import unittest

from ready.crud.firestore_store import encode, decode, _View


class Snapshot:
    def __init__(self, id, value):
        self.id, self.value, self.exists = id, value, value is not None
    def to_dict(self):
        return deepcopy(self.value)


class Reference:
    def __init__(self, fake, collection, id):
        self.fake, self.collection, self.id = fake, collection, id
    def get(self, transaction=None):
        self.fake.reads += 1
        return Snapshot(self.id, self.fake.rows.get((self.collection, self.id)))


class Collection:
    def __init__(self, fake, name): self.fake, self.name = fake, name
    def document(self, id): return Reference(self.fake, self.name, id)


class Fake:
    def __init__(self): self.rows, self.writes, self.reads = {}, [], 0
    def collection(self, name): return Collection(self, name)
    def create(self, reference, data): self.writes.append(("create", reference.id, data))
    def update(self, reference, data): self.writes.append(("update", reference.id, data))


class FirestoreAdapterTests(unittest.TestCase):
    def test_native_timestamp_roundtrip_in_nested_maps(self):
        data = {"test_taken_at": "2026-10-28T12:00:00.000000Z", "origin": {"source_reference": "2026-10-28"},
                "lifecycle_events": [{"at": "2026-10-28T12:00:00.000000Z"}]}
        stored = encode(data)
        self.assertIsInstance(stored["test_taken_at"], datetime)
        self.assertEqual(decode(stored), data)

    def test_transaction_buffers_writes_and_allows_read_your_writes(self):
        fake = Fake()
        store = type("Store", (), {"db": fake})()
        view = _View(store, fake)
        view.create("questions", "new", {"id": "new", "question_text": "Original"})
        self.assertEqual(fake.writes, [])
        self.assertEqual(view.get("questions", "new")["question_text"], "Original")
        view.replace_metadata("questions", "new", {"id": "new", "question_text": "Original", "record_version": 2})
        view.get("questions", "another")
        self.assertEqual(fake.writes, [])
        view.flush()
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(fake.writes[0][0], "create")
        self.assertEqual(fake.writes[0][2]["record_version"], 2)


if __name__ == "__main__":
    unittest.main()
