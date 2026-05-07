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
from app.schemas.jobs import (
    ScraperJobCancelResponse,
    ScraperJobStatusResponse,
)
from app.services.scraper_service import (
    get_in_memory_status,
    get_scraper_status_from_file,
    trigger_scrape,
    update_status,
)
from app.services.scraper_job_service import (
    cancel_scraper_job,
    get_scraper_job,
    get_scraper_queue_stats,
    list_scraper_jobs,
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


@router.get("/api/scraper/jobs/{job_id}", response_model=ScraperJobStatusResponse)
def get_job(job_id: int, _auth: None = Depends(scraper_auth)):
    job = get_scraper_job(job_id)
    if not job:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "status": job.status,
        "source": job.source,
        "webhook_url": job.webhook_url,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "cancelled": job.cancelled,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "last_error": job.last_error,
        "rq_job_id": job.rq_job_id,
    }


@router.post(
    "/api/scraper/jobs/{job_id}/cancel",
    response_model=ScraperJobCancelResponse,
)
def cancel_job(job_id: int, _auth: None = Depends(scraper_auth)):
    result = cancel_scraper_job(job_id)
    if not result.get("ok"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job not found")
    return ScraperJobCancelResponse(ok=result["ok"], status=result["status"], job_id=job_id)


@router.get("/api/scraper/jobs")
def list_jobs(limit: int = 20, _auth: None = Depends(scraper_auth)):
    jobs = list_scraper_jobs(limit=limit)
    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "source": j.source,
                "webhook_url": j.webhook_url,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "cancelled": j.cancelled,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "last_error": j.last_error,
            }
            for j in jobs
        ]
    }


@router.get("/api/scraper/queue/status")
def queue_status(_auth: None = Depends(scraper_auth)):
    return get_scraper_queue_stats()

