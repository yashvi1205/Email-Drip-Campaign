from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from app.core.settings import get_settings
from app.services.dashboard_service import drip_dashboard, sheets_status, sync_status_to_sheets

settings = get_settings()
dashboard_auth = require_api_key(settings.dashboard_api_key)

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard/drip")
def get_drip_dashboard(_auth: None = Depends(dashboard_auth)):
    return drip_dashboard()


@router.get("/api/sheets-status")
def get_sheets_status(_auth: None = Depends(dashboard_auth)):
    return sheets_status()


@router.post("/api/sync-status")
def sync_status(_auth: None = Depends(dashboard_auth)):
    return sync_status_to_sheets()

