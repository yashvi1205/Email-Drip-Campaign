from fastapi import APIRouter, Request, Response
from fastapi.responses import Response, RedirectResponse
from database.db import get_db_conn
import datetime
import json

router = APIRouter(tags=["Tracking"])

# 1x1 transparent pixel GIF
PIXEL_GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"

def log_event(tracking_id, event_type, request=None, additional_metadata=None):
    """Universal helper to log events to the database."""
    ip_address = request.client.host if request else "Unknown"
    user_agent = request.headers.get("user-agent", "Unknown") if request else "Unknown"
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # 1. Get lead information
            cur.execute(
                "SELECT id, lead_id FROM email_sequences WHERE tracking_id = %s",
                (tracking_id,)
            )
            res = cur.fetchone()
            if not res:
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
            
            # 3. Log to Events Table (Primary History)
            cur.execute(
                "INSERT INTO events (lead_id, event_type, timestamp, metadata) VALUES (%s, %s, %s, %s)",
                (lead_id, event_type, now, json.dumps(meta))
            )
            
            # 4. Sync Status back to Sequence (For Fast Dashboard)
            if event_type == "open":
                cur.execute("UPDATE email_sequences SET opened_at = %s WHERE id = %s AND opened_at IS NULL", (now, seq_id))
            elif event_type == "reply":
                cur.execute("UPDATE email_sequences SET replied = TRUE WHERE id = %s", (seq_id,))
            
            conn.commit()
            return True

@router.get("/open/{tracking_id}")
async def track_open(tracking_id: str, request: Request):
    """Logs an 'open' event when the pixel is loaded."""
    log_event(tracking_id, "open", request)
    return Response(content=PIXEL_GIF, media_type="image/gif")

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
