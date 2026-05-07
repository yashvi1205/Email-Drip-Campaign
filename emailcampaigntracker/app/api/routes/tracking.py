import asyncio
import datetime
import json
import logging
import os
import threading

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.tracking_security import validate_tracking_signature
from database.db import get_db

logger = logging.getLogger("tracking")
router = APIRouter(tags=["Tracking"])

PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01"
    b"\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def normalize_url(url):
    if not url:
        return url
    return (
        url.strip()
        .lower()
        .replace("https://nl.linkedin.com", "https://www.linkedin.com")
        .replace("http://", "https://")
        .rstrip("/")
    )


def sync_sheet_status_async(sync_data):
    try:
        from google_sheets import sync_leads_status

        if "linkedin_url" in sync_data:
            sync_data["linkedin_url"] = normalize_url(sync_data["linkedin_url"])
        for _ in range(3):
            try:
                sync_leads_status([sync_data])
                break
            except Exception as e:
                logger.warning("Retrying sheet sync... error=%s", e)
    except Exception:
        logger.exception("Sheet sync failed.")


def log_event(db: Session, tracking_id, event_type, request=None, additional_metadata=None):
    tracking_id = tracking_id.strip()
    ip_address = request.client.host if request else "Unknown"
    user_agent = request.headers.get("user-agent", "Unknown") if request else "Unknown"

    res = db.execute(
        text("SELECT id, lead_id FROM email_sequences WHERE tracking_id = :tracking_id"),
        {"tracking_id": tracking_id},
    ).mappings().first()
    if not res:
        logger.info("Tracking not found tracking_id=%s", tracking_id)
        return False

    seq_id = res["id"]
    lead_id = res["lead_id"]
    now = datetime.datetime.now()
    meta = {"ip": ip_address, "user_agent": user_agent, "sequence_id": seq_id}
    if additional_metadata:
        meta.update(additional_metadata)

    if event_type == "sent":
        db.execute(
            text("UPDATE email_sequences SET sent_at = :sent_at WHERE id = :seq_id"),
            {"sent_at": now, "seq_id": seq_id},
        )
    elif event_type == "open":
        last = db.execute(
            text(
                "SELECT timestamp FROM events WHERE lead_id = :lead_id AND event_type = 'open' "
                "ORDER BY timestamp DESC LIMIT 1"
            ),
            {"lead_id": lead_id},
        ).mappings().first()
        if last and (now - last["timestamp"]).seconds < 10:
            logger.info("Duplicate open ignored tracking_id=%s", tracking_id)
            return True
        db.execute(
            text(
                "UPDATE email_sequences SET open_count = COALESCE(open_count, 0) + 1, "
                "last_opened = :last_opened WHERE id = :seq_id"
            ),
            {"last_opened": now, "seq_id": seq_id},
        )
    elif event_type == "click":
        db.execute(
            text(
                "UPDATE email_sequences SET click_count = COALESCE(click_count, 0) + 1, "
                "last_clicked = :last_clicked WHERE id = :seq_id"
            ),
            {"last_clicked": now, "seq_id": seq_id},
        )
    elif event_type == "reply":
        db.execute(
            text(
                "UPDATE email_sequences SET replied = TRUE, last_replied = :last_replied "
                "WHERE id = :seq_id"
            ),
            {"last_replied": now, "seq_id": seq_id},
        )

    db.execute(
        text(
            "INSERT INTO events (lead_id, event_type, timestamp, metadata) "
            "VALUES (:lead_id, :event_type, :ts, :metadata)"
        ),
        {"lead_id": lead_id, "event_type": event_type, "ts": now, "metadata": json.dumps(meta)},
    )

    seq_data = db.execute(
        text(
            "SELECT sent_at, last_opened, last_clicked, last_replied, open_count, click_count, replied "
            "FROM email_sequences WHERE id = :seq_id"
        ),
        {"seq_id": seq_id},
    ).mappings().one()

    events = [
        (seq_data["sent_at"] or datetime.datetime.min, "SENT"),
        (seq_data["last_opened"] or datetime.datetime.min, "OPENED"),
        (seq_data["last_clicked"] or datetime.datetime.min, "CLICKED"),
        (seq_data["last_replied"] or datetime.datetime.min, "REPLIED"),
    ]
    events.sort(key=lambda x: x[0], reverse=True)
    final_status = events[0][1]

    db.execute(
        text("UPDATE leads SET status = :status WHERE id = :lead_id"),
        {"status": final_status, "lead_id": lead_id},
    )

    lead_info = db.execute(
        text("SELECT linkedin_url, email FROM leads WHERE id = :lead_id"),
        {"lead_id": lead_id},
    ).mappings().first()
    if lead_info:
        sync_data = {
            "linkedin_url": lead_info["linkedin_url"],
            "email": lead_info["email"],
            "status": final_status,
            "open_count": seq_data["open_count"],
            "last_opened": seq_data["last_opened"],
            "click_count": seq_data["click_count"],
            "last_clicked": seq_data["last_clicked"],
            "replied": seq_data["replied"],
            "last_replied": seq_data["last_replied"],
        }
        threading.Thread(target=sync_sheet_status_async, args=(sync_data,), daemon=True).start()
    return True


@router.get("/track/{tracking_id}")
@router.get("/t/o/{tracking_id}")
@router.get("/open/{tracking_id}")
async def track_open(
    tracking_id: str,
    request: Request,
    exp: int | None = Query(default=None),
    sig: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    tracking_id = tracking_id.replace(".png", "").replace(".gif", "").replace("logo_", "")
    validate_tracking_signature(tracking_id, exp, sig)

    ua = request.headers.get("user-agent", "").lower()
    if "googleimageproxy" not in ua:
        log_event(db, tracking_id, "open", request)

    local_url = os.getenv("LOCAL_BACKEND_URL")
    if os.getenv("RENDER") and local_url:
        async def forward():
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(f"{local_url}/api/tracking/open/{tracking_id}", timeout=1.0)
            except Exception:
                logger.debug("Forwarding open event failed", exc_info=True)
        asyncio.create_task(forward())

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "ngrok-skip-browser-warning": "1",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline; filename=logo.png",
    }
    return Response(content=PIXEL_GIF, media_type="image/gif", headers=headers)


@router.get("/click/{tracking_id}")
async def track_click(
    tracking_id: str,
    request: Request,
    url: str = Query(min_length=1),
    exp: int | None = Query(default=None),
    sig: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_tracking_signature(tracking_id, exp, sig)
    log_event(db, tracking_id, "click", request, {"target_url": url})
    return RedirectResponse(url=url)


@router.post("/reply/{tracking_id}")
async def track_reply(
    tracking_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    log_event(db, tracking_id, "reply", request)
    return {"status": "success", "message": "Reply tracked"}


@router.post("/delete/{tracking_id}")
async def track_delete(
    tracking_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if log_event(db, tracking_id, "delete", request):
        return {"status": "success", "message": "Deletion tracked"}
    return {"status": "error", "message": "Tracking ID not found"}


@router.post("/sent/{tracking_id}")
@router.get("/sent/{tracking_id}")
async def track_sent(
    tracking_id: str,
    step: int = Query(default=1, ge=1, le=20),
    db: Session = Depends(get_db),
):
    tracking_id = tracking_id.strip()
    if log_event(db, tracking_id, "sent", additional_metadata={"step": step}):
        updated = db.execute(
            text(
                "UPDATE email_sequences SET sent_at = :sent_at, step_number = :step "
                "WHERE tracking_id = :tracking_id RETURNING id"
            ),
            {"sent_at": datetime.datetime.now(), "step": step, "tracking_id": tracking_id},
        ).first()
        if not updated:
            logger.warning("Sent update failed tracking_id=%s", tracking_id)
        return {"status": "success", "message": f"Email Step {step} logged"}
    return {"status": "error", "message": "Tracking ID not found"}

