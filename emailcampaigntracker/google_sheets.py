"""
Compatibility shim (Phase 1).

The implementation moved to `app.integrations.google_sheets`.
This module re-exports the public surface so existing imports keep working.
"""

from app.integrations.google_sheets import *  # noqa: F403

