from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.integrations.google_sheets import get_last_entries, sync_leads_status
from app.repositories.dashboard_repository import (
    count_events,
    get_all_leads,
    get_latest_sequence_for_lead,
    has_event,
)
from database.db import SessionLocal
from database.models import Event, Lead

logger = logging.getLogger("dashboard")


def drip_dashboard() -> List[Dict[str, Any]]:
    """
    Preserve existing response format and error behavior from Phase 0:
    returns [] on exception.
    """
    try:
        leads = get_all_leads()
        result: List[Dict[str, Any]] = []

        for lead in leads:
            latest_seq = get_latest_sequence_for_lead(lead.id)

            sent_count = count_events(lead.id, "sent")
            click_count = count_events(lead.id, "click")
            open_count = count_events(lead.id, "open")
            deleted = has_event(lead.id, "delete")

            result.append(
                {
                    "lead_id": lead.id,
                    "name": lead.name,
                    "email": lead.email,
                    "company": lead.company,
                    "role": lead.role,
                    "status": lead.status,
                    "sequence": {
                        "step": latest_seq.step_number if latest_seq else None,
                        "status": latest_seq.status if latest_seq else "not_started",
                        "sent_at": latest_seq.sent_at if latest_seq else None,
                        "opened_at": latest_seq.last_opened if latest_seq else None,
                        "replied": latest_seq.replied if latest_seq else False,
                        "tracking_id": latest_seq.tracking_id if latest_seq else None,
                        "clicked": (latest_seq.click_count or 0) > 0 if latest_seq else False,
                        "click_count": latest_seq.click_count if latest_seq else 0,
                        "open_count": latest_seq.open_count if latest_seq else 0,
                        "sent_count": sent_count,
                        "last_replied": latest_seq.last_replied if latest_seq else None,
                    }
                    if latest_seq
                    else None,
                }
            )

        return result
    except Exception:
        logger.exception("Error in drip dashboard.")
        return []


def sheets_status() -> dict:
    entries = get_last_entries(10)
    logger.info("sheets_status_fetched count=%s", len(entries))
    return {"entries": entries, "count": len(entries)}


def sync_status_to_sheets() -> dict:
    """
    Preserves the existing implementation approach and response shape.
    """
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        leads_data = []

        for lead in leads:
            open_count = (
                db.query(Event)
                .filter(Event.lead_id == lead.id, Event.event_type == "open")
                .count()
            )

            leads_data.append(
                {
                    "linkedin_url": lead.linkedin_url,
                    "status": lead.status,
                    "open_count": open_count,
                }
            )

        logger.info("syncing_leads_to_sheet count=%s", len(leads_data))
        success = sync_leads_status(leads_data)

        return {"success": success, "total_synced": len(leads_data)}
    finally:
        db.close()

