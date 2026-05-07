from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from rq import Retry
from app.core.settings import get_settings
from app.queue.redis_queue import get_redis_connection, get_scraper_queue
from database.db import SessionLocal
from database.models import ScraperJob

logger = logging.getLogger("scraper_job_service")


PROJECT_ROOT_CACHE: Optional[str] = None


def _get_project_root() -> str:
    global PROJECT_ROOT_CACHE
    if PROJECT_ROOT_CACHE:
        return PROJECT_ROOT_CACHE
    import os

    PROJECT_ROOT_CACHE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return PROJECT_ROOT_CACHE


def _scraper_status_file() -> str:
    return f"{_get_project_root()}/scraper_status.json"


def _read_scraper_status_file() -> dict:
    import os

    path = _scraper_status_file()
    if not os.path.exists(path):
        return {"status": "idle", "new_posts_found": 0}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read scraper_status.json")
        return {"status": "error", "error": "Failed to read scraper_status.json"}


def _persist_scraper_status_file(payload: dict) -> None:
    import os

    path = _scraper_status_file()
    try:
        with open(path, "w") as f:
            json.dump(payload, f)
    except Exception:
        logger.exception("Failed to persist scraper_status.json")


def enqueue_scraper_job(webhook_url: Optional[str], source: str) -> Tuple[dict, Optional[int]]:
    """
    Creates + enqueues a scraper background job.

    Returns:
      (scrape_response_dict, job_id_if_started)
    """
    settings = get_settings()
    redis_conn = get_redis_connection()
    queue = get_scraper_queue()

    lock_key = "scraper:run_lock"
    lock_value = str(uuid.uuid4())
    acquired = redis_conn.set(
        lock_key, lock_value, nx=True, ex=settings.scraper_run_lock_ttl_seconds
    )

    # Even if lock not acquired, we keep backward-compatible behavior by checking file status.
    status_from_file = _read_scraper_status_file()
    now = datetime.utcnow()

    def _is_running(st: dict) -> bool:
        if st.get("status") != "running":
            return False
        ts = st.get("timestamp") or 0
        try:
            last_update = float(ts)
        except Exception:
            last_update = 0
        return (time.time() - last_update) < settings.scraper_max_running_age_seconds

    if not acquired or _is_running(status_from_file):
        if _is_running(status_from_file):
            return {"status": "already running", "source": source}, None
        # If lock couldn't be acquired but file doesn't say running, fall through and attempt DB check.

    session = SessionLocal()
    job: Optional[ScraperJob] = None
    try:
        running_job = (
            session.query(ScraperJob)
            .filter(ScraperJob.status.in_(["queued", "running", "retrying"]))
            .order_by(ScraperJob.created_at.desc())
            .first()
        )
        if running_job and (now - running_job.created_at).total_seconds() < settings.scraper_max_running_age_seconds:
            return {"status": "already running", "source": source}, None

        job = ScraperJob(
            status="queued",
            source=source,
            webhook_url=webhook_url,
            attempts=0,
            max_attempts=settings.scraper_job_max_attempts,
            cancelled=False,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # Initial scraper_status.json update (keeps existing frontend behavior).
        payload = {
            "status": "running",
            "message": f"Scraper started by {source}",
            "timestamp": datetime.utcnow().timestamp(),
            "new_posts_found": 0,
            "job_id": job.id,
        }
        _persist_scraper_status_file(payload)

        # RQ retry is based on number of retries beyond the initial attempt.
        retry = Retry(
            max=max(0, settings.scraper_job_max_attempts - 1),
            interval=settings.scraper_job_retry_interval_seconds,
        )

        from app.workers.scraper_worker import execute_scraper_job

        rq_job = queue.enqueue(
            execute_scraper_job,
            job.id,
            job_id=f"scraper:{job.id}",
            retry=retry,
            timeout=settings.scraper_job_timeout_seconds + 30,
        )

        job.rq_job_id = rq_job.id
        session.commit()

        scrape_response = {"status": "started", "source": source, "webhook_url": webhook_url}
        return scrape_response, job.id
    finally:
        session.close()


def get_scraper_job(job_id: int) -> Optional[ScraperJob]:
    session = SessionLocal()
    try:
        return session.query(ScraperJob).filter(ScraperJob.id == job_id).first()
    finally:
        session.close()


def list_scraper_jobs(limit: int = 20) -> list[ScraperJob]:
    session = SessionLocal()
    try:
        return (
            session.query(ScraperJob)
            .order_by(ScraperJob.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
    finally:
        session.close()


def cancel_scraper_job(job_id: int) -> dict:
    settings = get_settings()
    session = SessionLocal()
    queue = get_scraper_queue()
    try:
        job = session.query(ScraperJob).filter(ScraperJob.id == job_id).first()
        if not job:
            return {"ok": False, "status": "not_found", "job_id": job_id}
        if job.status in {"succeeded", "failed", "cancelled"}:
            return {"ok": True, "status": job.status, "job_id": job_id}

        job.cancelled = True
        if job.status != "cancelled":
            job.status = "cancelled"
            job.finished_at = datetime.utcnow()
        session.commit()

        if job.rq_job_id:
            try:
                rq_job = queue.fetch_job(job.rq_job_id)
                rq_job.cancel()
            except Exception:
                logger.debug("Unable to cancel rq job", exc_info=True)

        return {"ok": True, "status": "cancelled", "job_id": job_id}
    finally:
        session.close()


def get_scraper_queue_stats() -> dict:
    queue = get_scraper_queue()
    # RQ doesn't expose a very stable "running count" without a worker, so we provide best-effort queue length.
    return {
        "queue_name": queue.name,
        "queued": queue.count,
    }

