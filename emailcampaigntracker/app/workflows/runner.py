"""
Drip Campaign Workflow Runner
=============================
Orchestrator that ties together all 4 converted n8n workflows.

Usage
-----
Import this module and call the relevant runner functions, or run the
scheduler directly:

    python -m app.workflows.runner

Workflow summary
----------------
Workflow 1 - Profile Scraping & Processing
    Triggered: manually or via scraper callback webhook.
    run_workflow1(webhook_payload)

Workflow 2 - New Lead Email (First Outreach)
    Triggered: after workflow1 produces new leads.
    run_workflow2(lead, gemini_api_key, gmail_service, db_session)

Workflow 3 - Follow-up Emails (Phase 2 Drip)
    Triggered: scheduled every 5 days at 09:00.
    run_workflow3(gemini_api_key, gmail_service, db_session)

Workflow 4 - Reply Detection & Tracking
    Triggered: every minute via Gmail polling loop.
    run_workflow4_on_email(email_dict)  -- per email
    start_gmail_polling_loop(gmail_service)  -- background loop
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("workflow_runner")

# ---------------------------------------------------------------------------
# Environment / configuration helpers
# ---------------------------------------------------------------------------

def _get_env(key: str, required: bool = True) -> Optional[str]:
    val = os.environ.get(key)
    if required and not val:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return val


# ---------------------------------------------------------------------------
# Dependency builders
# ---------------------------------------------------------------------------

def _build_db_session():
    """Returns a SQLAlchemy session from the existing database setup."""
    from database.db import SessionLocal
    return SessionLocal()


def _build_gmail_service(credentials_json: Optional[str] = None):
    """
    Builds and returns an authenticated Gmail API service.
    Uses GOOGLE_APPLICATION_CREDENTIALS or the supplied JSON path.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds_path = credentials_json or _get_env("GMAIL_OAUTH_CREDENTIALS_PATH", required=False)
    if not creds_path:
        raise EnvironmentError(
            "Set GMAIL_OAUTH_CREDENTIALS_PATH to a valid OAuth2 token JSON file."
        )
    
    # Fallback to local files if path doesn't exist (e.g., Windows path inside Linux container)
    if not os.path.exists(creds_path):
        basename = os.path.basename(creds_path.replace("\\", "/"))
        for fallback in [basename, os.path.join("/app", basename), os.path.join(".", basename)]:
            if os.path.exists(fallback):
                creds_path = fallback
                break

    creds = Credentials.from_authorized_user_file(creds_path)
    service = build("gmail", "v1", credentials=creds)
    return service


def _get_gemini_api_key() -> str:
    return _get_env("GEMINI_API_KEY")


# ---------------------------------------------------------------------------
# High-level orchestration: Workflow 1 + 2
# ---------------------------------------------------------------------------

def process_webhook_payload(webhook_payload: Dict[str, Any]) -> None:
    """
    Called when the scraper posts its callback to the webhook endpoint.

    Runs:
        Workflow 1 → splits, deduplicates, branches new vs existing leads
        Workflow 2 → sends first outreach email for each lead
    """
    from app.workflows.workflow1_scrape_and_process import run_workflow1
    from app.workflows.workflow2_new_lead_email import run_workflow2

    gemini_api_key = _get_gemini_api_key()
    gmail_service = _build_gmail_service()
    db_session = _build_db_session()

    try:
        # Workflow 1
        new_leads, existing_leads = run_workflow1(webhook_payload)

        # Workflow 2 – new leads (full AI cold email path)
        for lead in new_leads:
            try:
                run_workflow2(
                    lead=lead,
                    gemini_api_key=gemini_api_key,
                    gmail_service=gmail_service,
                    db_session=db_session,
                    is_existing_lead=False,
                )
            except Exception as exc:
                logger.error("Workflow 2 failed for lead %s: %s", lead.get("email"), exc, exc_info=True)

        # Workflow 2 – existing leads (activity-based email path)
        for lead in existing_leads:
            try:
                run_workflow2(
                    lead=lead,
                    gemini_api_key=gemini_api_key,
                    gmail_service=gmail_service,
                    db_session=db_session,
                    is_existing_lead=True,
                )
            except Exception as exc:
                logger.error("Workflow 2 (existing) failed for lead %s: %s", lead.get("email"), exc, exc_info=True)

    finally:
        db_session.close()


# ---------------------------------------------------------------------------
# High-level orchestration: Workflow 3 (scheduled)
# ---------------------------------------------------------------------------

def run_followup_campaign() -> None:
    """
    Runs Workflow 3 – Follow-up Emails.
    Should be called by a scheduler every 5 days at 09:00.
    """
    from app.workflows.workflow3_followup_emails import run_workflow3

    gemini_api_key = _get_gemini_api_key()
    gmail_service = _build_gmail_service()
    db_session = _build_db_session()

    try:
        run_workflow3(
            gemini_api_key=gemini_api_key,
            gmail_service=gmail_service,
            db_session=db_session,
        )
    finally:
        db_session.close()


# ---------------------------------------------------------------------------
# High-level orchestration: Workflow 4 (background polling thread)
# ---------------------------------------------------------------------------

def start_reply_detection_thread() -> threading.Thread:
    """
    Starts Workflow 4 – Reply Detection in a background daemon thread.
    The thread polls Gmail every 60 seconds for new replies.

    Returns the thread object (already started).
    """
    from app.workflows.workflow4_reply_detection import start_gmail_polling_loop

    gmail_service = _build_gmail_service()

    thread = threading.Thread(
        target=start_gmail_polling_loop,
        args=(gmail_service,),
        kwargs={"poll_interval_seconds": 60},
        daemon=True,
        name="workflow4-reply-detection",
    )
    thread.start()
    logger.info("Started Workflow 4 reply detection thread.")
    return thread


# ---------------------------------------------------------------------------
# Optional: APScheduler-based scheduler for Workflow 3
# ---------------------------------------------------------------------------

def start_followup_scheduler() -> None:
    """
    Starts an APScheduler job that calls run_followup_campaign()
    every 5 days at 09:00 (mirrors n8n scheduleTrigger: daysInterval=5, triggerAtHour=9).

    Requires: pip install apscheduler
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning(
            "APScheduler not installed. Install with: pip install apscheduler\n"
            "Alternatively, set up a cron job that calls run_followup_campaign() "
            "every 5 days at 09:00."
        )
        return

    scheduler = BackgroundScheduler()
    # Every 5 days at 09:00 — APScheduler doesn't have a "every N days" interval
    # that aligns with a time-of-day, so we use an interval trigger with start_date
    # set to the next 09:00 occurrence, or use a cron with day-of-week wildcard.
    # Closest equivalent: run daily at 09:00 and let workflow3 SQL filter handle timing.
    scheduler.add_job(
        run_followup_campaign,
        trigger=CronTrigger(hour=9, minute=0),  # Daily at 09:00; SQL filters 5-day window
        id="workflow3_followup_campaign",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started for Workflow 3 (daily check at 09:00).")
    return scheduler


# ---------------------------------------------------------------------------
# __main__ entry-point for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "followup":
        logger.info("Running follow-up campaign (Workflow 3)…")
        run_followup_campaign()
    elif command == "reply-detection":
        logger.info("Starting reply detection (Workflow 4)…")
        t = start_reply_detection_thread()
        t.join()
    else:
        print(__doc__)
