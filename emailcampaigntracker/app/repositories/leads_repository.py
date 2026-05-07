from __future__ import annotations

from typing import List, Optional

from database.db import SessionLocal
from database.models import Event, Lead


def get_all_leads() -> List[Lead]:
    db = SessionLocal()
    try:
        return db.query(Lead).all()
    finally:
        db.close()


def get_lead_by_linkedin_url(url: str) -> Optional[Lead]:
    db = SessionLocal()
    try:
        return db.query(Lead).filter(Lead.linkedin_url == url).first()
    finally:
        db.close()


def get_lead_events(lead_id: int) -> List[Event]:
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .filter(Event.lead_id == lead_id)
            .order_by(Event.timestamp.desc())
            .all()
        )
    finally:
        db.close()


def get_latest_interaction_summary_event(lead_id: int | None) -> Optional[Event]:
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .filter(Event.lead_id == lead_id, Event.event_type == "interaction_summary")
            .order_by(Event.timestamp.desc())
            .first()
        )
    finally:
        db.close()

