"""
Workflow 3 - Follow-up Emails (Phase 2 Drip Sequence)
======================================================
Converted from n8n workflow: "AI Drip Campaign - Full System"

n8n nodes covered (in execution order):
  1. Phase2 Cron (Follow-ups)        (scheduleTrigger – every 5 days at 09:00)
  2. Fetch Leads Needing Follow-up   (Postgres SELECT – leads that need follow-up)
  3. Loop Over Items1                (splitInBatches – iterates one lead at a time)
  4. Build Follow-up Context         (Code node → builds ai_summary + next_step)
  5. AI Generate Follow-up Email     (Google Gemini – follow-up email)
  6. Prepare Follow-up with Tracking (Code node → injects pixel + click tracking)
  7. Insert Follow-up Sequence       (Postgres INSERT into email_sequences)
  8. Send Follow-up via Gmail        (Gmail send)
  9. Call /sent for Follow-up        (HTTP POST → /api/tracking/sent/<tracking_id>)
 10. Mark Stale Leads as IGNORED     (Postgres UPDATE)
 11. Loop Over Items1 (back)         (loops back until all leads processed)

The function `run_workflow3` is the main entry-point.
It should be called on a schedule (every 5 days at 09:00) by a scheduler such
as APScheduler, Celery Beat, or a cron job.
"""

from __future__ import annotations

import logging
import random
import string
import time
from typing import Any, Dict, List

import requests
from sqlalchemy import text

from app.workflows.workflow2_new_lead_email import (
    _build_email_html,
    _call_gemini,
    _generate_tracking_id,
    _parse_gemini_response,
    node_send_email_via_gmail,
    BACKEND_URL,
    LOCAL_BACKEND_URL,
    GEMINI_MODEL,
    CTA_URL,
)

logger = logging.getLogger("workflow3")


# ---------------------------------------------------------------------------
# Node 2: Fetch Leads Needing Follow-up
# ---------------------------------------------------------------------------

def node_fetch_leads_needing_followup(db_session) -> List[Dict[str, Any]]:
    """
    n8n node: "Fetch Leads Needing Follow-up"
    Type: postgres (executeQuery)

    SQL (verbatim from n8n):
        SELECT l.id AS lead_id, l.name, l.email, l.status, l.company, l.role,
               l.headline, l.about, l.linkedin_url,
               es.step_number, es.tracking_id AS last_tracking_id,
               es.sent_at, es.opened_at, es.replied
        FROM leads l
        JOIN email_sequences es ON es.lead_id = l.id
        JOIN (
            SELECT lead_id, MAX(sent_at) AS max_sent_at
            FROM email_sequences
            WHERE opened_at IS NULL
              AND COALESCE(replied, FALSE) = FALSE
              AND sent_at <= NOW() - INTERVAL '5 days'
            GROUP BY lead_id
        ) valid ON valid.lead_id = es.lead_id AND valid.max_sent_at = es.sent_at
        WHERE l.status IN ('SENT', 'IGNORED')
          AND es.step_number < 6;
    """
    sql = text("""
        SELECT
            l.id AS lead_id,
            l.name,
            l.email,
            l.status,
            l.company,
            l.role,
            l.headline,
            l.about,
            l.linkedin_url,
            es.step_number,
            es.tracking_id AS last_tracking_id,
            es.sent_at,
            es.opened_at,
            es.replied
        FROM leads l
        JOIN email_sequences es
            ON es.lead_id = l.id
        JOIN (
            SELECT lead_id, MAX(sent_at) AS max_sent_at
            FROM email_sequences
            WHERE
                opened_at IS NULL
                AND COALESCE(replied, FALSE) = FALSE
                AND sent_at <= NOW() - INTERVAL '5 days'
            GROUP BY lead_id
        ) valid
            ON valid.lead_id = es.lead_id
            AND valid.max_sent_at = es.sent_at
        WHERE
            l.status IN ('SENT', 'IGNORED')
            AND es.step_number < 6;
    """)

    result = db_session.execute(sql)
    rows = result.mappings().all()
    leads = [dict(r) for r in rows]
    logger.info("Fetched %d leads needing follow-up.", len(leads))
    return leads


# ---------------------------------------------------------------------------
# Node 4: Build Follow-up Context
# ---------------------------------------------------------------------------

def node_build_followup_context(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    n8n node: "Build Follow-up Context"
    Type: Code (JavaScript → Python)

    Builds ai_summary and computes next_step for the follow-up email.
    """
    next_step = (item.get("step_number") or 1) + 1
    summary = "\n".join([
        f"Name: {item.get('name', '')}",
        f"Role: {item.get('role', 'Professional')}",
        f"Company: {item.get('company', 'their company')}",
        f"Previous emails sent: {item.get('step_number', 1)}",
        f"Follow-up number: {next_step}",
        f"About: {(item.get('about') or '')[:200]}",
    ])
    return {**item, "ai_summary": summary, "next_step": next_step}


# ---------------------------------------------------------------------------
# Node 5: AI Generate Follow-up Email
# ---------------------------------------------------------------------------

def node_ai_generate_followup_email(
    item: Dict[str, Any],
    gemini_api_key: str,
) -> Dict[str, Any]:
    """
    n8n node: "AI Generate Follow-up Email"
    Type: @n8n/n8n-nodes-langchain.googleGemini

    Follow-up email styles by step (from n8n prompt):
        2 → Insight / value add
        3 → Social proof
        4 → Direct question
        5 → Soft urgency
        6 → Break-up (polite close)
    """
    prompt = (
        "You are a highly skilled sales strategist writing cold email follow-ups.\n\n"
        "Recipient:\n"
        f"{item.get('ai_summary', '')}\n\n"
        "Context:\n"
        f"- This is follow-up #{item.get('next_step', 2)}\n"
        "- Previous emails were sent but no reply\n\n"
        "Strategy:\n"
        "- Each follow-up must feel NEW and valuable (not repetitive)\n"
        "- Use psychological triggers: curiosity, relevance, light urgency\n"
        "- Keep it natural and human (NOT salesy)\n\n"
        "Follow-up styles:\n"
        "2 → Insight / value add  \n"
        "3 → Social proof  \n"
        "4 → Direct question  \n"
        "5 → Soft urgency  \n"
        "6 → Break-up (polite close)\n\n"
        "Rules:\n"
        "- Max 80 words\n"
        "- No placeholders\n"
        "- No generic phrases\n"
        "- First line must feel personalized\n"
        "- End with a simple question\n\n"
        "Return ONLY valid JSON:\n"
        "{\n  \"subject\": \"...\",\n  \"body\": \"...\"\n}"
    )

    response = _call_gemini(prompt, gemini_api_key)
    return {**item, "gemini_response": response}


# ---------------------------------------------------------------------------
# Node 6: Prepare Follow-up with Tracking
# ---------------------------------------------------------------------------

def node_prepare_followup_with_tracking(
    followup_context_item: Dict[str, Any],
    gemini_response_item: Dict[str, Any],
) -> Dict[str, Any]:
    """
    n8n node: "Prepare Follow-up with Tracking"
    Type: Code (JavaScript → Python)

    Uses lead data from Build Follow-up Context and AI response from
    AI Generate Follow-up Email to produce the full tracked HTML email.
    """
    lead_data = followup_context_item
    next_step = lead_data.get("next_step", 2)

    gemini_raw = gemini_response_item.get("gemini_response", {})
    parsed = _parse_gemini_response(
        gemini_raw,
        fallback_subject=f"Quick follow-up ({next_step})",
        fallback_body="Hi, wanted to follow up and see if this topic is relevant for you right now.",
    )

    tracking_id = _generate_tracking_id("trk_fu")

    from app.core.settings import get_settings
    try:
        settings = get_settings()
        backend_url = settings.local_backend_url or settings.backend_internal_url or BACKEND_URL
    except Exception:
        backend_url = BACKEND_URL

    email_body_html = _build_email_html(
        body=parsed["body"],
        tracking_id=tracking_id,
        backend_url=backend_url,
        cta_label="Schedule a quick call",
    )

    return {
        **lead_data,
        "tracking_id": tracking_id,
        "email_subject": parsed["subject"],
        "email_body_html": email_body_html,
        "email_body_plain": parsed["body"],
        "step_number": next_step,
    }


# ---------------------------------------------------------------------------
# Node 7: Insert Follow-up Sequence
# ---------------------------------------------------------------------------

def node_insert_followup_sequence(data: Dict[str, Any], db_session) -> Dict[str, Any]:
    """
    n8n node: "Insert Follow-up Sequence"
    Type: postgres (executeQuery)

    SQL (verbatim from n8n):
        INSERT INTO email_sequences (lead_id, step_number, tracking_id, status)
        VALUES (lead_id, step_number, tracking_id, 'sent');
    """
    sql = text("""
        INSERT INTO email_sequences (lead_id, step_number, tracking_id, status)
        VALUES (:lead_id, :step_number, :tracking_id, 'sent');
    """)
    params = {
        "lead_id": data["lead_id"],
        "step_number": data.get("step_number", 2),
        "tracking_id": data["tracking_id"],
    }
    db_session.execute(sql, params)
    db_session.commit()
    logger.info(
        "Inserted follow-up sequence: lead_id=%s step=%s tracking=%s",
        data["lead_id"], data["step_number"], data["tracking_id"],
    )
    return data


# ---------------------------------------------------------------------------
# Node 9: Call /sent for Follow-up
# ---------------------------------------------------------------------------

def node_call_sent_for_followup(data: Dict[str, Any]) -> None:
    """
    n8n node: "Call /sent for Follow-up"
    Type: httpRequest (POST)
    URL:  http://127.0.0.1:8000/api/tracking/sent/<tracking_id>?step=<step_number>
    """
    tracking_id = data.get("tracking_id")
    step = data.get("step_number", 2)
    
    from app.core.settings import get_settings
    try:
        settings = get_settings()
        backend_url = settings.backend_internal_url or LOCAL_BACKEND_URL
    except Exception:
        backend_url = LOCAL_BACKEND_URL
        
    url = f"{backend_url}/api/tracking/sent/{tracking_id}?step={step}"
    try:
        resp = requests.post(url, timeout=10)
        resp.raise_for_status()
        logger.info("Called /sent for follow-up tracking_id=%s step=%s", tracking_id, step)
    except requests.RequestException as exc:
        logger.warning("Failed to call /sent for follow-up: %s", exc)


# ---------------------------------------------------------------------------
# Node 10: Mark Stale Leads as IGNORED
# ---------------------------------------------------------------------------

def node_mark_stale_leads_as_ignored(db_session) -> None:
    """
    n8n node: "Mark Stale Leads as IGNORED"
    Type: postgres (executeQuery)

    SQL (verbatim from n8n):
        UPDATE leads SET status = 'IGNORED'
        WHERE status = 'SENT'
          AND id IN (
            SELECT lead_id FROM email_sequences
            WHERE opened_at IS NULL
              AND replied = FALSE
              AND sent_at <= NOW() - INTERVAL '5 days'
          );
    """
    sql = text("""
        UPDATE leads SET status = 'IGNORED'
        WHERE status = 'SENT'
          AND id IN (
            SELECT lead_id FROM email_sequences
            WHERE opened_at IS NULL
              AND replied = FALSE
              AND sent_at <= NOW() - INTERVAL '5 days'
          );
    """)
    db_session.execute(sql)
    db_session.commit()
    logger.info("Marked stale leads as IGNORED.")


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def run_workflow3(
    gemini_api_key: str,
    gmail_service,
    db_session,
) -> None:
    """
    Full Workflow 3 execution pipeline.

    This should be called by a scheduler every 5 days at 09:00 (mirroring
    the n8n scheduleTrigger: daysInterval=5, triggerAtHour=9).

    Args:
        gemini_api_key: Google Gemini API key.
        gmail_service:  Authenticated google-api-python-client Gmail service.
        db_session:     SQLAlchemy session bound to Postgres.
    """
    logger.info("=== Workflow 3: Follow-up Emails Started ===")

    # ---- Step 1: Fetch leads that need a follow-up -------------------------
    leads = node_fetch_leads_needing_followup(db_session)

    if not leads:
        logger.info("No leads need a follow-up at this time.")
    else:
        # ---- Step 2: Loop Over Items1 (one lead at a time) -----------------
        for lead in leads:
            try:
                # ---- Step 3: Build follow-up context -----------------------
                context_item = node_build_followup_context(lead)

                # ---- Step 4: Generate follow-up email via Gemini -----------
                gemini_item = node_ai_generate_followup_email(context_item, gemini_api_key)

                # ---- Step 5: Prepare email with tracking -------------------
                send_data = node_prepare_followup_with_tracking(context_item, gemini_item)

                # ---- Step 6: Insert follow-up sequence row -----------------
                send_data = node_insert_followup_sequence(send_data, db_session)

                # ---- Step 7: Send follow-up email via Gmail ----------------
                node_send_email_via_gmail(send_data, gmail_service)

                # ---- Step 8: Call /sent endpoint ---------------------------
                node_call_sent_for_followup(send_data)

            except Exception as exc:
                logger.error(
                    "Error processing follow-up for lead_id=%s: %s",
                    lead.get("lead_id"), exc, exc_info=True,
                )
                continue

    # ---- Step 9: Mark stale leads as IGNORED (runs after every loop) ------
    node_mark_stale_leads_as_ignored(db_session)

    logger.info("=== Workflow 3: Follow-up Emails Completed ===")
