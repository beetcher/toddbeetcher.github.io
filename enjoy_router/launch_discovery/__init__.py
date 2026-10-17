"""LAUNCH's side of Discovery: everything that knows about this product (finders, ZIP table, settings stores, the venue sink,
provider adapters). The product-blind engine lives in `discovery/` and never imports from here."""
from __future__ import annotations

# The finders the product has registered. A discovery_type or discovery_prompt may only name one of these.
FINDER_KEYS = ("venue",)
# The {placeholders} every finder's prompt may use (the core supplies these four).
PROMPT_PLACEHOLDERS = ("territory", "types", "fields", "max_results")
