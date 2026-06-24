"""
Webhook route: receives the scraper callback and fires Workflow 1 + 2.

This replaces the n8n Webhook node:
    POST /webhook/3aeb822a-2673-401f-9882-ff3dfe88db65

The scraper calls:
    POST /api/scrape?webhook_url=http://localhost:8000/webhook/scraper-callback
which then POSTs its result to this endpoint when done.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Body, Request

logger = logging.getLogger("webhook")

router = APIRouter(tags=["Webhook"])


def _run_workflows_1_and_2(payload: Dict[str, Any]) -> None:
    """
    Runs Workflow 1 (process profiles) → Workflow 2 (send emails) in a
    background thread so the webhook returns immediately to the scraper.
    """
    try:
        from app.workflows.runner import process_webhook_payload
        process_webhook_payload(payload)
    except Exception as exc:
        logger.error("Workflow 1+2 pipeline failed: %s", exc, exc_info=True)


@router.post("/webhook/scraper-callback")
async def scraper_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Scraper callback webhook endpoint.

    This is the Python replacement for the n8n Webhook node.
    The scraper POSTs its results here when scraping is complete.

    The workflow (1 → 2) runs in the background so we return 200 instantly.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    logger.info("Received scraper webhook callback. Launching Workflow 1+2 pipeline...")

    # Run in a background thread (non-blocking)
    thread = threading.Thread(
        target=_run_workflows_1_and_2,
        args=(payload,),
        daemon=True,
        name="workflow1-2-pipeline",
    )
    thread.start()

    return {"status": "accepted", "message": "Workflow 1+2 pipeline started in background"}
