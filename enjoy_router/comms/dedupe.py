"""Duplicate protection (CMS_GUIDE.md section 3 step 3; rule R-9). Explicit and deterministic: no time windows. Product-blind."""
from __future__ import annotations


def default_key(kind: str, recipient: dict, refs: dict) -> str:
    """kind + recipient + sorted refs. A caller whose event can legitimately repeat (a class changed twice) passes its own
    dedupe_key that includes an event version."""
    who = recipient.get("individual_id") or recipient.get("email") or recipient.get("phone") or ""
    ref_part = ",".join(f"{k}={refs[k]}" for k in sorted(refs) if refs.get(k))
    return f"{kind}:{who}:{ref_part}"[:300]
