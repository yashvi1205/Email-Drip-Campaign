from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

from rq import Queue
from rq.worker import Worker

from app.core.settings import get_settings
from app.queue.redis_queue import get_redis_connection, get_scraper_queue
from database.db import SessionLocal
from database.models import ScraperJob

logger = logging.getLogger("scraper_worker")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRAPER_SCRIPT = os.path.join(PROJECT_ROOT, "scraper", "scrape_automation.py")
SCRAPER_STATUS_FILE = os.path.join(PROJECT_ROOT, "scraper_status.json")


def _persist_scraper_status(payload: dict) -> None:
    try:
        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(payload, f)
    except Exception:
        logger.exception("Failed to persist scraper_status.json")


def _tail_excerpt(stdout: str, stderr: str, limit_chars: int = 20000) -> str:
    combined = (stdout or "") + "\n" + (stderr or "")
    if len(combined) <= limit_chars:
        return combined
    return combined[-limit_chars:]


def execute_scraper_job(scraper_job_id: int) -> None:
    settings = get_settings()
    session = SessionLocal()
    job: ScraperJob | None = None
    try:
        job = session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).first()
        if not job:
            logger.error("Scraper job not found id=%s", scraper_job_id)
            return

        now = datetime.utcnow()
        job.attempts = (job.attempts or 0) + 1
        job.status = "running"
        job.started_at = now
        session.commit()

        # cancellation check before launching
        session.refresh(job)
        if job.cancelled:
            job.status = "cancelled"
            job.finished_at = datetime.utcnow()
            session.commit()
            _persist_scraper_status(
                {
                    "status": "cancelled",
                    "message": f"Scraper job cancelled (id={job.id})",
                    "timestamp": datetime.utcnow().timestamp(),
                    "new_posts_found": 0,
                }
            )
            return

        _persist_scraper_status(
            {
                "status": "running",
                "message": f"Scraper started by {job.source}",
                "timestamp": datetime.utcnow().timestamp(),
                "new_posts_found": 0,
                "job_id": job.id,
            }
        )

        args = [sys.executable, SCRAPER_SCRIPT]
        if job.webhook_url:
            args.append(f"webhook_url={job.webhook_url}")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        start_ts = time.monotonic()
        stdout_buf = []
        stderr_buf = []

        while True:
            # Refresh cancellation state
            session.expire_all()
            job = session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).first()
            if job and job.cancelled:
                proc.kill()
                out, err = proc.communicate(timeout=5)
                stdout_buf.append(out or "")
                stderr_buf.append(err or "")
                job.status = "cancelled"
                job.finished_at = datetime.utcnow()
                job.last_error = "Cancelled"
                session.commit()
                _persist_scraper_status(
                    {
                        "status": "cancelled",
                        "message": f"Scraper job cancelled (id={job.id})",
                        "timestamp": datetime.utcnow().timestamp(),
                        "new_posts_found": 0,
                    }
                )
                return

            elapsed = time.monotonic() - start_ts
            if elapsed > settings.scraper_job_timeout_seconds:
                proc.kill()
                out, err = proc.communicate(timeout=5)
                stdout_buf.append(out or "")
                stderr_buf.append(err or "")
                # Mark job for retry/failed before raising so DB is accurate immediately.
                job = session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).first()
                job.finished_at = datetime.utcnow()
                job.last_error = f"Scraper job timed out after {settings.scraper_job_timeout_seconds}s"
                job.log_excerpt = _tail_excerpt("".join(stdout_buf), "".join(stderr_buf))
                if (job.attempts or 0) < (job.max_attempts or 0):
                    job.status = "retrying"
                    _persist_scraper_status(
                        {
                            "status": "running",
                            "message": f"Scraper job retrying after timeout (id={job.id})",
                            "timestamp": datetime.utcnow().timestamp(),
                            "new_posts_found": 0,
                            "job_id": job.id,
                        }
                    )
                else:
                    job.status = "failed"
                    _persist_scraper_status(
                        {
                            "status": "error",
                            "message": f"Scraper job failed after timeout (id={job.id})",
                            "timestamp": datetime.utcnow().timestamp(),
                            "new_posts_found": 0,
                            "job_id": job.id,
                        }
                    )
                session.commit()
                raise TimeoutError(
                    f"Scraper job timed out after {settings.scraper_job_timeout_seconds}s"
                )

            # Stream output to terminal
            if proc.stdout:
                line = proc.stdout.readline()
                if line:
                    print(f"[SCRAPER]: {line.strip()}")
                    stdout_buf.append(line)
            
            if proc.poll() is not None:
                break

        stdout = "".join(stdout_buf)
        stderr = "".join(stderr_buf)
        rc = proc.returncode

        if rc == 0:
            job = session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).first()
            job.status = "succeeded"
            job.finished_at = datetime.utcnow()
            job.log_excerpt = _tail_excerpt(stdout, stderr)
            job.last_error = None
            session.commit()
            _persist_scraper_status(
                {
                    "status": "completed",
                    "message": f"Scraper completed (id={job.id})",
                    "timestamp": datetime.utcnow().timestamp(),
                    "new_posts_found": 0,
                    "job_id": job.id,
                }
            )
            return

        # failure -> retry if allowed by rq retry config
        job = session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).first()
        job.finished_at = datetime.utcnow()
        job.last_error = f"Scraper process failed (rc={rc})"
        job.log_excerpt = _tail_excerpt(stdout, stderr)
        if (job.attempts or 0) < (job.max_attempts or 0):
            job.status = "retrying"
            message = f"Scraper retrying (id={job.id}, attempts={job.attempts}/{job.max_attempts})"
        else:
            job.status = "failed"
            message = f"Scraper failed (id={job.id}, attempts={job.attempts}/{job.max_attempts})"
        session.commit()

        _persist_scraper_status(
            {
                "status": "running" if job.status == "retrying" else "error",
                "message": message,
                "timestamp": datetime.utcnow().timestamp(),
                "new_posts_found": 0,
                "job_id": job.id,
            }
        )

        raise RuntimeError(f"Scraper process failed (rc={rc})")

    except Exception as e:
        logger.exception("Scraper job execution failed job_id=%s", scraper_job_id)
        if job:
            job.last_error = str(e)
            job.log_excerpt = job.log_excerpt or ""
            # keep status as-is if already set; otherwise mark failed
            if job.status not in {"cancelled"}:
                job.status = job.status if job.status else "failed"
            session.commit()
        raise
    finally:
        session.close()


from rq.worker import SimpleWorker

def main() -> None:
    redis_conn = get_redis_connection()
    queue = get_scraper_queue()
    worker = SimpleWorker([queue], connection=redis_conn, name=f"scraper-worker-{os.getpid()}")
    worker.work(logging_level="INFO")


if __name__ == "__main__":
    main()

