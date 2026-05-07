from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.services.dashboard_service import drip_dashboard, sheets_status, sync_status_to_sheets

dashboard_auth = require_roles("dashboard", "admin")

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard/drip")
def get_drip_dashboard(_auth: None = Depends(dashboard_auth)):
    return drip_dashboard()


@router.get("/api/sheets-status")
def get_sheets_status(_auth: None = Depends(dashboard_auth)):
    return sheets_status()


@router.post("/api/sync-status")
def sync_status(_auth: None = Depends(require_roles("admin"))):
    return sync_status_to_sheets()

