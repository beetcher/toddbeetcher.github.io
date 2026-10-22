"""The shared sign-in check (P-62 step 2). No Firebase in this file: the Google side is a `verifier` the caller passes in.

    access = authenticate(given, admin_key=..., verifier=..., store=..., now=...)

`given` is the Bearer value (already taken out of the Authorization header). Three ways in:

  * the admin key (the back door): acts as a super admin with the actor `user:admin`, exactly as the doors have always stamped it.
    Compared in constant time. Only when the key setting is present and at least MIN_KEY_LENGTH characters long.
  * the temporary review code (REVIEW_CODE_GUIDE.md): a super admin sets one code that works for 24 hours; it signs in as the view-only
    Global Inspector (method `code`, actor `review-code`). Only a hash is stored. Anything that is not a token and not the admin key is tried
    against it; wrong or expired codes are refused as `unauthorized` like any bad credential.
  * a Google sign-in token: the verifier says who Google says it is (uid, email, email_verified, provider, name). The email must be
    verified and the provider must be google.com. The email must match a live, switched-on `access_person` whose role is live and
    switched on; otherwise `not_invited`. The first sign-in saves Google's account id on the person; a later sign-in from a different
    Google account is refused (`account_changed`). The actor is `user:<access_person id>`.

Refusal codes (Access.ok is False): not_configured (no key setting and no verifier: fails closed), unauthorized (no credential, wrong
key, a token that does not verify, unverified email or a non-Google provider), not_invited, account_changed. The messages that say why
never name which part failed beyond these codes; nothing here logs a key, a token or an email.

A super admin role holds every capability, listed or not (`can` is True for any name). Others hold the global capabilities their role lists plus the
territorial capabilities of their grants (P-60: `access.territory` decides where a grant reaches).
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from crud import access_persons_crud as PE
from . import review_code
from .capabilities import CAPABILITIES, GLOBAL, TERRITORIAL

INSPECT = "inspect_everything"
MIN_KEY_LENGTH = 32            # same number as console.MIN_KEY_LENGTH (a test keeps them equal; console cannot be imported here)
KEY_ACTOR = "user:admin"
PROVIDER = "google.com"
SIGN_IN_WRITE_SECONDS = 600     # last_sign_in_at is written at most this often per person


@dataclass(frozen=True)
class Access:
    ok: bool
    code: str = ""                 # why not, when ok is False
    actor: str = ""                # what the door stamps as created_by / updated_by
    name: str = ""                 # what the Console shows
    email: str = ""
    role_key: str = ""
    capabilities: frozenset = frozenset()
    is_super_admin: bool = False
    scope_region_id: str = ""      # RETIRED (see grants); still carried so older records work
    grants: tuple = ()             # the territory: dicts with kind, state_code, region_ids (frozenset), capabilities (frozenset), group
    method: str = ""               # "key" or "google"
    individual_id: str = ""        # the person record this sign-in is linked to (an instructor sees the classes they teach)

    def can(self, capability: str) -> bool:
        return self.ok and (self.is_super_admin or capability in self.capabilities)

    @property
    def inspector(self) -> bool:
        """A person whose role holds `inspect_everything` is VIEW ONLY at every door (P-78): they may look at everything, change nothing.
        A super admin is never an inspector (the capability is listed on every super admin role only because a super admin holds them all)."""
        return self.ok and not self.is_super_admin and INSPECT in self.capabilities


ALL_GRANT = {"kind": "all", "capabilities": frozenset(TERRITORIAL)}


def _grants_of(store, person, role):
    """The person's grants in the form the code reads. State and all grants carry every territorial capability. An older person with
    only the retired `scope_region_id` counts as one grant for that region with the territorial capabilities their role lists."""
    out = []
    for g in person.get("grants") or []:
        if g.get("kind") == "all":
            out.append({"kind": "all", "capabilities": frozenset(TERRITORIAL), "group": g.get("group", "")})
        elif g.get("kind") == "state":
            out.append({"kind": "state", "state_code": g.get("state_code"), "capabilities": frozenset(TERRITORIAL), "group": g.get("group", "")})
        elif g.get("kind") == "regions":
            out.append({"kind": "regions", "state_code": g.get("state_code"), "region_ids": frozenset(g.get("region_ids", ())),
                        "capabilities": frozenset(g.get("capabilities", ())) & frozenset(TERRITORIAL), "group": g.get("group", "")})
    if not out and person.get("scope_region_id"):
        area = store.get("discovery_areas", person["scope_region_id"])
        if area and "deleted_at" not in area and area.get("kind") == "region":
            out.append({"kind": "regions", "state_code": area.get("state_code"), "region_ids": frozenset([area["id"]]),
                        "capabilities": frozenset(role.get("capabilities", ())) & frozenset(TERRITORIAL), "group": ""})
    return tuple(out)


def _refuse(code):
    return Access(False, code)


def looks_like_token(given: str) -> bool:
    """A Google ID token is a JWT: three dot-separated parts. Anything else is never sent to the verifier."""
    return isinstance(given, str) and given.count(".") == 2 and len(given) > 40


def _stale(person, now) -> bool:
    last = person.get("last_sign_in_at")
    if not last:
        return True
    try:
        then = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return (now - then).total_seconds() >= SIGN_IN_WRITE_SECONDS


def authenticate(given, *, admin_key, verifier, store, now) -> Access:
    key_on = isinstance(admin_key, str) and len(admin_key) >= MIN_KEY_LENGTH
    if not key_on and verifier is None:
        return _refuse("not_configured")
    if not given:
        return _refuse("unauthorized")
    if key_on and hmac.compare_digest(given.encode("utf-8"), admin_key.encode("utf-8")):
        return Access(True, actor=KEY_ACTOR, name="Admin key", role_key="super_admin", capabilities=frozenset(CAPABILITIES),
                      is_super_admin=True, grants=(ALL_GRANT,), method="key")
    if not looks_like_token(given):    # not a Google token: it may be the temporary review code (view only, 24 hours)
        coded = review_code.access_for(given, store, now)
        return coded if coded is not None else _refuse("unauthorized")
    if verifier is None:
        return _refuse("unauthorized")
    try:
        claims = verifier.verify(given)
    except Exception:   # an expired, forged or malformed token: say nothing about which
        return _refuse("unauthorized")
    email = claims.get("email") if isinstance(claims, dict) else None
    uid = claims.get("uid") if isinstance(claims, dict) else None
    if not (isinstance(email, str) and email and isinstance(uid, str) and uid
            and claims.get("email_verified") is True and claims.get("provider") == PROVIDER):
        return _refuse("unauthorized")
    person = PE.find_live_by_email(store, email)
    if person is None or not person.get("is_active"):
        return _refuse("not_invited")
    role = PE.role_of(store, person)
    if role is None or not role.get("is_active"):
        return _refuse("not_invited")
    if person.get("google_uid") and person["google_uid"] != uid:
        return _refuse("account_changed")
    if not person.get("google_uid") or _stale(person, now):
        PE.record_sign_in(store, person, uid, now)
    sup = bool(role.get("is_super_admin"))
    grants = (ALL_GRANT,) if sup else _grants_of(store, person, role)
    # global capabilities come from the role; territorial ones only from the grants (the role's territorial list is just the default for a new grant)
    caps = frozenset(CAPABILITIES) if sup else frozenset(c for c in role.get("capabilities", []) if c in GLOBAL).union(*(g["capabilities"] for g in grants))
    return Access(True, actor=f"user:{person['id']}", name=person.get("display_name") or claims.get("name") or person["email"],
                  email=person["email"], role_key=role["key"], capabilities=caps,
                  is_super_admin=sup, scope_region_id=person.get("scope_region_id", ""), grants=grants, method="google", individual_id=person.get("individual_id", "") or "")


class FirebaseVerifier:
    """The real verifier: Firebase Authentication ID tokens. firebase_admin must already be initialised (main.py does that).
    Returns only what the check needs. Raises on any bad token."""

    def verify(self, token):
        from firebase_admin import auth
        c = auth.verify_id_token(token, check_revoked=False)
        return {"uid": c.get("uid") or c.get("user_id") or c.get("sub"), "email": (c.get("email") or "").strip().lower(),
                "email_verified": c.get("email_verified") is True,
                "provider": (c.get("firebase") or {}).get("sign_in_provider", ""), "name": c.get("name", "")}
