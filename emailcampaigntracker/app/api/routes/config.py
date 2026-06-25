"""Public configuration endpoint — returns non-sensitive runtime config to the frontend."""

import os
from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/sheet-url")
def get_sheet_url():
    """Return the Google Sheet URL based on the current GOOGLE_SHEET_ID env var.

    The frontend uses this so the 'Open Google Sheet' button always links to the
    correct sheet without any hardcoded IDs in the client code.
    """
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if sheet_id:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?usp=sharing"
    else:
        url = None
    return {"sheet_id": sheet_id or None, "sheet_url": url}
