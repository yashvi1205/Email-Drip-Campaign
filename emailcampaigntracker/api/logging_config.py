"""
Compatibility shim (Phase 1).

Logging config moved to `app.core.logging`.
"""

from app.core.logging import configure_logging  # noqa: F401

