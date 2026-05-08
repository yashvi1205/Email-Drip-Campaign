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


from sqlalchemy.orm import joinedload

def drip_dashboard() -> List[Dict[str, Any]]:
    """
    Optimized dashboard query using joinedload to prevent N+1 issues.
    """
    db = SessionLocal()
    try:
        # Fetch all leads with their sequences in one/two queries
        leads = db.query(Lead).options(joinedload(Lead.sequences)).all()
        result: List[Dict[str, Any]] = []

        for lead in leads:
            # Get the latest sequence from the prefetched list
            sorted_seqs = sorted(lead.sequences, key=lambda s: s.id, reverse=True)
            latest_seq = sorted_seqs[0] if sorted_seqs else None

            # Note: We use the denormalized counts on EmailSequence for speed.
            # These are kept in sync by the tracking log_event logic.
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
                        "sent_count": 1 if latest_seq and latest_seq.sent_at else 0,
                        "last_replied": latest_seq.last_replied if latest_seq else None,
                    }
                    if latest_seq
                    else None,
                }
            )

        return result
    except Exception:
        logger.exception("Error in optimized drip dashboard.")
        return []
    finally:
        db.close()


def sheets_status() -> dict:
    entries = get_last_entries(10)
    logger.info("sheets_status_fetched count=%s", len(entries))
    return {"entries": entries, "count": len(entries)}


def sync_status_to_sheets() -> dict:
    """
    Optimized sheet sync using prefetched data.
    """
    db = SessionLocal()
    try:
        leads = db.query(Lead).options(joinedload(Lead.sequences)).all()
        leads_data = []

        for lead in leads:
            # Find open count from the latest sequence
            sorted_seqs = sorted(lead.sequences, key=lambda s: s.id, reverse=True)
            latest_seq = sorted_seqs[0] if sorted_seqs else None
            open_count = latest_seq.open_count if latest_seq else 0

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

