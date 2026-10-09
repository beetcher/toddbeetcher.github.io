"""The three errors a document store may raise. Every store (memory, Firestore) raises these same ones,
so handler files never import a particular store."""


class DocExists(Exception):
    """create: a document with that id already exists."""


class DocMissing(Exception):
    """update: no document with that id."""


class StaleUpdate(Exception):
    """update: expected_updated_at no longer matches the stored record."""
