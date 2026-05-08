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

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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


def execute_scraper_job(scraper_job_id: int, **kwargs) -> None:
    settings = get_settings()
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        # 1. ATOMIC TRANSITION: queued/retrying -> running
        # We use optimistic locking (version) and status check to ensure atomicity
        rows = session.query(ScraperJob).filter(
            ScraperJob.id == scraper_job_id,
            ScraperJob.status.in_(["queued", "retrying"]),
            ScraperJob.cancelled == False
        ).update({
            "status": "running",
            "started_at": now,
            "last_heartbeat": now,
            "attempts": ScraperJob.attempts + 1,
            "version": ScraperJob.version + 1
        }, synchronize_session=False)
        session.commit()

        if rows == 0:
            logger.warning("Scraper job %s skip: already running, cancelled, or missing", scraper_job_id)
            return

        # Fetch fresh job state
        job = session.query(ScraperJob).get(scraper_job_id)
        logger.info("Scraper job %s transition: running (attempt %s)", job.id, job.attempts)

        args = [sys.executable, "-u", SCRAPER_SCRIPT]
        if job.webhook_url:
            args.append(f"webhook_url={job.webhook_url}")

        # 2. INTERACTIVE MODE (Phase 3)
        # If not headless, we allow direct terminal access so user can log in manually
        if not settings.headless:
            logger.info("Starting scraper in INTERACTIVE mode (Headless=False)")
            proc = subprocess.Popen(
                args,
                env={**os.environ, "BACKEND_INTERNAL_URL": settings.backend_internal_url}
            )
            # No thread needed for queue in interactive mode
            stdout_buf = ["Interactive session - logs in terminal"]
            q = None 
        else:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env={**os.environ, "BACKEND_INTERNAL_URL": settings.backend_internal_url}
            )

            from queue import Queue, Empty
            from threading import Thread

            def enqueue_output(out, queue):
                try:
                    for line in iter(out.readline, ''):
                        queue.put(line)
                    out.close()
                except Exception:
                    pass

            q = Queue()
            t = Thread(target=enqueue_output, args=(proc.stdout, q))
            t.daemon = True
            t.start()
            stdout_buf = []

        start_ts = time.monotonic()
        last_heartbeat_ts = start_ts

        while True:
            # 2. HEARTBEAT & CANCELLATION CHECK
            current_ts = time.monotonic()
            if current_ts - last_heartbeat_ts > 30:  # Every 30s
                session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).update({
                    "last_heartbeat": datetime.utcnow()
                })
                session.commit()
                last_heartbeat_ts = current_ts

            # Refresh cancellation state
            session.expire_all()
            job = session.query(ScraperJob).get(scraper_job_id)
            if job and job.cancelled:
                logger.info("Scraper job %s: termination requested (cancelled)", scraper_job_id)
                proc.kill()
                job.status = "cancelled"
                job.finished_at = datetime.utcnow()
                session.commit()
                return

            # Read from queue without blocking
            if q:
                try:
                    line = q.get_nowait()
                    stdout_buf.append(line)
                    # Keep stdout minimal in worker logs, full logs in DB
                    if "error" in line.lower() or "critical" in line.lower():
                        logger.error("[SCRAPER %s]: %s", scraper_job_id, line.strip())
                except Empty:
                    if proc.poll() is not None:
                        break
                    time.sleep(1)
            else:
                # Interactive mode: just wait for process to exit
                if proc.poll() is not None:
                    break
                time.sleep(1)

            elapsed = time.monotonic() - start_ts
            if elapsed > settings.scraper_job_timeout_seconds:
                logger.error("Scraper job %s: TIMEOUT (elapsed=%ds)", scraper_job_id, elapsed)
                proc.kill()
                raise TimeoutError(f"Scraper job timed out after {elapsed}s")

        stdout = "".join(stdout_buf)
        stderr = ""
        rc = proc.wait()

        if rc == 0:
            session.query(ScraperJob).filter(ScraperJob.id == scraper_job_id).update({
                "status": "succeeded",
                "finished_at": datetime.utcnow(),
                "log_excerpt": _tail_excerpt(stdout, stderr),
                "last_error": None
            })
            session.commit()
            logger.info("Scraper job %s transition: succeeded", scraper_job_id)
            return

        # 3. FAILURE HANDLING
        job = session.query(ScraperJob).get(scraper_job_id)
        job.finished_at = datetime.utcnow()
        job.log_excerpt = _tail_excerpt(stdout, stderr)
        job.last_error = f"Scraper process failed (rc={rc})"
        
        if (job.attempts or 0) < (job.max_attempts or 0):
            job.status = "retrying"
            logger.warning("Scraper job %s failed (rc=%s), will retry", scraper_job_id, rc)
        else:
            job.status = "failed"
            logger.error("Scraper job %s failed permanently (rc=%s)", scraper_job_id, rc)
        
        session.commit()
        raise RuntimeError(f"Scraper process failed (rc={rc})")

    except Exception as e:
        # 4. CRITICAL EXCEPTION HANDLING
        logger.exception("Scraper job %s: execution exception", scraper_job_id)
        # Try to mark as failed in DB if not already finalized
        try:
            session.query(ScraperJob).filter(
                ScraperJob.id == scraper_job_id,
                ScraperJob.status == "running"
            ).update({
                "status": "failed",
                "finished_at": datetime.utcnow(),
                "last_error": str(e)
            })
            session.commit()
        except:
            pass
        raise
    finally:
        session.close()


from rq.worker import SimpleWorker

def main() -> None:
    redis_conn = get_redis_connection()
    queue = get_scraper_queue()
    worker = SimpleWorker([queue], connection=redis_conn, name=f"scraper-worker-{os.getpid()}")
    # Force a very high timeout for the worker itself on Windows
    worker.work(logging_level="INFO")


if __name__ == "__main__":
    main()

