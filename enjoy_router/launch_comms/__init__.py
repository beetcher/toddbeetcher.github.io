"""LAUNCH's side of the CMS: everything that knows about individuals, classes, venues and the Firestore collections.

The core (`comms/`) knows none of it (R-1). This package supplies the ports (directory, template store, log store, settings), the
message kinds and the fact builders that turn a LAUNCH record into the facts a kind declares. Written October 15, 2026 (thread 14).
"""
