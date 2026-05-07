from __future__ import annotations

from typing import Any, Dict, List

from app.integrations.google_sheets import get_last_entries
from app.repositories.leads_repository import get_all_leads, get_lead_events


def list_leads() -> List[Dict[str, Any]]:
    leads = get_all_leads()
    result = []
    for lead in leads:
        result.append(
            {
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "linkedin_url": lead.linkedin_url,
                "company": lead.company,
                "role": lead.role,
                "headline": lead.headline,
                "about": lead.about,
                "work_description": lead.work_description,
                "status": lead.status,
                "created_at": lead.created_at,
            }
        )
    return result


def list_lead_events(lead_id: int) -> List[Dict[str, Any]]:
    events = get_lead_events(lead_id)
    result = []
    for event in events:
        result.append(
            {
                "id": event.id,
                "type": event.event_type,
                "timestamp": event.timestamp,
                "metadata": event.additional_data,
            }
        )
    return result


def feed_entries(count: int = 50) -> dict:
    entries = get_last_entries(count)
    return {"entries": entries}

