from fastapi import APIRouter

from app.services.leads_service import list_lead_events, list_leads, feed_entries
from app.services.profiles_service import load_last_posts

router = APIRouter(tags=["Leads"])


@router.get("/api/leads")
def get_leads():
    return list_leads()


@router.get("/api/leads/{lead_id}/events")
def get_lead_events(lead_id: int):
    return list_lead_events(lead_id)


@router.get("/api/activity")
def get_activity():
    return load_last_posts()


@router.get("/api/feed")
def get_feed():
    return feed_entries(50)

