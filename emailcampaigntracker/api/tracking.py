from fastapi import APIRouter, Request, Response
from fastapi.responses import Response, RedirectResponse
from database.db import get_db_conn
import datetime
import json
import threading

router = APIRouter(tags=["Tracking"])

# 1x1 transparent pixel GIF
PIXEL_GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
# 1x1 transparent pixel PNG
PIXEL_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

# Map event types to lead statuses
EVENT_TO_STATUS = {
    "sent": "SENT",
    "open": "OPENED",
    "click": "CLICKED",
    "reply": "REPLIED",
    "delete": "DELETED",
}

def normalize_url(url):
    if not url:
        return url
    return (
        url.strip().lower()
        .replace("https://nl.linkedin.com", "https://www.linkedin.com")
        .replace("http://", "https://")
        .rstrip("/")
    )
    
def sync_sheet_status_async(linkedin_url, status, open_count=None):
    """Sync a single lead's status to Google Sheet in background thread."""
    try:
        from google_sheets import sync_leads_status
        payload = {
            "linkedin_url": normalize_url(linkedin_url),
            "status": status
        }
        if open_count is not None:
            payload["open_count"] = open_count
        for _ in range(3):
            try:
                sync_leads_status([payload])
                break
            except Exception as e:
                print("Retrying sheet sync...", e)
        print(f"   -> Sheet synced: {linkedin_url} = {status} (Opens: {open_count})")
    except Exception as e:
        print(f"   -> Sheet sync failed: {e}")

def log_event(tracking_id, event_type, request=None, additional_metadata=None):
    """Universal helper to log events to the database."""
    ip_address = request.client.host if request else "Unknown"
    user_agent = request.headers.get("user-agent", "Unknown") if request else "Unknown"
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # 1. Get lead + sequence
            print(f"DEBUG: Logging {event_type} for ID: {tracking_id}")
            cur.execute(
                "SELECT id, lead_id FROM email_sequences WHERE tracking_id = %s",
                (tracking_id,)
            )
            res = cur.fetchone()
            if not res:
                print(f"DEBUG: Tracking ID {tracking_id} NOT FOUND in database.")
                return False
            
            seq_id, lead_id = res
            now = datetime.datetime.now()
            
            # 2. Build metadata
            meta = {
                "ip": ip_address,
                "user_agent": user_agent,
                "sequence_id": seq_id
            }
            if additional_metadata:
                meta.update(additional_metadata)

            # 🚨 3. PREVENT DUPLICATE OPENS (BEFORE INSERT)
            if event_type == "open":
                cur.execute(
                    "SELECT 1 FROM events WHERE lead_id = %s AND event_type = 'open' LIMIT 1",
                    (lead_id,)
                )
                if cur.fetchone():
                    print("⚠️ Duplicate open ignored")
                    return True

            # ✅ HANDLE SENT EVENT (ADD THIS)
            if event_type == "sent":
                print(f"DEBUG: Marking email as SENT for tracking_id: {tracking_id}")

                # update sent_at in sequence
                cur.execute(
                    "UPDATE email_sequences SET sent_at = %s WHERE id = %s",
        (now, seq_id)
    )

            # ✅ 4. INSERT EVENT (ONLY ONCE)
            cur.execute(
                "INSERT INTO events (lead_id, event_type, timestamp, metadata) VALUES (%s, %s, %s, %s)",
                (lead_id, event_type, now, json.dumps(meta))
            )

            # ✅ 5. UPDATE SEQUENCE TABLE
            if event_type == "open":
                cur.execute(
                    "UPDATE email_sequences SET opened_at = %s WHERE id = %s AND opened_at IS NULL",
                    (now, seq_id)
                )

            elif event_type == "reply":
                cur.execute(
                    "UPDATE email_sequences SET replied = TRUE WHERE id = %s",
                    (seq_id,)
                )

            # ✅ 6. UPDATE LEAD STATUS
            new_status = EVENT_TO_STATUS.get(event_type)
            if event_type == "sent":
                new_status = "SENT"

            if new_status:
                cur.execute(
                    "UPDATE leads SET status = %s WHERE id = %s",
                    (new_status, lead_id)
                )

            # ✅ 7. GET LINKEDIN URL
            cur.execute("SELECT linkedin_url FROM leads WHERE id = %s", (lead_id,))
            url_res = cur.fetchone()
            linkedin_url = url_res[0] if url_res else None

            # ✅ 8. COUNT OPENS
            cur.execute(
                "SELECT COUNT(*) FROM events WHERE lead_id = %s AND event_type = 'open'",
                (lead_id,)
            )
            open_count = cur.fetchone()[0]

            conn.commit()

            if linkedin_url:
                print(f"DEBUG: Syncing sheet → {linkedin_url} | Status: {new_status} | Opens: {open_count}")

                threading.Thread(
                    target=sync_sheet_status_async,
                    args=(linkedin_url, new_status, open_count),
                    daemon=True
                ).start()

            return True


@router.get("/t/o/{tracking_id}")
@router.get("/open/{tracking_id}")
@router.get("/img/logo_{tracking_id}.png")
@router.get("/pixel/{tracking_id}.gif")
async def track_open(tracking_id: str, request: Request):
    """Logs an 'open' event when the pixel is loaded (with shorthand support)."""
    # Remove any file extensions if they were passed in the URL
    tracking_id = tracking_id.replace(".png", "").replace(".gif", "").replace("logo_", "")
    
    user_agent = request.headers.get("user-agent", "Unknown")
    is_gmail = "GoogleImageProxy" in user_agent
    
    print("\n" + "="*50)
    print(f"STEALTH PIXEL DETECTED!")
    print(f"ID: {tracking_id}")
    if is_gmail:
        print(">>> GMAIL PROXY DETECTED! <<<")
    print("="*50 + "\n")
    
    if not is_gmail:
        log_event(tracking_id, "open", request)
    else:
        print("⚠️ Skipping Gmail auto-open")    
    # Ultra-Hardened Headers for Gmail Proxy
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "ngrok-skip-browser-warning": "1",
        "X-Content-Type-Options": "nosniff"
    }

    if is_gmail:
        # For Gmail, return a REAL PNG DIRECTLY
        return Response(content=PIXEL_PNG, media_type="image/png", headers=headers)
    
    # For others, return the GIF
    return Response(content=PIXEL_GIF, media_type="image/gif", headers=headers)

@router.get("/click/{tracking_id}")
async def track_click(tracking_id: str, url: str, request: Request):
    """Logs a 'click' event and redirects the user."""
    log_event(tracking_id, "click", request, {"target_url": url})
    return RedirectResponse(url=url)

@router.post("/reply/{tracking_id}")
async def track_reply(tracking_id: str, request: Request):
    """Logs a 'reply' event (can be triggered by webhook or manual action)."""
    if log_event(tracking_id, "reply", request):
        return {"status": "success", "message": "Reply tracked"}
    return {"status": "error", "message": "Tracking ID not found"}

@router.post("/delete/{tracking_id}")
async def track_delete(tracking_id: str, request: Request):
    """Logs a 'delete' event."""
    if log_event(tracking_id, "delete", request):
        return {"status": "success", "message": "Deletion tracked"}
    return {"status": "error", "message": "Tracking ID not found"}

@router.post("/sent/{tracking_id}")
@router.get("/sent/{tracking_id}")
async def track_sent(tracking_id: str, step: int = 1):
    """Logs each time an email is sent (initial or follow-up)."""
    # Custom metadata to track which step in the drip it was
    if log_event(tracking_id, "sent", additional_metadata={"step": step}):
        # Also update the main sequence table with the latest send time
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE email_sequences SET sent_at = %s, step_number = %s WHERE tracking_id = %s",
                    (datetime.datetime.now(), step, tracking_id)
                )
                conn.commit()
        return {"status": "success", "message": f"Email Step {step} logged"}
    return {"status": "error", "message": "Tracking ID not found"}
