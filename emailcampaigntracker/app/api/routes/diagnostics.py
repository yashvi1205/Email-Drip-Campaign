from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from database.db import get_db
from database.models import Lead

router = APIRouter(tags=["Diagnostics"])


@router.get("/test-db")
def test_db(
    db: Session = Depends(get_db),
    _auth: None = Depends(require_roles("admin")),
):
    count = db.query(Lead).count()
    return {"leads_count": count}

