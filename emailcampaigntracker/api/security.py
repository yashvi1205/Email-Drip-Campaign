"""
Compatibility shim (Phase 1).

Security helpers moved to `app.core.security`.
"""

from app.core.security import require_api_key  # noqa: F401

