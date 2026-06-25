"""
Workflow 2 - New Lead Email (First Outreach)
============================================
Converted from n8n workflow: "AI Drip Campaign - Full System"

n8n nodes covered (in execution order, per item in "Loop Over Items"):
  1. Loop Over Items                (splitInBatches – iterates new leads one at a time)
  2. Build AI Summary               (Code node → builds ai_summary text)
  3. AI Generate Personalized Email (Google Gemini → cold email)
  4. Build Activity Summary         (Code node – existing lead path)
  5. Message a model                (Google Gemini – existing lead activity email)
  6. Prepare Email with Tracking    (Code node → injects pixel + click tracking)
  7. Prepare DB Values              (Code node → merges email + lead data)
  8. Upsert Lead in DB              (Postgres INSERT … ON CONFLICT)
  9. Get Lead ID from DB            (Code node → extracts returned id)
 10. Insert Email Sequence Row      (Postgres INSERT into email_sequences)
 11. Code in JavaScript             (Code node → merges everything for send)
 12. Send Email via Gmail           (Gmail send)
 13. Call Backend /sent Endpoint    (HTTP POST → /api/tracking/sent/<tracking_id>)

The function `run_workflow2` is the main entry-point.
It accepts a single lead dict (one iteration of the loop) and sends email + records DB rows.
Call it in a for-loop over the `new_leads` list returned by workflow1.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import string
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("workflow2")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKEND_URL = "https://email-drip-campaign-hpo2.onrender.com"
LOCAL_BACKEND_URL = "http://127.0.0.1:8000"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
CTA_URL = "https://example.com"  # Replace with real CTA URL


# ---------------------------------------------------------------------------
# Helper: generate tracking ID
# ---------------------------------------------------------------------------

def _generate_tracking_id(prefix: str = "trk") -> str:
    """Mirrors: 'trk_' + Date.now() + '_' + Math.random().toString(36).substring(2,10)"""
    ts = int(time.time() * 1000)
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}_{ts}_{rand_suffix}"


# ---------------------------------------------------------------------------
# Helper: build tracked HTML email body
# ---------------------------------------------------------------------------

def _build_email_html(
    body: str,
    tracking_id: str,
    backend_url: str = BACKEND_URL,
    cta_url: str = CTA_URL,
    cta_label: str = "Book a quick call",
) -> str:
    """
    Mirrors the JS in "Prepare Email with Tracking" and "Prepare Follow-up with Tracking":
    - Wraps bare URLs in tracked redirect links
    - Appends a CTA button
    - Appends a hidden tracking div
    - Appends a 1x1 tracking pixel
    - Wraps everything in <html><body>
    """
    tracking_pixel = (
        f'\n<img \n  src="{backend_url}/api/tracking/track/{tracking_id}" \n'
        f'  width="1" \n  height="1" \n  style="display:none;" \n/>\n'
    )

    # Replace bare URLs with tracked redirects
    def replace_url(match):
        url = match.group(0)
        if backend_url in url:
            return url
        tracked = f"{backend_url}/api/tracking/click/{tracking_id}?url={requests.utils.quote(url)}"
        return (
            f'\n    <a href="{tracked}"\n'
            f'       target="_blank"\n'
            f'       style="color:#1a73e8;text-decoration:none;">\n'
            f'       View details\n'
            f'    </a>\n  '
        )

    email_body = re.sub(r"https?://[^\s<>\"]+", replace_url, body)

    # CTA button
    tracked_cta = f"{backend_url}/api/tracking/click/{tracking_id}?url={requests.utils.quote(cta_url)}"
    cta_button = (
        f'\n<br><br>\n<a href="{tracked_cta}"\n'
        f'   target="_blank"\n'
        f'   style="\n      background:#1a73e8;\n      color:#ffffff;\n'
        f'      padding:10px 16px;\n      text-decoration:none;\n'
        f'      border-radius:5px;\n      display:inline-block;\n   ">\n'
        f'   {cta_label}\n</a>\n'
    )

    # Convert newlines to <br>
    email_body = email_body.replace("\n", "<br>")

    hidden_tracking = (
        f'\n<div style="display:none;font-size:1px;color:#ffffff;">\n'
        f'{tracking_id}\n</div>\n'
    )

    html = (
        f'\n<html>\n<body style="font-family:Arial,sans-serif;line-height:1.6;">\n'
        f'{email_body}\n{cta_button}\n{hidden_tracking}\n{tracking_pixel}\n'
        f'</body>\n</html>\n'
    )
    return html


# ---------------------------------------------------------------------------
# Helper: parse Gemini API response to subject + body
# ---------------------------------------------------------------------------

def _parse_gemini_response(gemini_response: Dict[str, Any], fallback_subject: str, fallback_body: str) -> Dict[str, str]:
    """
    Mirrors the JS in "Prepare Email with Tracking":
    Extracts the JSON part from Gemini's content.parts[].text and parses it.
    Falls back to defaults on parse failure.
    """
    parts = gemini_response.get("content", {}).get("parts", [])
    json_part = next(
        (
            p.get("text", "")
            for p in parts
            if p.get("text", "").strip().startswith("```json")
            or p.get("text", "").strip().startswith("{")
        ),
        "",
    )
    ai_raw = json_part.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(ai_raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Gemini JSON parse failed: %s", exc)
        parsed = {"subject": fallback_subject, "body": fallback_body}
    return {
        "subject": parsed.get("subject", fallback_subject),
        "body": parsed.get("body", fallback_body),
    }


# ---------------------------------------------------------------------------
# Node 2: Build AI Summary (new lead path)
# ---------------------------------------------------------------------------

def node_build_ai_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    n8n node: "Build AI Summary"
    Type: Code (JavaScript → Python)

    Builds a plain-text ai_summary from the lead's profile fields.
    """
    recent = item.get("recent_activity") or []
    if isinstance(recent, list):
        recent_text = "; ".join(recent[:2])
    else:
        recent_text = str(recent)

    summary = "\n".join([
        f"Name: {item.get('name', 'Unknown')}",
        f"Role: {item.get('role', 'Professional')}",
        f"Company: {item.get('company', 'their company')}",
        f"Headline: {item.get('headline', '')}",
        f"About: {(item.get('about') or '')[:300]}",
        f"Recent Activity: {recent_text}",
    ])
    return {**item, "ai_summary": summary}


# ---------------------------------------------------------------------------
# Node 4: Build Activity Summary (existing lead / activity path)
# ---------------------------------------------------------------------------

def node_build_activity_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    n8n node: "Build Activity Summary"
    Type: Code (JavaScript → Python)

    Builds an ai_summary from the lead's latest interaction activity.
    Used for existing leads who just performed an action (post/comment/like).
    """
    summary = "\n".join([
        f"Name: {item.get('name', '')}",
        f"Company: {item.get('company', '')}",
        f"Action: {item.get('interaction_type', '')}ed: {item.get('latest_content', '')}",
    ])
    return {**item, "ai_summary": summary}


# ---------------------------------------------------------------------------
# Node 3: AI Generate Personalized Email (new lead)
# ---------------------------------------------------------------------------

def node_ai_generate_personalized_email(
    item: Dict[str, Any],
    gemini_api_key: str,
) -> Dict[str, Any]:
    """
    n8n node: "AI Generate Personalized Email"
    Type: @n8n/n8n-nodes-langchain.googleGemini
    Model: models/gemini-3-flash-preview

    Calls the Gemini API with the cold outreach prompt and returns the raw response dict.
    """
    prompt = (
        "You are a highly skilled B2B cold email strategist.\n\n"
        "Write a short, personalized outreach email.\n\n"
        "Recipient:\n"
        f"{item.get('ai_summary', '')}\n\n"
        "Objective:\nStart a conversation (NOT sell anything directly).\n\n"
        "---\n\nRules:\n\n"
        "1. Subject line:\n- Must reference their company, role, or recent activity\n"
        "- 3–7 words max\n- No spam words\n\n"
        "2. Opening line:\n- Must feel specific and real (based on their profile)\n"
        "- Avoid generic lines like \"I came across your profile\"\n\n"
        "3. Body:\n- Show you understand what they do\n"
        "- Add 1 insight / observation / angle\n- Keep it natural, human, not salesy\n\n"
        "4. Length:\n- Max 80–100 words\n\n"
        "5. Tone:\n- Friendly, sharp, confident\n- No buzzwords, no fluff\n\n"
        "---\n\n6. ENDING (VERY IMPORTANT):\n\nUse ONE of these high-performing styles:\n\n"
        "- Curious question:\n  \"Curious how you're currently approaching this?\"\n\n"
        "- Light ask:\n  \"Worth a quick exchange of thoughts?\"\n\n"
        "- Soft open:\n  \"Would love to hear your perspective.\"\n\n"
        "- Low-friction:\n  \"Open to a quick chat?\"\n\n"
        "   Do NOT say:\n- \"Let me know\"\n- \"Schedule a call\"\n- \"Book a meeting\"\n\n"
        "---\n\nReturn ONLY valid JSON:\n{\"subject\": \"...\", \"body\": \"...\"}"
    )

    response = _call_gemini(prompt, gemini_api_key)
    return {**item, "gemini_response": response}


# ---------------------------------------------------------------------------
# Node 5: Message a model (existing lead / activity email)
# ---------------------------------------------------------------------------

def node_message_a_model(
    item: Dict[str, Any],
    gemini_api_key: str,
) -> Dict[str, Any]:
    """
    n8n node: "Message a model"
    Type: @n8n/n8n-nodes-langchain.googleGemini
    Model: models/gemini-3-flash-preview

    Generates a follow-up email referencing the lead's latest activity.
    """
    prompt = (
        "You are writing a quick follow-up email to someone you already know.\n\n"
        "Context:\n"
        f"{item.get('ai_summary', '')}\n\n"
        f"Task:\nWrite a very short (max 50 words) email mentioning their latest "
        f"{item.get('interaction_type', 'activity')}.\n\n"
        "Rules:\n- Sound like a human following up.\n"
        f"- Mention specifically: \"{item.get('latest_content', '')}\"\n"
        "- End with a low-pressure question about the topic.\n\n"
        "Return ONLY valid JSON:\n"
        "{ \"subject\": \"Saw your post about...\", \"body\": \"...\" }"
    )

    response = _call_gemini(prompt, gemini_api_key)
    return {**item, "gemini_response": response}


# ---------------------------------------------------------------------------
# Helper: Gemini HTTP call
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str) -> Dict[str, Any]:
    """
    Direct REST call to the Gemini generateContent API.
    Mirrors what the n8n googleGemini node does internally.
    Includes retry logic with backoff for transient errors (e.g. 503).
    """
    import time
    # Ensure model name has the required 'models/' prefix for the REST API
    model = GEMINI_MODEL
    if not model.startswith("models/"):
        model = f"models/{model}"

    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    
    max_retries = 3
    backoff = 2
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # Normalise to what n8n returns: {content: {parts: [...]}}
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                return {"content": content}
            return {"content": {"parts": []}}
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 500
            if status_code in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                sleep_time = backoff ** (attempt + 1)
                logger.warning("Gemini API returned transient status %s. Retrying in %d seconds (attempt %d/%d)...", 
                               status_code, sleep_time, attempt + 1, max_retries)
                time.sleep(sleep_time)
            else:
                raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt < max_retries - 1:
                sleep_time = backoff ** (attempt + 1)
                logger.warning("Gemini API request failed due to connection/timeout: %s. Retrying in %d seconds (attempt %d/%d)...", 
                               exc, sleep_time, attempt + 1, max_retries)
                time.sleep(sleep_time)
            else:
                raise
                
    return {"content": {"parts": []}}


# ---------------------------------------------------------------------------
# Node 6: Prepare Email with Tracking
# ---------------------------------------------------------------------------

def node_prepare_email_with_tracking(
    gemini_response_item: Dict[str, Any],
) -> Dict[str, Any]:
    """
    n8n node: "Prepare Email with Tracking"
    Type: Code (JavaScript → Python)

    Parses the Gemini JSON response, builds the full HTML email with tracking
    pixel + click-redirect links + CTA button.
    Returns a dict with:
        tracking_id, email_subject, email_body_html, email_body_plain, step_number
    """
    gemini_raw = gemini_response_item.get("gemini_response", {})
    parsed = _parse_gemini_response(
        gemini_raw,
        fallback_subject="Quick question",
        fallback_body="Hi, wanted to follow up and see if this topic is relevant for you right now.",
    )

    subject = parsed["subject"]
    body = parsed["body"]
    tracking_id = _generate_tracking_id("trk")

    from app.core.settings import get_settings
    try:
        settings = get_settings()
        # Priority:
        # 1. TRACKING_BASE_URL  — explicit override (e.g. ngrok public URL)
        # 2. BACKEND_INTERNAL_URL — set in .env / docker-compose (e.g. http://192.168.x.x:8000)
        # 3. Hard-coded Render URL — last resort for production-only deploys
        backend_url = (
            os.getenv("TRACKING_BASE_URL")
            or settings.backend_internal_url
            or BACKEND_URL
        )
    except Exception:
        backend_url = os.getenv("TRACKING_BASE_URL") or os.getenv("BACKEND_INTERNAL_URL") or BACKEND_URL

    email_body_html = _build_email_html(
        body=body,
        tracking_id=tracking_id,
        backend_url=backend_url,
        cta_label="Book a quick call",
    )

    return {
        "tracking_id": tracking_id,
        "email_subject": subject,
        "email_body_html": email_body_html,
        "email_body_plain": body,
        "step_number": 1,
    }


# ---------------------------------------------------------------------------
# Node 7: Prepare DB Values
# ---------------------------------------------------------------------------

def node_prepare_db_values(
    email_tracking_data: Dict[str, Any],
    lead_data: Dict[str, Any],
    db_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    n8n node: "Prepare DB Values"
    Type: Code (JavaScript → Python)

    Merges email tracking data, lead profile data, and DB insert result.
    Extracts lead_id from the DB result.
    """
    lead_id = db_result.get("id") or (
        db_result.get("rows", [{}])[0].get("id") if db_result.get("rows") else None
    )
    return {**email_tracking_data, **lead_data, "lead_id": lead_id}


# ---------------------------------------------------------------------------
# Node 8: Upsert Lead in DB
# ---------------------------------------------------------------------------

def node_upsert_lead_in_db(lead: Dict[str, Any], db_session) -> Dict[str, Any]:
    """
    n8n node: "Upsert Lead in DB"
    Type: postgres (executeQuery)

    SQL (verbatim from n8n):
        INSERT INTO leads (name, email, linkedin_url, company, role, headline, about, work_description, status)
        VALUES (...)
        ON CONFLICT (linkedin_url) DO UPDATE SET name=EXCLUDED.name, email=EXCLUDED.email,
          company=EXCLUDED.company, role=EXCLUDED.role, status='SENT'
        RETURNING id;

    Uses the passed SQLAlchemy session (raw SQL) so we don't depend on ORM internals.
    Returns dict with 'id' key.
    """
    from sqlalchemy import text

    sql = text("""
        INSERT INTO leads (name, email, linkedin_url, company, role, headline, about, work_description, status)
        VALUES (:name, :email, :linkedin_url, :company, :role, :headline, :about, :work_description, 'SENT')
        ON CONFLICT (linkedin_url) DO UPDATE SET
            name = EXCLUDED.name,
            email = EXCLUDED.email,
            company = EXCLUDED.company,
            role = EXCLUDED.role,
            status = 'SENT'
        RETURNING id;
    """)

    params = {
        "name": (lead.get("name") or "")[:255],
        "email": (lead.get("email") or "")[:255],
        "linkedin_url": (lead.get("url") or lead.get("linkedin_url") or "")[:500],
        "company": (lead.get("company") or "")[:255],
        "role": (lead.get("role") or "")[:255],
        "headline": (lead.get("headline") or "")[:500],
        "about": (lead.get("about") or "")[:500],
        "work_description": (lead.get("work_description") or "")[:500],
    }

    result = db_session.execute(sql, params)
    db_session.commit()
    row = result.fetchone()
    return {"id": row[0] if row else None}


# ---------------------------------------------------------------------------
# Node 9: Get Lead ID from DB
# ---------------------------------------------------------------------------

def node_get_lead_id_from_db(
    email_tracking_data: Dict[str, Any],
    lead_data: Dict[str, Any],
    db_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    n8n node: "Get Lead ID from DB"
    Type: Code (JavaScript → Python)

    Merges email tracking + lead data and extracts the lead_id from the DB result.
    """
    lead_id = db_result.get("id") or (
        (db_result.get("rows") or [{}])[0].get("id")
    )
    return {**email_tracking_data, "lead_id": lead_id}


# ---------------------------------------------------------------------------
# Node 10: Insert Email Sequence Row
# ---------------------------------------------------------------------------

def node_insert_email_sequence_row(data: Dict[str, Any], db_session) -> Dict[str, Any]:
    """
    n8n node: "Insert Email Sequence Row"
    Type: postgres (executeQuery)

    SQL (verbatim from n8n):
        INSERT INTO email_sequences (lead_id, step_number, tracking_id, status)
        VALUES (lead_id, step_number, tracking_id, 'sent')
        RETURNING tracking_id;
    """
    from sqlalchemy import text

    sql = text("""
        INSERT INTO email_sequences (lead_id, step_number, tracking_id, status)
        VALUES (:lead_id, :step_number, :tracking_id, 'sent')
        RETURNING tracking_id;
    """)
    params = {
        "lead_id": data["lead_id"],
        "step_number": data.get("step_number", 1),
        "tracking_id": data["tracking_id"],
    }
    result = db_session.execute(sql, params)
    db_session.commit()
    row = result.fetchone()
    return {**data, "db_tracking_id": row[0] if row else data["tracking_id"]}


# ---------------------------------------------------------------------------
# Node 11: Code in JavaScript (merge for send)
# ---------------------------------------------------------------------------

def node_code_in_javascript(
    email_tracking_data: Dict[str, Any],
    lead_data: Dict[str, Any],
    insert_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    n8n node: "Code in JavaScript"
    Type: Code (JavaScript → Python)

    Merges email tracking data, lead data, and insert result into a single dict
    ready to pass to the Gmail send node.
    """
    return {**email_tracking_data, **lead_data, **insert_data}


# ---------------------------------------------------------------------------
# Node 12: Send Email via Gmail
# ---------------------------------------------------------------------------

def node_send_email_via_gmail(
    data: Dict[str, Any],
    gmail_service,
) -> None:
    """
    n8n node: "Send Email via Gmail"
    Type: gmail (send)

    sendTo   : data["email"]
    subject  : data["email_subject"]
    message  : data["email_body_html"]

    Expects a google-api-python-client Gmail service object.
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["To"] = data["email"]
    msg["Subject"] = data["email_subject"]
    msg.attach(MIMEText(data["email_body_html"], "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info("Email sent to %s (tracking: %s)", data["email"], data.get("tracking_id"))


# ---------------------------------------------------------------------------
# Node 13: Call Backend /sent Endpoint
# ---------------------------------------------------------------------------

def node_call_backend_sent_endpoint(data: Dict[str, Any]) -> None:
    """
    n8n node: "Call Backend /sent Endpoint"
    Type: httpRequest (POST)
    URL:  http://127.0.0.1:8000/api/tracking/sent/<tracking_id>?step=<step_number>
    """
    tracking_id = data.get("tracking_id")
    step = data.get("step_number", 1)
    
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
        logger.info("Called /sent for tracking_id=%s step=%s", tracking_id, step)
    except requests.RequestException as exc:
        logger.warning("Failed to call /sent endpoint: %s", exc)


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def run_workflow2(
    lead: Dict[str, Any],
    gemini_api_key: str,
    gmail_service,
    db_session,
    is_existing_lead: bool = False,
) -> None:
    """
    Full Workflow 2 execution pipeline for a single lead (one loop iteration).

    Args:
        lead:             A single lead/profile dict from workflow1 output.
        gemini_api_key:   Google Gemini API key (replaces n8n credential).
        gmail_service:    Authenticated google-api-python-client Gmail service.
        db_session:       SQLAlchemy session bound to the Postgres database.
        is_existing_lead: If True, uses the activity-summary path instead of new-lead path.
    """
    logger.info("Processing lead: %s <%s>", lead.get("name"), lead.get("email"))

    # ---- Step 1: Build AI summary ------------------------------------------
    if is_existing_lead:
        enriched = node_build_activity_summary(lead)
        gemini_item = node_message_a_model(enriched, gemini_api_key)
    else:
        enriched = node_build_ai_summary(lead)
        gemini_item = node_ai_generate_personalized_email(enriched, gemini_api_key)

    # ---- Step 2: Prepare email with tracking --------------------------------
    email_data = node_prepare_email_with_tracking(gemini_item)

    # ---- Step 3: Upsert lead in DB ------------------------------------------
    db_result = node_upsert_lead_in_db(lead, db_session)

    # ---- Step 4: Get lead ID ------------------------------------------------
    merged = node_get_lead_id_from_db(email_data, enriched, db_result)

    # ---- Step 5: Insert email sequence row ----------------------------------
    merged = node_insert_email_sequence_row(merged, db_session)

    # ---- Step 6: Merge for send (Code in JavaScript) -----------------------
    send_data = node_code_in_javascript(email_data, enriched, merged)

    # ---- Step 7: Send email -------------------------------------------------
    node_send_email_via_gmail(send_data, gmail_service)

    # ---- Step 8: Call /sent endpoint ----------------------------------------
    node_call_backend_sent_endpoint(send_data)

    logger.info("Workflow 2 complete for lead: %s", lead.get("email"))
