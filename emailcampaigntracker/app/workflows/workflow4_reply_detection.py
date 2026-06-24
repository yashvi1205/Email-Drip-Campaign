"""
Workflow 4 - Reply Detection & Tracking
========================================
Converted from n8n workflow: "AI Drip Campaign - Full System"

n8n nodes covered (in execution order):
  1. Gmail Trigger        (gmailTrigger – polls every minute for new emails)
  2. Filter only replies  (IF condition – checks if email body contains a trk_ token)
  3. Extract tracking_id  (Code node – regex extracts trk_... from email body)
  4. Ensure ID exists     (IF condition – skips if tracking_id is empty)
  5. HTTP Request         (POST → /api/tracking/reply/<tracking_id>)

The function `run_workflow4_on_email` is the main entry-point for a single email.
Call it once per new email received from the Gmail polling loop.

For the polling loop itself, see `start_gmail_polling_loop()` which mirrors
the n8n gmailTrigger node (polls every 60 seconds).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("workflow4")

LOCAL_BACKEND_URL = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# Node 2: Filter only replies
# ---------------------------------------------------------------------------

def node_filter_only_replies(email: Dict[str, Any]) -> bool:
    """
    n8n node: "Filter only replies"
    Type: IF (condition)

    Condition (OR):
        ($json.snippet || '').includes('trk_') ||
        ($json.text    || '').includes('trk_') ||
        ($json.html    || '').includes('trk_') ||
        ($json.textAsHtml || '').includes('trk_')

    Returns True if the email is a reply to one of our tracked emails.
    """
    fields = [
        email.get("snippet", ""),
        email.get("text", ""),
        email.get("html", ""),
        email.get("textAsHtml", ""),
    ]
    return any("trk_" in (f or "") for f in fields)


# ---------------------------------------------------------------------------
# Node 3: Extract tracking_id
# ---------------------------------------------------------------------------

def node_extract_tracking_id(email: Dict[str, Any]) -> Optional[str]:
    """
    n8n node: "Extract tracking_id"
    Type: Code (JavaScript → Python)
    Mode: runOnceForEachItem

    Combines all text fields from the email and runs a regex to extract
    the first trk_... token found.

    Returns the tracking_id string or None if not found.
    """
    snippet = email.get("snippet", "")
    text = email.get("text", "")
    html = email.get("html", "")
    text_as_html = email.get("textAsHtml", "")

    full_text = f"\n{snippet}\n{text}\n{html}\n{text_as_html}\n"

    match = re.search(r"(trk_[a-zA-Z0-9_]+)", full_text)
    tracking_id = match.group(1) if match else None
    logger.debug("Extracted tracking_id: %s", tracking_id)
    return tracking_id


# ---------------------------------------------------------------------------
# Node 4: Ensure ID exists
# ---------------------------------------------------------------------------

def node_ensure_id_exists(tracking_id: Optional[str]) -> bool:
    """
    n8n node: "Ensure ID exists"
    Type: IF (condition)

    Condition: $json.tracking_id is not empty (string, notEmpty)

    Returns True if the tracking_id is a non-empty string.
    """
    return bool(tracking_id and tracking_id.strip())


# ---------------------------------------------------------------------------
# Node 5: HTTP Request → /api/tracking/reply/<tracking_id>
# ---------------------------------------------------------------------------

def node_http_request_reply(tracking_id: str) -> None:
    """
    n8n node: "HTTP Request"
    Type: httpRequest (POST)
    URL:  http://127.0.0.1:8000/api/tracking/reply/<tracking_id>

    Notifies the backend that this tracking_id received a reply.
    """
    url = f"{LOCAL_BACKEND_URL}/api/tracking/reply/{tracking_id}"
    try:
        resp = requests.post(url, timeout=10)
        resp.raise_for_status()
        logger.info("Marked reply for tracking_id=%s", tracking_id)
    except requests.RequestException as exc:
        logger.error("Failed to call /reply endpoint for %s: %s", tracking_id, exc)


# ---------------------------------------------------------------------------
# Single-email entry-point
# ---------------------------------------------------------------------------

def run_workflow4_on_email(email: Dict[str, Any]) -> None:
    """
    Full Workflow 4 pipeline for a single Gmail message dict.

    The email dict should have the fields that the n8n gmailTrigger exposes:
        snippet, text, html, textAsHtml  (all optional strings)

    Steps:
        1. Filter only replies (contains trk_ token)
        2. Extract tracking_id from body
        3. Ensure ID is non-empty
        4. POST to /api/tracking/reply/<tracking_id>
    """
    # ---- Node 2: Filter only replies ---------------------------------------
    if not node_filter_only_replies(email):
        logger.debug("Email is not a reply to a tracked email; skipping.")
        return

    # ---- Node 3: Extract tracking_id --------------------------------------
    tracking_id = node_extract_tracking_id(email)

    # ---- Node 4: Ensure ID exists -----------------------------------------
    if not node_ensure_id_exists(tracking_id):
        logger.debug("No valid tracking_id found in email; skipping.")
        return

    # ---- Node 5: Call /reply endpoint -------------------------------------
    node_http_request_reply(tracking_id)


# ---------------------------------------------------------------------------
# Gmail polling loop (mirrors gmailTrigger – everyMinute)
# ---------------------------------------------------------------------------

def start_gmail_polling_loop(
    gmail_service,
    poll_interval_seconds: int = 60,
    history_id_store: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Mirrors the n8n gmailTrigger node (pollTimes: everyMinute, simple: false).

    Continuously polls Gmail for new messages and calls `run_workflow4_on_email`
    for each new message. Runs indefinitely; call in a background thread.

    Args:
        gmail_service:         Authenticated google-api-python-client Gmail service.
        poll_interval_seconds: How often to poll (default 60 seconds).
        history_id_store:      Mutable dict with key 'history_id' to persist state
                               across calls. If None, uses list() internally.
    """
    if history_id_store is None:
        history_id_store = {}

    logger.info("Starting Gmail polling loop (interval=%ds) …", poll_interval_seconds)

    # Seed the history_id on first run
    if "history_id" not in history_id_store:
        profile = gmail_service.users().getProfile(userId="me").execute()
        history_id_store["history_id"] = profile.get("historyId")
        logger.info("Seeded Gmail history_id=%s", history_id_store["history_id"])

    while True:
        try:
            _poll_gmail_once(gmail_service, history_id_store)
        except Exception as exc:
            logger.error("Error in Gmail polling loop: %s", exc, exc_info=True)
        time.sleep(poll_interval_seconds)


def _poll_gmail_once(gmail_service, history_id_store: Dict[str, Any]) -> None:
    """
    One iteration of the Gmail poll: fetch new messages since last historyId,
    process each, then update historyId.
    """
    current_history_id = history_id_store.get("history_id")
    if not current_history_id:
        return

    try:
        history_resp = (
            gmail_service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=current_history_id,
                historyTypes=["messageAdded"],
                labelId="INBOX",
            )
            .execute()
        )
    except Exception as exc:
        logger.warning("Gmail history.list failed: %s", exc)
        return

    histories = history_resp.get("history", [])
    new_history_id = history_resp.get("historyId", current_history_id)

    for hist in histories:
        for msg_added in hist.get("messagesAdded", []):
            msg_id = msg_added.get("message", {}).get("id")
            if not msg_id:
                continue
            try:
                full_msg = (
                    gmail_service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                # Build the dict that matches what n8n gmailTrigger exposes
                email_dict = _parse_gmail_message(full_msg)
                run_workflow4_on_email(email_dict)
            except Exception as exc:
                logger.error("Error processing Gmail message %s: %s", msg_id, exc)

    history_id_store["history_id"] = new_history_id


def _parse_gmail_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a raw Gmail API message object into the simplified dict that the
    n8n gmailTrigger node exposes (snippet, text, html, textAsHtml).
    """
    import base64

    snippet = msg.get("snippet", "")
    text = ""
    html = ""

    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    def extract_parts(part_list):
        nonlocal text, html
        for part in part_list:
            mime = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")
            sub_parts = part.get("parts", [])
            if sub_parts:
                extract_parts(sub_parts)
            if body_data:
                decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
                if mime == "text/plain":
                    text = decoded
                elif mime == "text/html":
                    html = decoded

    if parts:
        extract_parts(parts)
    else:
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
            mime = payload.get("mimeType", "")
            if mime == "text/plain":
                text = decoded
            elif mime == "text/html":
                html = decoded

    # textAsHtml is a simplified conversion (n8n does this internally)
    text_as_html = text.replace("\n", "<br>") if text else ""

    return {
        "id": msg.get("id"),
        "snippet": snippet,
        "text": text,
        "html": html,
        "textAsHtml": text_as_html,
    }
