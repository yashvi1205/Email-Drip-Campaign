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
    Creates + enqueues a scraper background job with zombie cleanup.
    """
    settings = get_settings()
    redis_conn = get_redis_connection()
    queue = get_scraper_queue()
    now = datetime.utcnow()

    # 1. Concurrency Protection: Distributed Lock
    lock_key = "scraper:run_lock"
    lock_value = str(uuid.uuid4())
    acquired = redis_conn.set(
        lock_key, lock_value, nx=True, ex=30  # Short lock just for enqueuing
    )
    if not acquired:
        return {"status": "error", "message": "Queue busy, try again in a few seconds"}, None

    session = SessionLocal()
    try:
        # 2. Backlog Protection (Phase 3)
        queued_count = session.query(ScraperJob).filter(ScraperJob.status == "queued").count()
        if queued_count > 50: # Configurable limit
            return {"status": "error", "message": f"Backlog too large ({queued_count} jobs). Please wait."}, None

        # Zombie Cleanup & Already Running Check
        # Find jobs that are 'running' but haven't pulsed for 10 mins
        zombie_threshold = datetime.utcnow().timestamp() - 600
        zombies = session.query(ScraperJob).filter(
            ScraperJob.status == "running",
            ScraperJob.last_heartbeat < datetime.fromtimestamp(zombie_threshold)
        ).all()
        
        for zombie in zombies:
            logger.warning("Cleanup: Marking zombie job %s as failed", zombie.id)
            zombie.status = "failed"
            zombie.last_error = "Zombie detected: heartbeat timed out"
            zombie.finished_at = datetime.utcnow()
        session.commit()

        # Check for truly running jobs
        running_job = session.query(ScraperJob).filter(
            ScraperJob.status.in_(["queued", "running", "retrying"]),
            ScraperJob.cancelled == False
        ).order_by(ScraperJob.created_at.desc()).first()

        if running_job:
            return {"status": "already running", "job_id": running_job.id}, None

        # 3. Job Creation
        job = ScraperJob(
            status="queued",
            source=source,
            webhook_url=webhook_url,
            attempts=0,
            max_attempts=settings.scraper_job_max_attempts,
            cancelled=False,
            version=1,
            created_at=now
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # 4. Redis Enqueue
        from app.workers.scraper_worker import execute_scraper_job
        retry = Retry(
            max=max(0, settings.scraper_job_max_attempts - 1),
            interval=settings.scraper_job_retry_interval_seconds,
        )
        rq_job = queue.enqueue(
            execute_scraper_job,
            job.id,
            job_id=f"scraper_{job.id}",
            retry=retry,
            timeout=settings.scraper_job_timeout_seconds + 60,
        )

        job.rq_job_id = rq_job.id
        session.commit()

        return {"status": "started", "job_id": job.id}, job.id
    except Exception as e:
        session.rollback()
        logger.exception("Failed to enqueue scraper job")
        return {"status": "error", "message": str(e)}, None
    finally:
        session.close()
        redis_conn.delete(lock_key)

def get_scraper_job(job_id: int) -> Optional[ScraperJob]:
    session = SessionLocal()
    try:
        return session.query(ScraperJob).get(job_id)
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
    session = SessionLocal()
    queue = get_scraper_queue()
    try:
        job = session.query(ScraperJob).get(job_id)
        if not job:
            return {"ok": False, "status": "not_found"}
        
        if job.status in {"succeeded", "failed", "cancelled"}:
            return {"ok": True, "status": job.status}

        # Atomic cancellation
        job.cancelled = True
        job.status = "cancelled"
        job.finished_at = datetime.utcnow()
        session.commit()

        if job.rq_job_id:
            try:
                rq_job = queue.fetch_job(job.rq_job_id)
                if rq_job:
                    rq_job.cancel()
            except: pass

        return {"ok": True, "status": "cancelled"}
    finally:
        session.close()

def get_scraper_queue_stats() -> dict:
    queue = get_scraper_queue()
    session = SessionLocal()
    try:
        running = session.query(ScraperJob).filter(ScraperJob.status == "running").count()
        failed = session.query(ScraperJob).filter(ScraperJob.status == "failed").count()
        succeeded = session.query(ScraperJob).filter(ScraperJob.status == "succeeded").count()
        
        return {
            "queue_name": queue.name,
            "queued": queue.count,
            "running": running,
            "failed_total": failed,
            "succeeded_total": succeeded,
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        session.close()

