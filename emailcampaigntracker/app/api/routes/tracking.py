import asyncio
import datetime
import json
import logging
import os
import threading

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database.models import EmailSequence, Event, Lead

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
        return ""
    url = url.strip().lower()
    # Strip protocol and www for matching purposes
    url = url.replace("https://", "").replace("http://", "").replace("www.", "")
    # Ensure consistent domain
    url = url.replace("nl.linkedin.com", "linkedin.com")
    return url.rstrip("/")


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


def log_event(
    db: Session,
    tracking_id: str,
    event_type: str,
    request: Request | None = None,
    additional_metadata=None,
) -> bool:
    try:
        tracking_id = tracking_id.strip()
        ip_address = "Unknown"
        user_agent = "Unknown"
        
        if request:
            try:
                if request.client:
                    ip_address = request.client.host
                user_agent = request.headers.get("user-agent", "Unknown")
            except: pass

        seq: EmailSequence | None = (
            db.query(EmailSequence).filter(EmailSequence.tracking_id == tracking_id).first()
        )
        if not seq:
            logger.warning("Tracking ID not found: %s", tracking_id)
            return False

        lead_id = seq.lead_id
        now = datetime.datetime.now()
        meta = {"ip": ip_address, "user_agent": user_agent, "sequence_id": seq.id}
        if additional_metadata:
            meta.update(additional_metadata)

        # IDEMPOTENCY CHECK: Prevent rapid duplicate events of same type (within 10 seconds)
        last_event = (
            db.query(Event.timestamp)
            .filter(Event.lead_id == lead_id, Event.event_type == event_type)
            .order_by(Event.timestamp.desc())
            .first()
        )
        if last_event is not None:
            last_event_ts = last_event[0]
            if last_event_ts and (now - last_event_ts).total_seconds() < 10:
                logger.info("Idempotency: Ignoring rapid duplicate %s for lead %s", event_type, lead_id)
                return True

        # State Transitions
        if event_type == "open":
            seq.open_count = (seq.open_count or 0) + 1
            seq.last_opened = now
        elif event_type == "sent":
            seq.sent_at = now
        elif event_type == "click":
            seq.click_count = (seq.click_count or 0) + 1
            seq.last_clicked = now
        elif event_type == "reply":
            seq.replied = True
            seq.last_replied = now

        # Insert into events table
        db.add(
            Event(
                lead_id=lead_id,
                event_type=event_type,
                timestamp=now,
                additional_data=meta,
            )
        )

        # Status Derivation (Source of Truth: sequence actions)
        status_weights = {"SENT": 1, "OPENED": 2, "CLICKED": 3, "REPLIED": 4}
        events = [
            (seq.sent_at, "SENT"),
            (seq.last_opened, "OPENED"),
            (seq.last_clicked, "CLICKED"),
            (seq.last_replied, "REPLIED"),
        ]
        
        current_max_weight = 0
        final_status = "SENT"
        
        for ts, status in events:
            if ts and status_weights[status] > current_max_weight:
                current_max_weight = status_weights[status]
                final_status = status

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        status_changed = False
        if lead and lead.status != final_status:
            lead.status = final_status
            status_changed = True

        if lead:
            sync_data = {
                "linkedin_url": lead.linkedin_url,
                "email": lead.email,
                "status": final_status,
                "open_count": seq.open_count,
                "last_opened": seq.last_opened,
                "click_count": seq.click_count,
                "last_clicked": seq.last_clicked,
                "replied": seq.replied,
                "last_replied": seq.last_replied,
            }
            # Always trigger background sync to keep the sheet live
            threading.Thread(
                target=sync_sheet_status_async,
                args=(sync_data,),
                daemon=True,
            ).start()

        db.commit()
        logger.info("Successfully logged %s event for lead_id %s", event_type, lead_id)
        return True
    except Exception:
        db.rollback()
        logger.exception("Consistency Error: Event logging failed for %s", tracking_id)
        return False


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
    print(f"\n[DEBUG] OPEN REQUEST RECEIVED! ID={tracking_id}")
    tracking_id = tracking_id.replace(".png", "").replace(".gif", "").replace("logo_", "")
    # if exp is not None and sig is not None:
    #     validate_tracking_signature(tracking_id, exp, sig)

    # Log all opens, including those through proxies, to ensure reliability
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
    print(f"\n[DEBUG] CLICK DETECTED! ID={tracking_id} URL={url}")
    tracking_id = tracking_id.replace(".png", "").replace(".gif", "").replace("logo_", "")
    # if exp is not None and sig is not None:
    #     validate_tracking_signature(tracking_id, exp, sig)
    log_event(db, tracking_id, "click", request, {"target_url": url})
    
    # FORWARDING: Only forward if we are on Render
    local_url = os.getenv("LOCAL_BACKEND_URL")
    if os.getenv("RENDER") and local_url:
        async def forward():
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(f"{local_url}/api/tracking/click/{tracking_id}?url={url}", timeout=1.0)
            except Exception:
                logger.debug("Forwarding click event failed", exc_info=True)
        asyncio.create_task(forward())

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
        seq = db.query(EmailSequence).filter(EmailSequence.tracking_id == tracking_id).first()
        if not seq:
            logger.warning("Sent update failed tracking_id=%s", tracking_id)
        else:
            seq.sent_at = datetime.datetime.now()
            seq.step_number = step
        return {"status": "success", "message": f"Email Step {step} logged"}
    return {"status": "error", "message": "Tracking ID not found"}

