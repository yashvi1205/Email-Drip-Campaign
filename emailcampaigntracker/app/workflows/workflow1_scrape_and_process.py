"""
Workflow 1 - Profile Scraping & Lead Processing
================================================
Converted from n8n workflow: "AI Drip Campaign - Full System"

n8n nodes covered (in execution order):
  1. Start Scrapping Profiles       (Manual Trigger)
  2. Scrape LinkedIn Profiles       (HTTP POST → /api/scrape)
  3. Webhook                        (receives POST from scraper callback)
  4. Split Into Individual Profiles (splitOut on body.data)
  5. Read Emails from Google Sheet  (Google Sheets read)
  6. Fill Missing Emails from Sheet (JS Code → Python)
  7. Fetch Existing Leads from DB   (HTTP GET → /api/leads)
  8. Deduplicate Against DB         (JS Code → Python)
  9. Is New Lead?                   (IF condition → boolean branch)

The function `run_workflow1` is the main entry-point.
It returns a tuple:
  - new_leads:      list of dicts that are brand-new (is_new_lead=True)
  - existing_leads: list of dicts that are already in DB (is_new_lead=False)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

import requests

logger = logging.getLogger("workflow1")

# ---------------------------------------------------------------------------
# Configuration (mirror what the n8n nodes hard-code)
# ---------------------------------------------------------------------------
BACKEND_URL = "http://127.0.0.1:8000"
SCRAPER_API_KEY = "scraper-key-789"
WEBHOOK_URL = f"{BACKEND_URL}/webhook/3aeb822a-2673-401f-9882-ff3dfe88db65"


# ---------------------------------------------------------------------------
# Node 1 & 2: Start Scraping Profiles
# ---------------------------------------------------------------------------

def node_scrape_linkedin_profiles(webhook_url: str = WEBHOOK_URL) -> Dict[str, Any]:
    """
    n8n node: "Scrape LinkedIn Profiles"
    Type: httpRequest (POST)
    URL:  http://127.0.0.1:8000/api/scrape?webhook_url=<webhook_url>
    Header: X-API-Key: scraper-key-789

    Triggers the scraper and returns the raw HTTP response body.
    The actual profile data arrives later via the webhook callback.
    """
    url = f"{BACKEND_URL}/api/scrape?webhook_url={webhook_url}"
    headers = {"X-API-Key": SCRAPER_API_KEY}
    logger.info("Scraping LinkedIn profiles via backend …")
    resp = requests.post(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Node 3 (Webhook) + Node 4: Split Into Individual Profiles
# ---------------------------------------------------------------------------

def node_split_into_individual_profiles(webhook_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    n8n node: "Split Into Individual Profiles"
    Type: splitOut on field "body.data"

    Receives the webhook POST payload from the scraper callback and returns
    the flat list of individual profile dicts.
    """
    if not webhook_payload:
        data = []
    elif "body" in webhook_payload and isinstance(webhook_payload["body"], dict):
        data = webhook_payload["body"].get("data", [])
    else:
        data = webhook_payload.get("data", [])
    
    if not data and isinstance(webhook_payload, list):
        data = webhook_payload

    if not isinstance(data, list):
        data = [data]
    logger.info("Split %d profiles from webhook payload.", len(data))
    return data


# ---------------------------------------------------------------------------
# Node 5: Read Emails from Google Sheet
# ---------------------------------------------------------------------------

def node_read_emails_from_google_sheet(gsheets_client=None) -> List[Dict[str, Any]]:
    """
    n8n node: "Read Emails from Google Sheet"
    Type: googleSheets (getAll)
    Sheet: LinkedIn_Profile_DataScraper → sheet "Profiles"
    Document ID: 1H68sixKlA1kiqiKc1yv4kapV2UQYEPNz9Pjj5VQwguo

    Returns list of row dicts from the Google Sheet.
    Pass a gspread-compatible client or leave None to use the app integration.
    """
    if gsheets_client is None:
        # Use the existing app integration
        from app.integrations.google_sheets import get_profile_urls  # noqa: F401
        # The integration already wraps gspread; here we open the sheet directly.
        import gspread
        import os
        from app.integrations.google_sheets import client
        if not client:
            logger.warning("Google Sheets client is not initialized; returning empty list.")
            return []
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id:
            logger.error("GOOGLE_SHEET_ID env var not set — cannot read emails from sheet.")
            return []
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet("Profiles")
        rows = ws.get_all_records()
        return rows

    # If a client is supplied directly
    import os
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        logger.error("GOOGLE_SHEET_ID env var not set — cannot read emails from sheet.")
        return []
    sh = gsheets_client.open_by_key(sheet_id)
    ws = sh.worksheet("Profiles")
    return ws.get_all_records()


# ---------------------------------------------------------------------------
# Node 6: Fill Missing Emails from Sheet  (JS → Python)
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """
    Mirror the JS normalizeUrl() helper from the n8n Code node.
    Strips protocol / www / locale subdomain / trailing slash / query string.
    """
    if not url:
        return ""
    url = url.lower()
    url = url.replace("https://", "").replace("http://", "").replace("www.", "")
    url = re.sub(r"[a-z]{2}\.linkedin\.com", "linkedin.com", url)
    url = url.split("?")[0].rstrip("/").strip()
    return url


def node_fill_missing_emails_from_sheet(
    profiles: List[Dict[str, Any]],
    sheet_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    n8n node: "Fill Missing Emails from Sheet"
    Type: Code (JavaScript → Python)

    For every profile that has no valid email, looks up the email from the
    Google Sheet using the LinkedIn profile URL as the join key.
    """
    # Build url→email map from sheet rows
    email_map: Dict[str, str] = {}
    for row in sheet_rows:
        url_key = next(
            (k for k in row if "profile" in k.lower() and "url" in k.lower()), None
        )
        email_key = next(
            (k for k in row if "email" in k.lower()), None
        )
        url = _normalize_url(row.get(url_key, "") if url_key else "")
        email = (row.get(email_key, "") if email_key else "").strip()
        if url and email and "@" in email:
            email_map[url] = email

    results: List[Dict[str, Any]] = []
    for p in profiles:
        p = dict(p)
        current_url = _normalize_url(p.get("url") or p.get("linkedin_url") or "")
        email = (p.get("email") or "").lower()
        if not email or "restricted" in email or "@" not in email:
            sheet_email = email_map.get(current_url)
            if sheet_email:
                p["email"] = sheet_email
                p["email_source"] = "google_sheet"
        results.append(p)

    logger.info("Filled emails: %d profiles processed.", len(results))
    return results


# ---------------------------------------------------------------------------
# Node 7: Fetch Existing Leads from DB
# ---------------------------------------------------------------------------

def node_fetch_existing_leads_from_db() -> List[Dict[str, Any]]:
    """
    n8n node: "Fetch Existing Leads from DB"
    Type: httpRequest (GET)
    URL:  http://127.0.0.1:8000/api/leads

    Returns the list of existing lead dicts from the backend API.
    """
    resp = requests.get(f"{BACKEND_URL}/api/leads", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # API may return {"leads": [...]} or plain list
    if isinstance(data, list):
        return data
    return data.get("leads", data.get("data", []))


# ---------------------------------------------------------------------------
# Node 8: Deduplicate Against DB  (JS → Python)
# ---------------------------------------------------------------------------

def node_deduplicate_against_db(
    profiles: List[Dict[str, Any]],
    existing_leads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    n8n node: "Deduplicate Against DB"
    Type: Code (JavaScript → Python)

    Rules:
    - Skip profiles with no valid email.
    - If NOT emailed yet (either not in DB or in DB but status is 'active') → mark is_new_lead=True and include.
    - If emailed (status is SENT, OPENED, etc.) and is_new_lead is explicitly False → include (existing lead update path).
    - If emailed and is_new_lead is True or not set → skip (already processed).
    """
    emailed_urls = {
        (lead.get("linkedin_url") or "").lower()
        for lead in existing_leads
        if (lead.get("status") or "").upper() not in {"ACTIVE", "UNCONTACTED"}
    }

    results: List[Dict[str, Any]] = []
    for p in profiles:
        p = dict(p)
        url = (p.get("url") or p.get("linkedin_url") or "").lower()
        email = (p.get("email") or "").lower()

        # Must have a valid email
        if not email or "@" not in email or "restricted" in email:
            continue

        already_emailed = url in emailed_urls

        if not already_emailed:
            p["is_new_lead"] = True
            results.append(p)
        elif already_emailed and p.get("is_new_lead") is False:
            results.append(p)

    logger.info("Dedup: %d profiles ready for processing.", len(results))
    return results


# ---------------------------------------------------------------------------
# Node 9: Is New Lead? (IF condition)
# ---------------------------------------------------------------------------

def node_is_new_lead(
    profiles: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    n8n node: "Is New Lead?"
    Type: IF (boolean condition on $json.is_new_lead === true)

    Returns:
        (new_leads, existing_leads)
        - new_leads    → True branch  → goes to "Loop Over Items" → Build AI Summary
        - existing_leads → False branch → goes to "Build Activity Summary"
    """
    new_leads: List[Dict[str, Any]] = []
    existing_leads: List[Dict[str, Any]] = []

    for p in profiles:
        if p.get("is_new_lead") is True:
            new_leads.append(p)
        else:
            existing_leads.append(p)

    logger.info(
        "Is New Lead split: %d new, %d existing.", len(new_leads), len(existing_leads)
    )
    return new_leads, existing_leads


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def run_workflow1(
    webhook_payload: Dict[str, Any],
    gsheets_client=None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Full Workflow 1 execution pipeline.

    Args:
        webhook_payload: The JSON body received on the n8n webhook endpoint
                         (from the scraper callback). Shape: {"body": {"data": [...]}}
        gsheets_client:  Optional gspread client; if None the app integration is used.

    Returns:
        (new_leads, existing_leads)
    """
    # Step 1: Split profiles from webhook body
    profiles = node_split_into_individual_profiles(webhook_payload)

    # Step 2: Read emails from Google Sheet
    sheet_rows = node_read_emails_from_google_sheet(gsheets_client)

    # Step 3: Fill missing emails
    profiles = node_fill_missing_emails_from_sheet(profiles, sheet_rows)

    # Step 4: Fetch existing leads from DB
    existing_leads_db = node_fetch_existing_leads_from_db()

    # Step 5: Deduplicate
    profiles = node_deduplicate_against_db(profiles, existing_leads_db)

    # Step 6: Branch on is_new_lead
    new_leads, existing_leads = node_is_new_lead(profiles)

    return new_leads, existing_leads
