from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("scraper")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRAPER_SCRIPT = os.path.join(PROJECT_ROOT, "scraper", "scrape_automation.py")
SCRAPER_STATUS_FILE = os.path.join(PROJECT_ROOT, "scraper_status.json")

SCRAPER_STATUS: Dict[str, Any] = {"status": "idle", "message": ""}


def get_scraper_status_from_file() -> dict:
    if not os.path.exists(SCRAPER_STATUS_FILE):
        return {"status": "idle", "new_posts_found": 0}
    try:
        with open(SCRAPER_STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed to read scraper_status.json.")
        return {"status": "error", "error": str(e)}


def trigger_scrape(webhook_url: Optional[str] = None, source: str = "unknown") -> dict:
    from app.services.scraper_job_service import enqueue_scraper_job

    logger.info("scraper_triggered source=%s webhook=%s", source, bool(webhook_url))
    result, job_id = enqueue_scraper_job(webhook_url=webhook_url, source=source)
    if result.get("status") == "started" and job_id is not None:
        SCRAPER_STATUS["status"] = "running"
        SCRAPER_STATUS["message"] = f"Scraper started by {source}"
        SCRAPER_STATUS["timestamp"] = datetime.utcnow().timestamp()
        SCRAPER_STATUS["new_posts_found"] = 0
        SCRAPER_STATUS["job_id"] = job_id
    return result


def update_status(data: dict) -> dict:
    global SCRAPER_STATUS
    # Fault tolerance: merge update into persisted state so fields like job_id survive restarts.
    try:
        persisted = get_scraper_status_from_file()
    except Exception:
        persisted = {}

    persisted.update(data)
    persisted["timestamp"] = datetime.utcnow().timestamp()

    # Keep the in-memory dict in sync for backward compatibility.
    SCRAPER_STATUS = persisted  # type: ignore[assignment]

    try:
        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(SCRAPER_STATUS, f)
    except Exception:
        logger.exception("Failed to persist scraper status file.")

    return {"ok": True}


def get_in_memory_status() -> dict:
    # Return persisted state for multi-instance safety.
    return get_scraper_status_from_file()

