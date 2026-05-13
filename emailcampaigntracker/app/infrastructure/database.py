"""Database connection management with optimization

Provides connection pooling, session management, and query optimization.
"""

import logging
from typing import Generator, Optional

from sqlalchemy import create_engine, pool, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import text

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def get_engine():
    """Create SQLAlchemy engine with optimized connection pooling"""
    settings = get_settings()

    # Determine pool class based on database
    if "sqlite" in settings.database_url:
        poolclass = pool.StaticPool
        connect_args = {"check_same_thread": False}
    else:
        poolclass = pool.QueuePool
        connect_args = {"connect_timeout": 10}

    engine = create_engine(
        settings.database_url,
        poolclass=poolclass,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.app_env == "development",
        connect_args=connect_args,
    )

    # Add query logging in development
    if settings.app_env == "development":

        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            logger.debug("Executing: %s", statement[:100])

    return engine


def get_session_factory():
    """Get SQLAlchemy session factory"""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Database session dependency for FastAPI

    Yields:
        SQLAlchemy Session
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def optimize_session(db: Session) -> None:
    """Apply optimizations to a session"""
    # Expire on commit can cause N+1 queries, disable if doing bulk operations
    db.expire_on_commit = False


def get_session_stats(db: Session) -> dict:
    """Get session statistics for monitoring"""
    try:
        result = db.execute(text("SELECT COUNT(*) as active_connections FROM information_schema.processlist WHERE user = DATABASE();"))
        connection_count = result.scalar() or 0
    except Exception:
        connection_count = 0

    return {
        "is_active": db.is_active,
        "connection_count": connection_count,
        "pending_rollback": db.transaction is not None and not db.transaction.is_active,
    }


# Eager loading patterns for common queries
COMMON_JOINS = {
    "Lead": ["sequences", "events"],
    "EmailSequence": ["lead", "events"],
    "Event": ["lead", "email_sequence"],
}


def apply_eager_loading(query, model_name: str):
    """Apply eager loading relationships to a query

    Args:
        query: SQLAlchemy query object
        model_name: Name of the model being queried

    Returns:
        Query with eager loading applied
    """
    if model_name in COMMON_JOINS:
        for relationship in COMMON_JOINS[model_name]:
            try:
                from sqlalchemy.orm import joinedload
                query = query.options(joinedload(getattr(model_name, relationship)))
            except Exception:
                pass

    return query
