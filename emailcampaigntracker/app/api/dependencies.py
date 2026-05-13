"""FastAPI Dependency Injection

Phase 2: Centralized dependency injection for all endpoints.
Provides: database sessions, auth context, configuration, services.

All dependencies are injected via Depends() in route handlers,
making services testable and configuration centralized.
"""

from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_user
from app.core.settings import get_settings
from database.db import SessionLocal


# ============================================================================
# Database Session
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency: Database session (SQLAlchemy ORM).

    Yields a new session for each request, automatically committed on success
    or rolled back on exception.

    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# Authentication & Authorization
# ============================================================================

def get_authenticated_user(request: Request) -> AuthUser:
    """
    Dependency: Current authenticated user.

    Verifies JWT token or API key in request headers.
    Raises HTTP 401 if not authenticated.

    Usage:
        @router.get("/profile")
        def get_profile(user: AuthUser = Depends(get_authenticated_user)):
            return {"username": user.username}
    """
    return get_current_user(request)


def require_role(*allowed_roles: str):
    """
    Dependency factory: Require specific user roles.

    Returns a dependency that verifies the user has one of the allowed roles.
    Raises HTTP 403 if user lacks required role.

    Usage:
        admin_only = require_role("admin")

        @router.delete("/users/{user_id}")
        def delete_user(
            user_id: int,
            user: AuthUser = Depends(admin_only)
        ):
            ...
    """
    async def check_role(user: AuthUser = Depends(get_authenticated_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return check_role


# ============================================================================
# Configuration
# ============================================================================

def get_config():
    """
    Dependency: Application configuration.

    Returns settings from environment variables (cached via lru_cache).

    Usage:
        @router.get("/config/debug")
        def get_debug_status(config = Depends(get_config)):
            return {"debug": config.app_env == "development"}
    """
    return get_settings()


# ============================================================================
# Services (to be refactored in Phase 2)
# ============================================================================
# Placeholder for application service dependencies
# These will be implemented as the services are refactored to use DI

# Example (Phase 2):
# from app.application.services.lead_service import LeadService
#
# def get_lead_service(db: Session = Depends(get_db)) -> LeadService:
#     """Dependency: Lead business logic service"""
#     return LeadService(db)
#
# Usage:
#     @router.get("/leads")
#     def list_leads(service: LeadService = Depends(get_lead_service)):
#         return service.list_all()
