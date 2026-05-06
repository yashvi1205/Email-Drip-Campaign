"""
Compatibility shim (Phase 1).

Middleware moved to `app.middleware.request_context`.
"""

from app.middleware.request_context import (  # noqa: F401
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    get_request_id,
)

