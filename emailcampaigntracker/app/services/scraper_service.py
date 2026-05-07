from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException

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
    global SCRAPER_STATUS

    if SCRAPER_STATUS.get("status") == "running":
        now = datetime.utcnow().timestamp()
        last_update = SCRAPER_STATUS.get("timestamp", 0)
        if now - last_update < 300:
            logger.warning("scrape_rejected_already_running source=%s", source)
            return {"status": "already running", "source": source}

    logger.info("scraper_triggered source=%s webhook=%s", source, bool(webhook_url))

    SCRAPER_STATUS["status"] = "running"
    SCRAPER_STATUS["message"] = f"Scraper started by {source}"
    SCRAPER_STATUS["timestamp"] = datetime.utcnow().timestamp()
    SCRAPER_STATUS["new_posts_found"] = 0

    try:
        args = [sys.executable, SCRAPER_SCRIPT]
        if webhook_url:
            args.append(f"webhook_url={webhook_url}")

        subprocess.Popen(args)

        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(SCRAPER_STATUS, f)

        return {"status": "started", "source": source, "webhook_url": webhook_url}
    except Exception as e:
        SCRAPER_STATUS["status"] = "error"
        SCRAPER_STATUS["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


def update_status(data: dict) -> dict:
    global SCRAPER_STATUS
    SCRAPER_STATUS.update(data)
    SCRAPER_STATUS["timestamp"] = datetime.utcnow().timestamp()

    try:
        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(SCRAPER_STATUS, f)
    except Exception:
        logger.exception("Failed to persist scraper status file.")

    return {"ok": True}


def get_in_memory_status() -> dict:
    return SCRAPER_STATUS

