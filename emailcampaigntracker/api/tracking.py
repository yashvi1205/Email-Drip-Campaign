from fastapi import APIRouter, Request, Response
from fastapi.responses import Response, RedirectResponse
from database.db import get_db_conn
import datetime
import json
import threading
import os
import httpx
import asyncio
from google_sheets import sync_sheet_status_async

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
    
def sync_sheet_status_async(sync_data):
    """Sync lead tracking data to Google Sheet in background thread."""
    try:
        from google_sheets import sync_leads_status
        # Ensure URL is normalized
        if "linkedin_url" in sync_data:
            sync_data["linkedin_url"] = normalize_url(sync_data["linkedin_url"])
            
        for _ in range(3):
            try:
                sync_leads_status([sync_data])
                break
            except Exception as e:
                print("Retrying sheet sync...", e)
        print(f"   -> Sheet synced: {sync_data.get('linkedin_url')} = {sync_data.get('status')}")
    except Exception as e:
        print(f"   -> Sheet sync failed: {e}")

def log_event(tracking_id, event_type, request=None, additional_metadata=None):
    tracking_id = tracking_id.strip()
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
                print("TRACKING NOT FOUND:", tracking_id)
                return False
            
            seq_id = res['id']
            lead_id = res['lead_id']
            now = datetime.datetime.now()
            
            # 2. Build metadata
            meta = {
                "ip": ip_address,
                "user_agent": user_agent,
                "sequence_id": seq_id
            }
            if additional_metadata:
                meta.update(additional_metadata)

            # 3. Handle Events (INCREMENT, DON'T OVERWRITE)
            if event_type == "sent":
                cur.execute("UPDATE email_sequences SET sent_at = %s WHERE id = %s", (now, seq_id))

            elif event_type == "open":
                # 🚫 Prevent rapid duplicate opens (within 10 seconds)
                cur.execute("""
                    SELECT timestamp FROM events 
                    WHERE lead_id = %s AND event_type = 'open'
                    ORDER BY timestamp DESC LIMIT 1
                """, (lead_id,))
                last = cur.fetchone()
                if last and (now - last['timestamp']).seconds < 10:
                    print("⚠️ Duplicate open ignored")
                    return True
                
                cur.execute("""
                    UPDATE email_sequences 
                    SET open_count = COALESCE(open_count, 0) + 1, last_opened = %s 
                    WHERE id = %s
                """, (now, seq_id))

            elif event_type == "click":
                cur.execute("""
                    UPDATE email_sequences 
                    SET click_count = COALESCE(click_count, 0) + 1, last_clicked = %s 
                    WHERE id = %s
                """, (now, seq_id))

            elif event_type == "reply":
                cur.execute("""
                    UPDATE email_sequences 
                    SET replied = TRUE, last_replied = %s 
                    WHERE id = %s
                """, (now, seq_id))

            # 4. INSERT INTO EVENTS LOG
            cur.execute(
                "INSERT INTO events (lead_id, event_type, timestamp, metadata) VALUES (%s, %s, %s, %s)",
                (lead_id, event_type, now, json.dumps(meta))
            )

            # 5. DERIVE FINAL STATUS (OPTION B: LATEST ACTION)
            cur.execute("""
                SELECT sent_at, last_opened, last_clicked, last_replied, open_count, click_count, replied 
                FROM email_sequences WHERE id = %s
            """, (seq_id,))
            seq_data = cur.fetchone()

            # Identify all events and their timestamps
            # We use datetime.min for any event that hasn't happened yet
            events = [
                (seq_data['sent_at'] or datetime.datetime.min, "SENT"),
                (seq_data['last_opened'] or datetime.datetime.min, "OPENED"),
                (seq_data['last_clicked'] or datetime.datetime.min, "CLICKED"),
                (seq_data['last_replied'] or datetime.datetime.min, "REPLIED")
            ]
            
            # Sort by timestamp (descending) to find the most recent one
            events.sort(key=lambda x: x[0], reverse=True)
            final_status = events[0][1]

            # 6. UPDATE LEAD TABLE
            cur.execute("UPDATE leads SET status = %s WHERE id = %s", (final_status, lead_id))

            # 7. FETCH LEAD INFO FOR SYNC
            cur.execute("SELECT linkedin_url, email FROM leads WHERE id = %s", (lead_id,))
            lead_info = cur.fetchone()
            
            conn.commit()

            if lead_info:
                sync_data = {
                    "linkedin_url": lead_info['linkedin_url'],
                    "email": lead_info['email'],
                    "status": final_status,
                    "open_count": seq_data['open_count'],
                    "last_opened": seq_data['last_opened'],
                    "click_count": seq_data['click_count'],
                    "last_clicked": seq_data['last_clicked'],
                    "replied": seq_data['replied'],
                    "last_replied": seq_data['last_replied']
                }
                threading.Thread(
                    target=sync_sheet_status_async,
                    args=(sync_data,),
                    daemon=True
                ).start()

            return True


@router.get("/track/{tracking_id}")
@router.get("/t/o/{tracking_id}")
@router.get("/open/{tracking_id}")
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
    
    # 🚫 Ignore Gmail proxy + bots
    ua = request.headers.get("user-agent", "").lower()
    is_gmail_proxy = "googleimageproxy" in ua
    is_bot = "bot" in ua or "crawler" in ua

    print(f"USER AGENT: {ua}")

    # ✅ Allow real opens but block obvious proxies
    if is_gmail_proxy:
        print("⚠️ Gmail proxy ignored")
    else:
        log_event(tracking_id, "open", request)
    
    # FORWARDING: Only forward if we are on Render
    local_url = os.getenv("LOCAL_BACKEND_URL")
    if os.getenv("RENDER") and local_url:
        async def forward():
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(f"{local_url}/api/tracking/open/{tracking_id}", timeout=1.0)
            except: pass
        asyncio.create_task(forward())

    # Ultra-Hardened Headers for Gmail Proxy
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "ngrok-skip-browser-warning": "1",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline; filename=logo.png"
    }

    return Response(content=PIXEL_GIF, media_type="image/gif", headers=headers)
    
@router.get("/click/{tracking_id}")
async def track_click(tracking_id: str, url: str, request: Request):
    """Logs a 'click' event and redirects the user."""
    log_event(tracking_id, "click", request, {"target_url": url})
    
    # FORWARDING: Only forward if we are on Render
    local_url = os.getenv("LOCAL_BACKEND_URL")
    if os.getenv("RENDER") and local_url:
        async def forward():
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(f"{local_url}/api/tracking/click/{tracking_id}?url={url}", timeout=1.0)
            except: pass
        asyncio.create_task(forward())
        
    return RedirectResponse(url=url)

@router.post("/reply/{tracking_id}")
async def track_reply(tracking_id: str, request: Request):
    """Logs a 'reply' event (can be triggered by webhook or manual action)."""
    log_event(tracking_id, "reply", request)
    
    # FORWARDING: Only forward if we are on Render
    local_url = os.getenv("LOCAL_BACKEND_URL")
    if os.getenv("RENDER") and local_url:
        async def forward():
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(f"{local_url}/api/tracking/reply/{tracking_id}", timeout=1.0)
            except: pass
        asyncio.create_task(forward())

    return {"status": "success", "message": "Reply tracked"}

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
    tracking_id = tracking_id.strip()

    # 🔥 DEBUG (temporary - remove later)
    print("DEBUG TRACKING_ID:", tracking_id)
    print("DEBUG STEP:", step)
    
    # Custom metadata to track which step in the drip it was
    if log_event(tracking_id, "sent", additional_metadata={"step": step}):
        # Also update the main sequence table with the latest send time
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE email_sequences SET sent_at = %s, step_number = %s WHERE tracking_id = %s RETURNING id",(datetime.datetime.now(), step, tracking_id))

                updated = cur.fetchone()

                if not updated:
                    print("❌ UPDATE FAILED FOR:", tracking_id)
                conn.commit()
        return {"status": "success", "message": f"Email Step {step} logged"}
    return {"status": "error", "message": "Tracking ID not found"}