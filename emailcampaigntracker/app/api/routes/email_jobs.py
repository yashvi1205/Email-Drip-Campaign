from fastapi import APIRouter, BackgroundTasks, Depends
from app.core.auth import require_roles
from app.services.email_draft_service import process_pending_email_drafts
from app.services.email_send_service import process_email_approvals_and_sends

router = APIRouter(tags=["Email Jobs"])
email_auth = require_roles("admin", "dashboard")

@router.post("/api/email/draft")
def trigger_email_draft(background_tasks: BackgroundTasks, _auth: None = Depends(email_auth)):
    """Trigger the draft generation process asynchronously in the background."""
    background_tasks.add_task(process_pending_email_drafts)
    return {"status": "started", "message": "Email draft generation started in background"}

@router.post("/api/email/send")
def trigger_email_send(background_tasks: BackgroundTasks, _auth: None = Depends(email_auth)):
    """Trigger the email approval check and sending process asynchronously in the background."""
    background_tasks.add_task(process_email_approvals_and_sends)
    return {"status": "started", "message": "Email sending process started in background"}
