"""Email Sequence Repository

Phase 2: Data access layer for EmailSequence entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import EmailSequence
from .base_repository import BaseRepository


class EmailSequenceRepository(BaseRepository[EmailSequence]):
    """Email sequence data access layer"""

    def __init__(self, db: Session):
        super().__init__(db, EmailSequence)

    def get_by_tracking_id(self, tracking_id: str) -> Optional[EmailSequence]:
        """Get sequence by tracking ID"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.tracking_id == tracking_id
        ).first()

    def list_by_lead(self, lead_id: int) -> List[EmailSequence]:
        """Get all sequences for a specific lead"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.lead_id == lead_id
        ).order_by(EmailSequence.step_number).all()

    def get_latest_by_lead(self, lead_id: int) -> Optional[EmailSequence]:
        """Get the most recent sequence for a lead"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.lead_id == lead_id
        ).order_by(EmailSequence.id.desc()).first()

    def list_by_status(self, status: str) -> List[EmailSequence]:
        """Get all sequences with specific status"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.status == status
        ).all()

    def list_opened(self) -> List[EmailSequence]:
        """Get all opened emails"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.open_count > 0
        ).all()

    def list_replied(self) -> List[EmailSequence]:
        """Get all sequences with replies"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.replied == True
        ).all()

    def count_sent(self) -> int:
        """Count total sent emails"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.sent_at.isnot(None)
        ).count()

    def count_opened(self) -> int:
        """Count opened emails"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.open_count > 0
        ).count()

    def count_replied(self) -> int:
        """Count emails with replies"""
        return self.db.query(EmailSequence).filter(
            EmailSequence.replied == True
        ).count()
