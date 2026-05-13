"""Lead Repository

Phase 2: Data access layer for Lead entities.

Provides database queries for Lead operations, encapsulating
all SQL logic behind a clean interface.
"""

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from database.models import Lead
from .base_repository import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    """
    Lead data access layer.

    Provides database operations for Lead entities including:
    - Standard CRUD (create, read, update, delete)
    - Domain-specific queries (by email, by LinkedIn URL, by status)
    - Optimized queries with eager loading
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        super().__init__(db, Lead)

    def get_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email address"""
        return self.db.query(Lead).filter(Lead.email == email).first()

    def get_by_linkedin_url(self, linkedin_url: str) -> Optional[Lead]:
        """Get lead by LinkedIn profile URL"""
        return self.db.query(Lead).filter(
            Lead.linkedin_url == linkedin_url
        ).first()

    def list_by_status(self, status: str) -> List[Lead]:
        """List all leads with specific status (active, inactive, etc.)"""
        return self.db.query(Lead).filter(Lead.status == status).all()

    def list_with_sequences(self, skip: int = 0, limit: int = 100) -> List[Lead]:
        """
        List leads with their email sequences eagerly loaded.

        Prevents N+1 query problem by using joinedload.
        """
        return self.db.query(Lead).options(
            joinedload(Lead.sequences)
        ).offset(skip).limit(limit).all()

    def search_by_name(self, name_fragment: str) -> List[Lead]:
        """Search leads by name (partial match)"""
        return self.db.query(Lead).filter(
            Lead.name.ilike(f"%{name_fragment}%")
        ).all()

    def list_active(self, skip: int = 0, limit: int = 100) -> List[Lead]:
        """List all active leads"""
        return self.db.query(Lead).filter(
            Lead.status == "active"
        ).offset(skip).limit(limit).all()

    def count_by_status(self, status: str) -> int:
        """Count leads with specific status"""
        return self.db.query(Lead).filter(Lead.status == status).count()

    def list_recent(self, days: int = 7, limit: int = 100) -> List[Lead]:
        """List recently created leads"""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.db.query(Lead).filter(
            Lead.created_at >= cutoff
        ).order_by(Lead.created_at.desc()).limit(limit).all()
