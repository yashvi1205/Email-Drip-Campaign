"""Phase 1: Configuration management layer

This module will eventually contain:
- settings.py (application configuration from env vars)
- constants.py (application-wide constants)

Currently, these are in app/core/ for backwards compatibility.
They will be migrated here in Phase 2.
"""

from app.core.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
