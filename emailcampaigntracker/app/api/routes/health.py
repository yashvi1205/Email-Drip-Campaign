from fastapi import APIRouter
from sqlalchemy import text

from app.queue.redis_queue import get_redis_connection, get_scraper_queue
from database.db import SessionLocal
from rq.worker import Worker

from app.services.health_service import health_payload

router = APIRouter(tags=["Health"], prefix="")


@router.get(
    "/api/health",
    summary="Health Check",
    description="Check if the API is running and responding to requests",
    response_description="API health status"
)
def health_check():
    """Check API health status"""
    return health_payload()


@router.get(
    "/api/health/readiness",
    summary="Readiness Check",
    description="Check if all dependencies (database, Redis, queue) are available",
    response_description="Readiness status with dependency health checks"
)
def readiness_check():
    checks = {"database": "ok", "redis": "ok", "queue": "ok"}

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
    finally:
        db.close()

    try:
        redis_conn = get_redis_connection()
        redis_conn.ping()
    except Exception:
        checks["redis"] = "error"

    try:
        q = get_scraper_queue()
        _ = q.count
    except Exception:
        checks["queue"] = "error"

    status = "ready" if all(v == "ok" for v in checks.values()) else "not_ready"
    return {"status": status, "checks": checks}


@router.get("/api/health/queue")
def queue_health():
    q = get_scraper_queue()
    return {"queue_name": q.name, "queued": q.count}


@router.get("/api/health/workers")
def worker_health():
    redis_conn = get_redis_connection()
    workers = Worker.all(connection=redis_conn)
    return {
        "worker_count": len(workers),
        "workers": [
            {
                "name": w.name,
                "state": w.state,
                "queues": [q.name for q in w.queues],
            }
            for w in workers
        ],
    }

