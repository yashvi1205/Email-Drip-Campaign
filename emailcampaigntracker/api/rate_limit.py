"""
Compatibility shim (Phase 1).

Rate limiting moved to `app.core.rate_limit`.
"""

from app.core.rate_limit import rate_limit  # noqa: F401

