from __future__ import annotations

from typing import List, Optional

from database.db import SessionLocal
from database.models import EmailSequence, Event, Lead


def get_all_leads() -> List[Lead]:
    db = SessionLocal()
    try:
        return db.query(Lead).all()
    finally:
        db.close()


def get_latest_sequence_for_lead(lead_id: int) -> Optional[EmailSequence]:
    db = SessionLocal()
    try:
        return (
            db.query(EmailSequence)
            .filter(EmailSequence.lead_id == lead_id)
            .order_by(EmailSequence.id.desc())
            .first()
        )
    finally:
        db.close()


def count_events(lead_id: int, event_type: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .filter(Event.lead_id == lead_id, Event.event_type == event_type)
            .count()
        )
    finally:
        db.close()


def has_event(lead_id: int, event_type: str) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .filter(Event.lead_id == lead_id, Event.event_type == event_type)
            .first()
            is not None
        )
    finally:
        db.close()

