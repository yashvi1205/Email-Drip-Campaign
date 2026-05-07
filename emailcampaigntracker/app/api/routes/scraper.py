from fastapi import APIRouter, Body, Depends

from app.core.auth import require_roles
from app.core.rate_limit import rate_limit
from app.core.settings import get_settings
from app.schemas.scraper import (
    ScrapeStartRequest,
    ScrapeStartResponse,
    ScraperStatusUpdateRequest,
    ScraperStatusUpdateResponse,
)
from app.services.scraper_service import (
    get_in_memory_status,
    get_scraper_status_from_file,
    trigger_scrape,
    update_status,
)

settings = get_settings()
scraper_auth = require_roles("scraper", "admin")
scraper_rate_limit = rate_limit("scraper", settings.scraper_rate_limit_per_minute)

router = APIRouter(tags=["Scraper"])


@router.get("/api/scraper-status")
def get_scraper_status(_auth: None = Depends(scraper_auth)):
    return get_scraper_status_from_file()


@router.post("/api/scrape")
def start_scrape(
    payload: ScrapeStartRequest = Depends(),
    _auth: None = Depends(scraper_auth),
    _rl: None = Depends(scraper_rate_limit),
) -> ScrapeStartResponse:
    result = trigger_scrape(webhook_url=payload.webhook_url, source=payload.source)
    return ScrapeStartResponse(**result)


@router.post("/api/update-status")
def post_update_status(
    data: ScraperStatusUpdateRequest = Body(...),
    _auth: None = Depends(scraper_auth),
    _rl: None = Depends(scraper_rate_limit),
) -> ScraperStatusUpdateResponse:
    return ScraperStatusUpdateResponse(**update_status(data.model_dump(exclude_none=True)))


@router.get("/api/scrape/status")
def get_status(_auth: None = Depends(scraper_auth)):
    return get_in_memory_status()

