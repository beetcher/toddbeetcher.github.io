"""A small in-memory rate limiter for the public form.

Each running copy of the function keeps its own counts, so with several copies running the
real limit is a little looser than stated. That is accepted for now; App Check and a shared
counter come later. Visitors are keyed by a salted hash of their address, never the address.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict, deque
from typing import Optional

# (window in seconds, maximum requests in that window). Todd, 2026-10-06: 5 per 10 minutes, 30 per day.
DEFAULT_RULES = ((600, 5), (86400, 30))
MAX_KEYS = 10000


def parse_rules(text: str) -> tuple:
    """"600:5,86400:30" -> ((600, 5), (86400, 30)). Raises ValueError on anything else."""
    rules = tuple((int(w), int(m)) for w, m in (p.split(":") for p in text.split(",")))
    if not rules or any(w <= 0 or m <= 0 for w, m in rules):
        raise ValueError("rate rules must be positive window:max pairs")
    return rules


def visitor_key(address: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{address}".encode()).hexdigest()[:16]


class RateLimiter:
    def __init__(self, rules=DEFAULT_RULES, max_keys: int = MAX_KEYS):
        self.rules = tuple(rules)
        self.max_keys = max_keys
        self._hits: "OrderedDict[str, deque]" = OrderedDict()

    def allow(self, key: str, now: float) -> bool:
        """Record one request for key and say whether it is within every rule."""
        longest = max(w for w, _ in self.rules)
        hits = self._hits.get(key)
        if hits is None:
            hits = self._hits[key] = deque()
            while len(self._hits) > self.max_keys:
                self._hits.popitem(last=False)
        else:
            self._hits.move_to_end(key)
        while hits and hits[0] <= now - longest:
            hits.popleft()
        for window, limit in self.rules:
            if sum(1 for t in hits if t > now - window) >= limit:
                return False
        hits.append(now)
        return True

    def retry_after(self, key: str, now: float) -> Optional[int]:
        """Seconds until the oldest counted request leaves the shortest full window (a hint for the visitor)."""
        hits = self._hits.get(key, ())
        waits = []
        for window, limit in self.rules:
            inside = [t for t in hits if t > now - window]
            if len(inside) >= limit:
                waits.append(int(inside[0] + window - now) + 1)
        return max(waits) if waits else None
