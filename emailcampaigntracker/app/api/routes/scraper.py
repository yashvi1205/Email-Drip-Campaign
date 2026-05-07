from fastapi import APIRouter, Depends

from app.core.rate_limit import rate_limit
from app.core.security import require_api_key
from app.core.settings import get_settings
from app.services.scraper_service import (
    get_in_memory_status,
    get_scraper_status_from_file,
    trigger_scrape,
    update_status,
)

settings = get_settings()
scraper_auth = require_api_key(settings.scraper_api_key)
scraper_rate_limit = rate_limit("scraper", settings.scraper_rate_limit_per_minute)

router = APIRouter(tags=["Scraper"])


@router.get("/api/scraper-status")
def get_scraper_status(_auth: None = Depends(scraper_auth)):
    return get_scraper_status_from_file()


@router.post("/api/scrape")
def start_scrape(
    webhook_url: str = None,
    source: str = "unknown",
    _auth: None = Depends(scraper_auth),
    _rl: None = Depends(scraper_rate_limit),
):
    return trigger_scrape(webhook_url=webhook_url, source=source)


@router.post("/api/update-status")
def post_update_status(
    data: dict,
    _auth: None = Depends(scraper_auth),
    _rl: None = Depends(scraper_rate_limit),
):
    return update_status(data)


@router.get("/api/scrape/status")
def get_status(_auth: None = Depends(scraper_auth)):
    return get_in_memory_status()

