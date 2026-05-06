"""
Compatibility shim (Phase 1).

The FastAPI app entrypoint moved to `app.main`.
This keeps `uvicorn api.main:app` working.
"""

from app.main import app  # noqa: F401

