"""Sign-in and per-person access (P-62; see schemas/ACCESS_GUIDE.md).

    from access import authenticate, Access, CAPABILITIES

`authenticate` is the ONE check every door asks: it turns the Bearer value into an Access (who, and what they may do), or a refusal code.
"""
from .authorize import Access, FirebaseVerifier, authenticate, KEY_ACTOR  # noqa: F401
from .capabilities import CAPABILITIES  # noqa: F401
