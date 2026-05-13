"""Event Repository

Phase 2: Data access layer for Event entities (tracking events).
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from database.models import Event
from .base_repository import BaseRepository


class EventRepository(BaseRepository[Event]):
    """Event (tracking) data access layer"""

    def __init__(self, db: Session):
        super().__init__(db, Event)

    def list_by_lead(self, lead_id: int) -> List[Event]:
        """Get all events for a specific lead"""
        return self.db.query(Event).filter(
            Event.lead_id == lead_id
        ).order_by(Event.timestamp.desc()).all()

    def list_by_type(self, event_type: str) -> List[Event]:
        """Get all events of a specific type (open, click, reply, etc.)"""
        return self.db.query(Event).filter(
            Event.event_type == event_type
        ).all()

    def list_by_lead_and_type(self, lead_id: int, event_type: str) -> List[Event]:
        """Get specific event type for a lead"""
        return self.db.query(Event).filter(
            Event.lead_id == lead_id,
            Event.event_type == event_type
        ).order_by(Event.timestamp.desc()).all()

    def count_by_lead(self, lead_id: int) -> int:
        """Count all events for a lead"""
        return self.db.query(Event).filter(Event.lead_id == lead_id).count()

    def count_by_type(self, event_type: str) -> int:
        """Count all events of a specific type"""
        return self.db.query(Event).filter(Event.event_type == event_type).count()

    def list_recent(self, hours: int = 24) -> List[Event]:
        """Get events from the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(Event).filter(
            Event.timestamp >= cutoff
        ).order_by(Event.timestamp.desc()).all()

    def count_recent(self, hours: int = 24) -> int:
        """Count events from the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(Event).filter(Event.timestamp >= cutoff).count()

    def delete_old_events(self, days: int = 90) -> int:
        """Delete events older than N days. Returns count deleted."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = self.db.query(Event).filter(Event.timestamp < cutoff).delete()
        self.db.flush()
        return count
